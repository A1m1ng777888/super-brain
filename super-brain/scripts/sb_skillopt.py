#!/usr/bin/env python3
"""
SuperBrain SkillOpt - Skill self-evolution engine inspired by Microsoft SkillOpt.

Implements the SkillOpt loop: rollout → reflect → edit → gate
Supports both optimizing external skills and self-evolution of super-brain.

Key differences from original SkillOpt:
1. Three signal sources (explicit > implicit > validation) instead of just validation score
2. Trace-based rollout (records actual usage, not synthetic tasks)
3. Supports both SkillOpt-Sleep (offline batch optimization) and online mode

Optimization loop:
1. Rollout: collect traces (from sb_trace) as "execution evidence"
2. Reflect: analyze success/failure patterns, identify improvement opportunities
3. Edit: propose bounded edits to SKILL.md (add/delete/replace under edit budget)
4. Gate: accept edit only if validation set score improves (or weighted score on real traces)
5. Update: if rejected, remember in buffer; if accepted, update current skill

Edit budget = "textual learning rate" (default 4 edits per round)
"""

import json
import os
import sys
import re
import difflib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (ensure_workspace, read_json, write_json, 
                    get_timestamp, generate_id, load_config)
from sb_trace import (get_traces, get_trace_stats, export_traces_for_skillopt,
                      compute_weighted_score, EXPLICIT_WEIGHT, IMPLICIT_WEIGHT, VALIDATION_WEIGHT)


# Default edit budget (textual learning rate)
DEFAULT_EDIT_BUDGET = 4

# Minimum improvement to accept an edit (validation set score delta)
MIN_IMPROVEMENT = 0.01

# Rejected edit buffer size
REJECTED_BUFFER_SIZE = 20


def get_skillopt_dir(workspace=None):
    """Get skillopt working directory."""
    ws_dir = ensure_workspace(workspace)
    skillopt_dir = os.path.join(ws_dir, "skillopt")
    os.makedirs(skillopt_dir, exist_ok=True)
    return skillopt_dir


def load_skill_file(skill_path):
    """Load a SKILL.md file, return (frontmatter, content) tuple."""
    with open(skill_path, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Parse frontmatter if present
    frontmatter = {}
    content = text
    if text.startswith("---"):
        end_idx = text.find("---", 3)
        if end_idx != -1:
            fm_text = text[3:end_idx].strip()
            content = text[end_idx+3:].strip()
            # Parse simple YAML-like frontmatter
            for line in fm_text.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    frontmatter[key.strip()] = val.strip()
    
    return frontmatter, content


def save_skill_file(skill_path, frontmatter, content):
    """Save SKILL.md with optional frontmatter."""
    with open(skill_path, "w", encoding="utf-8") as f:
        if frontmatter:
            f.write("---\n")
            for k, v in frontmatter.items():
                f.write(f"{k}: {v}\n")
            f.write("---\n\n")
        f.write(content)


def compute_edit_budget(epoch, base_budget=DEFAULT_EDIT_BUDGET):
    """
    Compute edit budget for current epoch.
    Budget decreases as training progresses (like learning rate decay).
    """
    if epoch <= 2:
        return base_budget
    elif epoch <= 5:
        return max(2, base_budget - 1)
    else:
        return max(1, base_budget - 2)


def analyze_traces_for_reflection(traces, skill_content):
    """
    Analyze traces to generate reflection insights.
    Returns dict with patterns found in successes and failures.
    """
    successes = [t for t in traces if t["weighted_score"] > 0]
    failures = [t for t in traces if t["weighted_score"] <= 0]
    
    reflection = {
        "epoch": None,
        "total_traces": len(traces),
        "success_count": len(successes),
        "failure_count": len(failures),
        "success_patterns": [],
        "failure_patterns": [],
        "edit_suggestions": []
    }
    
    # Analyze failure patterns
    failure_commands = {}
    for t in failures:
        cmd = t["command"]
        failure_commands[cmd] = failure_commands.get(cmd, 0) + 1
    
    if failure_commands:
        reflection["failure_patterns"].append({
            "type": "command_failure_frequency",
            "data": failure_commands,
            "insight": f"Commands with most failures: {max(failure_commands, key=failure_commands.get)}"
        })
    
    # Check for common failure signals
    error_traces = [t for t in failures if t["signals"]["implicit"].get("error")]
    if error_traces:
        reflection["failure_patterns"].append({
            "type": "execution_errors",
            "count": len(error_traces),
            "insight": "Execution errors detected in traces"
        })
    
    # Analyze success patterns
    satisfied_traces = [t for t in successes if t["signals"]["explicit"] and 
                        t["signals"]["explicit"]["rating"] == "satisfied"]
    if satisfied_traces:
        reflection["success_patterns"].append({
            "type": "explicit_satisfaction",
            "count": len(satisfied_traces),
            "insight": "Users explicitly satisfied with these executions"
        })
    
    return reflection


def generate_edit_suggestions(reflection, skill_content, edit_budget):
    """
    Generate edit suggestions based on reflection.
    This is a rule-based approach; in production this would use an LLM.
    
    Returns list of edit operations: {"type": "add|delete|replace", "target": ..., "content": ...}
    """
    suggestions = []
    
    # Rule 1: If many execution errors, add error handling guidance
    error_pattern = next((p for p in reflection["failure_patterns"] 
                         if p["type"] == "execution_errors"), None)
    if error_pattern and error_pattern["count"] >= 3:
        suggestions.append({
            "type": "add",
            "section": "troubleshooting",
            "content": "\n### 常见错误处理\n- 执行前检查所有依赖是否可用\n- 文件操作前验证路径存在\n- 网络操作添加超时和重试\n",
            "reason": f"检测到 {error_pattern['count']} 次执行错误，建议添加错误处理指导"
        })
    
    # Rule 2: If specific commands fail often, add clarification
    cmd_pattern = next((p for p in reflection["failure_patterns"] 
                       if p["type"] == "command_failure_frequency"), None)
    if cmd_pattern:
        worst_cmd = max(cmd_pattern["data"], key=cmd_pattern["data"].get)
        suggestions.append({
            "type": "add",
            "section": "command_guidance",
            "content": f"\n### {worst_cmd} 命令注意事项\n- 确保输入参数完整\n- 检查输出格式是否符合预期\n",
            "reason": f"命令 {worst_cmd} 失败频率最高，需补充指导"
        })
    
    # Rule 3: If high satisfaction, preserve those patterns
    sat_pattern = next((p for p in reflection["success_patterns"] 
                       if p["type"] == "explicit_satisfaction"), None)
    if sat_pattern and len(suggestions) < edit_budget:
        suggestions.append({
            "type": "add",
            "section": "best_practices",
            "content": "\n### 用户满意的操作模式\n- 按步骤执行并及时反馈进度\n- 完成后主动总结结果\n",
            "reason": "用户满意度高的模式，建议固化为最佳实践"
        })
    
    return suggestions[:edit_budget]


def apply_edits(skill_content, edits):
    """
    Apply edit operations to skill content.
    Returns new content and list of applied edits.
    """
    new_content = skill_content
    applied = []
    
    for edit in edits:
        if edit["type"] == "add":
            # Simple append to end (in production, would target specific sections)
            new_content += edit["content"]
            applied.append(edit)
        
        elif edit["type"] == "replace":
            # Replace target text if found
            target = edit.get("target", "")
            replacement = edit.get("content", "")
            if target and target in new_content:
                new_content = new_content.replace(target, replacement, 1)
                applied.append(edit)
        
        elif edit["type"] == "delete":
            # Delete target text if found
            target = edit.get("target", "")
            if target and target in new_content:
                new_content = new_content.replace(target, "")
                applied.append(edit)
    
    return new_content, applied


def compute_validation_score(skill_path, validation_tasks):
    """
    Compute validation score by running skill on validation tasks.
    For super-brain, this runs subcommands and checks outputs.
    
    Returns float 0-1 (average score across tasks).
    """
    # This is a placeholder - in production, this would actually execute tasks
    # For now, return a mock score based on skill file completeness
    
    if not os.path.exists(skill_path):
        return 0.0
    
    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Simple heuristic: score based on completeness of SKILL.md
    score = 0.0
    checks = [
        ("触发词" in content or "trigger" in content.lower(), 0.2),
        ("子命令" in content or "subcommand" in content.lower(), 0.2),
        ("示例" in content or "example" in content.lower(), 0.2),
        (len(content) > 1000, 0.2),
        ("troubleshoot" in content.lower() or "故障" in content, 0.1),
        ("best_practice" in content.lower() or "最佳实践" in content, 0.1),
    ]
    
    for check, weight in checks:
        if check:
            score += weight
    
    return min(score, 1.0)


def run_skillopt_epoch(skill_path, traces, validation_tasks, epoch, workspace=None):
    """
    Run one SkillOpt epoch.
    
    Args:
        skill_path: path to SKILL.md being optimized
        traces: list of execution traces
        validation_tasks: list of validation task dicts
        epoch: current epoch number
        workspace: workspace name
    
    Returns:
        dict: epoch result with edit decisions
    """
    # Load current skill
    frontmatter, skill_content = load_skill_file(skill_path)
    edit_budget = compute_edit_budget(epoch)
    
    # Step 1: Reflect
    reflection = analyze_traces_for_reflection(traces, skill_content)
    reflection["epoch"] = epoch
    
    # Step 2: Generate edits
    edits = generate_edit_suggestions(reflection, skill_content, edit_budget)
    
    if not edits:
        return {
            "epoch": epoch,
            "status": "no_edits",
            "message": "No edit suggestions generated",
            "reflection": reflection
        }
    
    # Step 3: Apply edits to create candidate
    candidate_content, applied_edits = apply_edits(skill_content, edits)
    
    # Step 4: Gate (validation)
    current_score = compute_validation_score(skill_path, validation_tasks)
    candidate_path = skill_path + ".candidate"
    save_skill_file(candidate_path, frontmatter, candidate_content)
    candidate_score = compute_validation_score(candidate_path, validation_tasks)
    
    accepted = (candidate_score - current_score) >= MIN_IMPROVEMENT
    
    # Step 5: Update
    epoch_result = {
        "epoch": epoch,
        "timestamp": get_timestamp(),
        "edit_budget": edit_budget,
        "reflection": reflection,
        "proposed_edits": edits,
        "applied_edits": applied_edits,
        "current_score": current_score,
        "candidate_score": candidate_score,
        "accepted": accepted
    }
    
    if accepted:
        # Accept candidate: replace skill file
        save_skill_file(skill_path, frontmatter, candidate_content)
        epoch_result["status"] = "accepted"
        epoch_result["message"] = f"Edit accepted (score {current_score:.3f} → {candidate_score:.3f})"
        
        # Save accepted edit to history
        save_optimization_history(epoch_result, workspace)
    else:
        # Reject: save to rejected buffer
        epoch_result["status"] = "rejected"
        epoch_result["message"] = f"Edit rejected (score {current_score:.3f} → {candidate_score:.3f})"
        
        save_rejected_edit(epoch_result, workspace)
        
        # Clean up candidate file
        if os.path.exists(candidate_path):
            os.remove(candidate_path)
    
    return epoch_result


def save_optimization_history(epoch_result, workspace=None):
    """Save accepted optimization result to history."""
    skillopt_dir = get_skillopt_dir(workspace)
    history_path = os.path.join(skillopt_dir, "optimization_history.json")
    history = read_json(history_path) or []
    history.append(epoch_result)
    write_json(history_path, history)


def save_rejected_edit(epoch_result, workspace=None):
    """Save rejected edit to buffer (negative feedback for optimizer)."""
    skillopt_dir = get_skillopt_dir(workspace)
    buffer_path = os.path.join(skillopt_dir, "rejected_buffer.json")
    buffer = read_json(buffer_path) or []
    buffer.append(epoch_result)
    # Keep only recent rejections
    buffer = buffer[-REJECTED_BUFFER_SIZE:]
    write_json(buffer_path, buffer)


def get_optimization_history(workspace=None, limit=10):
    """Get optimization history."""
    skillopt_dir = get_skillopt_dir(workspace)
    history_path = os.path.join(skillopt_dir, "optimization_history.json")
    history = read_json(history_path) or []
    history.sort(key=lambda x: x.get("epoch", 0), reverse=True)
    return history[:limit]


def get_rejected_buffer(workspace=None):
    """Get rejected edit buffer."""
    skillopt_dir = get_skillopt_dir(workspace)
    buffer_path = os.path.join(skillopt_dir, "rejected_buffer.json")
    return read_json(buffer_path) or []


def rollback_skillopt(epoch, skill_path, workspace=None):
    """
    Rollback to a previous epoch.
    Note: This requires keeping backups of previous skill versions.
    """
    history = get_optimization_history(workspace, limit=100)
    target = next((h for h in history if h["epoch"] == epoch), None)
    
    if not target:
        return {"status": "error", "message": f"Epoch {epoch} not found in history"}
    
    # In production, would restore from backup
    # For now, return the epoch result for manual restoration
    return {
        "status": "rollback_info",
        "message": f"To rollback to epoch {epoch}, restore from backup or manually revert the edits",
        "epoch_result": target
    }


def optimize_external_skill(skill_path, traces, validation_tasks, epochs=3, workspace=None):
    """
    Optimize an external skill using SkillOpt.
    
    Args:
        skill_path: path to target SKILL.md
        traces: execution traces (can be empty for cold start)
        validation_tasks: validation task set
        epochs: number of optimization epochs
        workspace: workspace for storing optimization state
    
    Returns:
        dict: optimization results
    """
    results = []
    
    for epoch in range(1, epochs + 1):
        result = run_skillopt_epoch(skill_path, traces, validation_tasks, epoch, workspace)
        results.append(result)
        
        # If no edits generated, stop early
        if result["status"] == "no_edits":
            break
    
    return {
        "skill_path": skill_path,
        "epochs_completed": len(results),
        "results": results,
        "final_status": results[-1]["status"] if results else "not_started"
    }


def self_evolve(epochs=3, validation_tasks=None, workspace=None):
    """
    Self-evolution: optimize super-brain's own SKILL.md.
    
    Args:
        epochs: number of optimization epochs
        validation_tasks: validation task set (uses default if None)
        workspace: workspace name
    
    Returns:
        dict: optimization results
    """
    # Find own SKILL.md
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skill_path = os.path.join(skill_dir, "SKILL.md")
    
    if not os.path.exists(skill_path):
        return {"status": "error", "message": "SKILL.md not found"}
    
    # Get traces from this workspace
    traces = get_traces(workspace, limit=1000)
    
    if not traces:
        return {"status": "error", "message": "No traces found. Run super-brain commands first to collect execution traces."}
    
    # Use default validation tasks if none provided
    if not validation_tasks:
        validation_tasks = get_default_validation_tasks()
    
    return optimize_external_skill(skill_path, traces, validation_tasks, epochs, workspace)


def get_default_validation_tasks():
    """
    Get default validation tasks for super-brain self-evaluation.
    These are predefined tasks that test core super-brain functionality.
    """
    return [
        {
            "name": "记忆写入与召回",
            "command": "memory add",
            "input": {"content": "测试记忆", "type": "fact"},
            "expected_output": {"id": True},  # expects an ID in output
            "score_weight": 1.0
        },
        {
            "name": "语义搜索",
            "command": "memory search",
            "input": {"query": "测试"},
            "expected_output": {"results": True},
            "score_weight": 1.0
        },
        {
            "name": "知识图谱节点添加",
            "command": "graph add-node",
            "input": {"name": "测试节点", "type": "concept"},
            "expected_output": {"id": True},
            "score_weight": 1.0
        },
        {
            "name": "自检功能",
            "command": "selfcheck",
            "input": {},
            "expected_output": {"overall_status": True},
            "score_weight": 1.0
        }
    ]


def skillopt_status(workspace=None):
    """Get SkillOpt optimization status."""
    history = get_optimization_history(workspace)
    rejected = get_rejected_buffer(workspace)
    trace_stats = get_trace_stats(workspace)
    
    return {
        "optimization_epochs": len(history),
        "last_epoch": history[0]["epoch"] if history else None,
        "last_epoch_status": history[0]["status"] if history else None,
        "rejected_edits": len(rejected),
        "trace_stats": trace_stats,
        "default_validation_tasks": len(get_default_validation_tasks())
    }
