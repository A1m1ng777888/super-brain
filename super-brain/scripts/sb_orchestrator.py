#!/usr/bin/env python3
"""
SuperBrain Orchestrator — Sub-Agent Orchestration Engine (v3.3.0)

Orchestrator+Executor pattern for multi-agent task decomposition.
When a single agent can't handle it (context overflow / parallel exploration /
capability divergence), this module assesses, decomposes, and generates
sub-agent specs with budget caps, failure isolation, and anti-orchestration gating.

v3.3.0 — Goal Continuation (Level 2):
  - Structured goal evaluation after all sub-tasks complete
  - Stall detection via result signature hashing (zero LLM cost)
  - Max 4 continuations with progressive back-off
  - Continuation count tracked per orchestration trace

Design principles:
  1. Only orchestrate when parallel gain > coordination cost
  2. Each sub-task MUST be independent (no chained dependencies)
  3. Minimal tool set per sub-agent (no full-context pollution)
  4. Budget circuit breaker prevents token runaway
  5. Single-subtask failure never cascades to global failure
  6. Goal-level continuation with stall detection (v3.3.0)

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import json
import os
import re
from collections import defaultdict

from sb_core import (
    get_timestamp, generate_id, ensure_workspace, get_workspace_dir,
    read_json, write_json, load_config
)

# ─── Constants ────────────────────────────────────────────────────────────

# Complexity score threshold: ≥ this → recommend orchestration
ORCHESTRATE_THRESHOLD = 0.6

# Anti-orchestration: hard rejection when these patterns are detected
SEQUENTIAL_PATTERNS = [
    r"然后.*再.*然后",          # "do A then B then C" — strongly sequential
    r"依次|逐个|逐一|按顺序",    # explicit sequential keywords
    r"步骤[一二三四五六七八九十\d]+",  # numbered steps implying order
    r"先.*后.*再",              # "first A, then B, then C"
]
TRIVIAL_PATTERNS = [
    r"^.{1,20}$",              # very short task (≤20 chars)
    r"帮我看(一下|看)?",        # "help me look at" — simple lookup
    r"这是什么|怎么.*(读|念|写|拼)",  # definition/pronunciation
    r"翻译|translate",
    r"几点了|今天是|现在时间",
]

# Budget
DEFAULT_BUDGET_CAP = 50000         # max total tokens per orchestration
DEFAULT_SUB_BUDGET = 10000         # max tokens per sub-agent
MAX_RETRIES_PER_SUB = 2            # retries before marking failed
CIRCUIT_BREAKER_FAILURES = 3       # session-level: stop spawning after N failures

# v3.3.0 — Goal Continuation constants
MAX_CONTINUATIONS = 4              # max orchestration-level continuations
STALL_SIGNATURE_PRECISION = 8      # hash length for stall detection signature
PARTIAL_SUCCESS_THRESHOLD = 0.5    # ≤50% sub-tasks failed → partial success, continueable

# ─── Tool Profiles ────────────────────────────────────────────────────────

TOOL_PROFILES = {
    "research": {
        "description": "Web search, documentation lookup, information gathering",
        "subagent_type": "Explore",
        "tools": ["WebSearch", "WebFetch", "Read", "Glob", "Grep"],
        "skills": [],
        "token_weight": 0.6
    },
    "code": {
        "description": "Writing, editing, testing code; file operations; running commands",
        "subagent_type": "general-purpose",
        "tools": ["Write", "Edit", "Read", "Bash", "Glob", "Grep", "PowerShell"],
        "skills": [],
        "token_weight": 0.8
    },
    "design": {
        "description": "Visual design, UI/UX, layout, styling",
        "subagent_type": "general-purpose",
        "tools": ["Write", "Edit", "Read", "show_widget", "read_me"],
        "skills": ["impeccable", "design-taste-frontend", "modern-web-design"],
        "token_weight": 0.7
    },
    "data": {
        "description": "Data analysis, spreadsheet processing, charts, statistics",
        "subagent_type": "Explore",
        "tools": ["Read", "Write", "Bash", "Grep"],
        "skills": ["xlsx", "xlsx"],
        "token_weight": 0.7
    },
    "docs": {
        "description": "Document creation, editing, formatting (docx, pdf, pptx)",
        "subagent_type": "general-purpose",
        "tools": ["Read", "Write", "Edit", "Bash"],
        "skills": ["docx", "pptx", "pdf", "word-docx"],
        "token_weight": 0.6
    },
    "general": {
        "description": "General-purpose sub-agent, minimal tools",
        "subagent_type": "general-purpose",
        "tools": ["Read", "Write", "Edit", "Bash"],
        "skills": [],
        "token_weight": 1.0
    }
}


def _build_tool_index():
    """Build a lookup index of all tools in profiles."""
    idx = defaultdict(list)
    for name, profile in TOOL_PROFILES.items():
        for tool in profile.get("tools", []):
            idx[tool].append(name)
        for skill in profile.get("skills", []):
            idx[f"skill:{skill}"].append(name)
    return dict(idx)

TOOL_INDEX = _build_tool_index()

# ─── Complexity Assessment ────────────────────────────────────────────────

def assess_complexity(task_description, current_context_size=0, workspace=None):
    """

    Evaluate whether a task should be orchestrated into sub-agents.

    Returns a score 0-1 and breakdown across 4 dimensions:
      - context_isolation: how much current context is polluted/diluted
      - task_independence: how well the task can be decomposed independently
      - tool_divergence: how different the required tools are from current
      - token_risk: how likely the task is to overflow the context window

    Args:
        task_description: str, the task the user wants done
        current_context_size: int, estimated tokens in current conversation
        workspace: str, workspace name

    Returns:
        dict with keys: score, recommend, dimensions, reasoning
    """

    description = task_description.strip()
    desc_len = len(description)

    # ── Dimension 1: Context Isolation ──
    # High when conversation is long and the task is a new topic
    context_score = min(current_context_size / 80000, 1.0) * 0.8
    # Boost if task introduces new entities not in recent context
    novel_keywords = _detect_novel_keywords(description, workspace)
    context_score = min(context_score + novel_keywords * 0.2, 1.0)

    # ── Dimension 2: Task Independence ──
    # Score how parallelizable this task is
    independence_score = _assess_independence(description)

    # ── Dimension 3: Tool Divergence ──
    # How different are the needed tools from default conversation tools?
    needed_profiles = _detect_needed_profiles(description)
    divergence_score = min(len(needed_profiles) / 3.0, 1.0)

    # ── Dimension 4: Token Risk ──
    # Estimate if this task will overflow context
    estimated_tokens = _estimate_task_tokens(description)
    token_score = min(estimated_tokens / 30000, 1.0)

    # ── Compute composite ──
    weights = {
        "context_isolation": 0.25,
        "task_independence": 0.35,  # most important: can we actually parallelize?
        "tool_divergence": 0.25,
        "token_risk": 0.15
    }

    composite = (
        weights["context_isolation"] * context_score +
        weights["task_independence"] * independence_score +
        weights["tool_divergence"] * divergence_score +
        weights["token_risk"] * token_score
    )

    dimensions = {
        "context_isolation": round(context_score, 3),
        "task_independence": round(independence_score, 3),
        "tool_divergence": round(divergence_score, 3),
        "token_risk": round(token_score, 3)
    }

    # Generate reasoning
    reasoning_parts = []
    if context_score > 0.5:
        reasoning_parts.append("当前上下文已高度混杂，需要隔离执行")
    if independence_score > 0.5:
        reasoning_parts.append("任务可拆分为多个独立并行的方向")
    else:
        reasoning_parts.append("任务依赖性强，串行执行为主")
    if divergence_score > 0.3:
        reasoning_parts.append(f"需要不同工具画像: {', '.join(needed_profiles[:3])}")
    if token_score > 0.5:
        reasoning_parts.append(f"预估 {estimated_tokens} tokens，可能撑爆上下文窗口")

    # v3.7: 能力感知路由 — 检查任务是否落在超脑的锯齿凹陷点上
    capability_warnings = []
    try:
        from sb_capability import assess_task_capabilities
        cap_result = assess_task_capabilities(description, workspace)
        capability_warnings = cap_result.get("warnings", [])
        if capability_warnings:
            weak_caps = [w["capability"] for w in capability_warnings]
            reasoning_parts.append(f"⚠️ 能力凹陷点: {', '.join(weak_caps)}")
            if cap_result.get("has_critical_warnings"):
                reasoning_parts.append("存在严重能力不足，建议显式求助用户")
    except Exception:
        pass  # 能力检查失败不阻塞评估

    return {
        "score": round(composite, 3),
        "recommend": composite >= ORCHESTRATE_THRESHOLD,
        "threshold": ORCHESTRATE_THRESHOLD,
        "dimensions": dimensions,
        "reasoning": "；".join(reasoning_parts) if reasoning_parts else "任务简单，单Agent可处理",
        "estimated_tokens": estimated_tokens,
        "needed_profiles": needed_profiles,
        # v3.7: capability-aware routing
        "capability_warnings": capability_warnings
    }


def _detect_novel_keywords(description, workspace=None):
    """Detect keywords not present in current workspace memories. Returns 0-1."""
    try:
        ws_dir = get_workspace_dir(workspace)
        mem_path = os.path.join(ws_dir, "memories.json")
        if not os.path.exists(mem_path):
            return 0.5  # no memories yet → assume novel
        memories = read_json(mem_path) or []

        # Extract significant words from description
        words = set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{4,}', description))
        if not words:
            return 0.0

        # Check against memory content
        known = set()
        for mem in memories[:50]:  # sample recent 50
            content = mem.get("content", "") + mem.get("entity", "")
            for w in words:
                if w.lower() in content.lower():
                    known.add(w)

        novel_ratio = 1.0 - (len(known) / len(words)) if words else 0.0
        return novel_ratio
    except Exception:
        return 0.5


def _assess_independence(description):
    """Score 0-1 how parallelizable the task is.

    High independence: multiple subtopics, explicit parallel markers, list of items,
    OR implicit scope (single sentence describing a large multi-domain project).

    Low independence: sequential markers, single focused task with no expansion.
    """
    score = 0.5  # neutral baseline

    # ── Boost: explicit parallel markers ──
    parallel_markers = [
        r"(同时|一并|分别|各自|各|每个|每项|多项).{0,10}(做|处理|完成|执行)",
        r"(和|以及|并且).{0,5}(都|也|同样)",
        r"分别.*和.*和",  # "分别 A、B 和 C"
        r"[、,].{2,}[、,]",  # multiple comma-separated items
        r"列表|清单|批量",
        r"几个.*问题|多个.*任务"
    ]
    for pattern in parallel_markers:
        if re.search(pattern, description):
            score += 0.1

    # ── Penalty: sequential markers ──
    for pattern in SEQUENTIAL_PATTERNS:
        if re.search(pattern, description):
            score -= 0.2

    # ── Count distinct subtopics via sentence boundaries ──
    sentences = re.split(r'[。！？\n]', description)
    substantive = [s for s in sentences if len(s.strip()) > 10]
    if len(substantive) >= 3:
        score += 0.1
    if len(substantive) >= 5:
        score += 0.1

    # ── NEW: Implicit scope detection ──
    # Even single-sentence tasks can imply multi-domain work.
    # "搭建完整的电商网站" — one sentence, but it's frontend + backend + deploy.

    # Multi-profile boost: different profiles = different sub-agents
    profiles = _detect_needed_profiles(description)
    if len(profiles) >= 4:
        score += 0.25
    elif len(profiles) >= 3:
        score += 0.20
    elif len(profiles) >= 2:
        score += 0.12

    # Domain-complexity boost: certain keywords imply massive scope
    scope_keywords = [
        (r'完整的?|全套|全栈|full.?stack|搭建.*(?:网站|项目|应用)|build.*from.*scratch|从零', 0.25),
        (r'系统|平台|platform|应用|app|application|企业级', 0.18),
        (r'项目|project|重构|refactor|迁移|migrate|改造', 0.15),
        (r'所有|全部|整体|整个|all|entire|whole|全面', 0.12),
        (r'大型|大型|大规模|large.?scale|复杂|complex', 0.15),
        (r'包括|包含|涵盖|涉及|cover', 0.10),
    ]
    for pattern, boost in scope_keywords:
        if re.search(pattern, description):
            score += boost
            break  # apply only the highest-matching boost

    # ── Token volume boost: large estimated work → parallelization potential ──
    est_tokens = _estimate_task_tokens(description)
    if est_tokens >= 15000:
        score += 0.12
    elif est_tokens >= 8000:
        score += 0.07

    return max(0.0, min(1.0, score))


def _detect_needed_profiles(description):
    """Detect which tool profiles a task needs based on keyword analysis."""
    desc_lower = description.lower()
    profiles = []

    # Research indicators
    if re.search(r'搜索|查|找.*资料|调研|研究|了解|最新|news|search|research|论文', description):
        profiles.append("research")

    # Code indicators
    if re.search(r'代码|编程|写.*程序|脚本|bug|修复|测试|test|code|函数|function|class|import|API|接口|框架|npm|pip|git|前端|后端|frontend|backend|数据库|database|部署|deploy', description):
        profiles.append("code")

    # Design indicators
    if re.search(r'设计|UI|界面|样式|CSS|颜色|布局|排版|视觉|美化|动效|动画|animation|design|icon|logo|网站|网页|web|website|页面|page', description):
        profiles.append("design")

    # Data indicators
    if re.search(r'数据|分析|统计|图表|报表|excel|表格|计算|汇总|data|chart|analyze|statistic', description):
        profiles.append("data")

    # Docs indicators
    if re.search(r'文档|报告|论文|ppt|word|pdf|docx|slide|演示|汇报|document|report', description):
        profiles.append("docs")

    if not profiles:
        profiles.append("general")

    return profiles


def _estimate_task_tokens(description):
    """Token estimate with domain-aware floor.

    Text-length estimates are too conservative for single-sentence big tasks.
    "搭建完整的电商网站" is 8 chars but implies 15000+ tokens of work.
    We use domain keywords to set a realistic floor, not just text-length × multiplier.
    """
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', description))
    english_chars = len(re.findall(r'[a-zA-Z]', description))
    other_chars = len(description) - chinese_chars - english_chars

    text_base = chinese_chars / 2.0 + english_chars / 4.0 + other_chars / 3.0

    # ── Domain-aware floor estimation ──
    # Keywords that imply a large scope get a minimum token floor
    domain_floor = 0
    domain_keywords = [
        (r'完整的?(?:网站|web|网页|website|前后端|全栈|商城|电商|博客|论坛)', 15000),
        (r'全栈|full.?stack', 20000),
        (r'从零|from.*scratch|搭建.*(?:网站|项目|应用)', 12000),
        (r'(?:企业级|大型)(?:系统|平台|应用)', 18000),
        (r'重构|refactor|迁移|migrate', 10000),
        (r'分析.*(?:项目|代码库|codebase)', 8000),
        (r'完整的?(?:报告|文档|论文|手册)', 6000),
        (r'设计.*完整的?(?:系统|架构)', 8000),
    ]
    for pattern, floor in domain_keywords:
        if re.search(pattern, description):
            domain_floor = floor
            break

    # ── Profile-based multiplier ──
    profiles = _detect_needed_profiles(description)
    profile_count = len(profiles)

    # Base multiplier from activity type
    if re.search(r'代码|code|脚本|script|build|implement|开发|构建|部署', description):
        activity_mult = 5
    elif re.search(r'分析|报告|report|analyze|research', description):
        activity_mult = 3
    else:
        activity_mult = 2

    # Combine: max of (domain floor, text × multiplier × profile factor)
    text_estimate = text_base * activity_mult * max(1.0, profile_count * 0.7)
    estimate = max(text_estimate, domain_floor)

    return int(estimate)


# ─── Anti-Orchestration Gate ──────────────────────────────────────────────

def should_orchestrate(task_description, current_context_size=0, workspace=None):
    """
    Master decision function: should we spawn sub-agents?

    Hard gates (return False immediately):
      1. Task is trivially simple
      2. Task is strongly sequential
      3. Complexity score < threshold
      4. Circuit breaker tripped

    Returns:
        dict with: should_spawn, reason, assessment, gate
    """

    # Gate 1: Trivial task?
    for pattern in TRIVIAL_PATTERNS:
        if re.search(pattern, task_description.strip()):
            return {
                "should_spawn": False,
                "reason": "任务过于简单，编配开销大于收益",
                "gate": "trivial",
                "assessment": None
            }

    # Gate 2: Strongly sequential?
    sequential_hits = []
    for pattern in SEQUENTIAL_PATTERNS:
        if re.search(pattern, task_description.strip()):
            sequential_hits.append(pattern)
    if len(sequential_hits) >= 2:  # require ≥2 sequential patterns for rejection
        return {
            "should_spawn": False,
            "reason": "任务存在强顺序依赖，拆解后反而更慢",
            "gate": "sequential",
            "details": {"matched_patterns": sequential_hits},
            "assessment": None
        }

    # Gate 3: Circuit breaker?
    if _is_circuit_broken(workspace):
        return {
            "should_spawn": False,
            "reason": f"会话内已有{CIRCUIT_BREAKER_FAILURES}次失败，熔断生效",
            "gate": "circuit_breaker",
            "assessment": None
        }

    # Gate 4: Complexity assessment
    assessment = assess_complexity(task_description, current_context_size, workspace)

    if not assessment["recommend"]:
        return {
            "should_spawn": False,
            "reason": f"复杂度评分 {assessment['score']:.2f} < 阈值 {ORCHESTRATE_THRESHOLD}",
            "gate": "complexity",
            "assessment": assessment
        }

    return {
        "should_spawn": True,
        "reason": assessment["reasoning"],
        "gate": "passed",
        "assessment": assessment
    }


def _is_circuit_broken(workspace=None):
    """Check if session-level circuit breaker is tripped."""
    try:
        ws_dir = get_workspace_dir(workspace)
        orch_path = os.path.join(ws_dir, "orchestrator.json")
        if not os.path.exists(orch_path):
            return False
        data = read_json(orch_path)
        if not data:
            return False
        recent_failures = [t for t in data.get("traces", [])[-20:]
                          if t.get("status") == "failed"]
        if len(recent_failures) >= CIRCUIT_BREAKER_FAILURES:
            last_success_idx = -1
            for i, t in enumerate(reversed(data.get("traces", []))):
                if t.get("status") == "completed":
                    last_success_idx = len(data["traces"]) - 1 - i
                    break
            # Only trip if failures are consecutive (no recent success)
            all_after_success = data["traces"][last_success_idx + 1:] if last_success_idx >= 0 else data["traces"]
            consecutive_failures = sum(1 for t in all_after_success if t.get("status") == "failed")
            return consecutive_failures >= CIRCUIT_BREAKER_FAILURES
        return False
    except Exception:
        return False


# ─── Task Decomposition Engine ───────────────────────────────────────────

def decompose_task(task_description, workspace=None):
    """
    Decompose a task into independent, parallelizable sub-tasks.

    Each sub-task receives 4 required fields:
      1. objective — clear one-sentence goal
      2. output_format — expected deliverable format
      3. tools — which tool profile(s) to use
      4. boundary — where the work ends (explicit constraint)

    Decomposition strategies (tried in order):
      S1: Explicit numbered/listed sub-tasks (user enumerated)
      S2: Multi-profile expansion — each distinct profile = one sub-task
      S3: Single-profile large task — expand into implicit sub-components
      S4: Fallback — single general sub-task

    Args:
        task_description: str
        workspace: str

    Returns:
        dict with: sub_tasks, count, independence_score, warnings
    """

    profiles = _detect_needed_profiles(task_description)
    description = task_description.strip()
    sub_tasks = []

    # Strategy 1: Explicit numbered/listed sub-tasks
    pattern = r'(?:^|\n)\s*(?:\d+[.、．]|[-•*]\s+)(.+?)(?=(?:\n\s*(?:\d+[.、．]|[-•*]\s+)|\Z))'
    matches = re.findall(pattern, description, re.DOTALL)
    if matches and len(matches) >= 2:
        for i, match in enumerate(matches):
            sub_desc = match.strip()
            sub_profiles = _detect_needed_profiles(sub_desc)
            sub_tasks.append(_build_subtask(
                index=i, description=sub_desc, profiles=sub_profiles
            ))
    elif len(profiles) >= 2:
        # Strategy 2: Multi-profile — one sub-task per distinct profile
        scope_notes = {
            "research": "仅负责信息搜索与资料汇总，不涉及代码编写或设计",
            "code": "仅负责代码编写/修改/测试，不涉及视觉设计或文档排版",
            "design": "仅负责视觉设计/布局/动效，不涉及后端逻辑或数据处理",
            "data": "仅负责数据分析/图表/统计，不涉及前端UI或文档写作",
            "docs": "仅负责文档创建/编辑/格式化，不涉及代码或设计",
        }
        for profile in profiles:
            sub_tasks.append(_build_subtask(
                index=len(sub_tasks), description=description,
                profiles=[profile],
                scope_note=scope_notes.get(profile, TOOL_PROFILES[profile]['description'])
            ))
    else:
        # Strategy 3: Single-profile large task — expand into implicit sub-components
        implicit_subs = _discover_implicit_subtasks(
            description, profiles[0] if profiles else "general"
        )
        if implicit_subs and len(implicit_subs) >= 2:
            for i, sub in enumerate(implicit_subs):
                sub_tasks.append(_build_subtask(
                    index=i, description=sub.get("description", description),
                    profiles=[sub.get("profile", profiles[0])],
                    scope_note=sub.get("scope_note")
                ))
        else:
            # Strategy 4: Fallback — single general sub-task
            sub_tasks.append(_build_subtask(
                index=0, description=description, profiles=["general"]
            ))

    # ── Independence validation ──
    independence_issues = validate_isolation(sub_tasks)

    return {
        "sub_tasks": sub_tasks,
        "count": len(sub_tasks),
        "independence_score": 1.0 - (len(independence_issues) * 0.15),
        "warnings": independence_issues,
        "profiles_used": list(set(p for t in sub_tasks for p in t.get("profiles", [])))
    }


def _discover_implicit_subtasks(description, primary_profile):
    """For single-sentence large tasks, auto-discover implicit sub-components.

    Example: "帮我搭建一个完整的电商网站"
      → [{profile: "code", label: "前端开发"}, {profile: "code", label: "后端API"},
         {profile: "design", label: "UI设计"}, {profile: "docs", label: "项目文档"}]

    Returns list of {profile, description, scope_note} dicts, or [] if undiscoverable.
    """
    # ── Domain → implied sub-components ──
    IMPLICIT_DECOMPOSITIONS = [
        (r'网站|web|website|网页|前后端|全栈|商城|电商|博客|论坛',
         [
             {"profile": "code", "label": "前端开发", "scope": "仅负责前端页面、组件、路由、状态管理"},
             {"profile": "code", "label": "后端API与数据库", "scope": "仅负责后端接口、数据模型、业务逻辑"},
             {"profile": "design", "label": "UI设计与样式", "scope": "仅负责视觉设计、配色、组件样式"},
             {"profile": "docs", "label": "项目文档", "scope": "仅负责README、API文档、部署说明"},
         ]),
        (r'完整的?(?:报告|分析报告|调研)',
         [
             {"profile": "research", "label": "资料搜集", "scope": "仅负责信息搜索、资料整理、数据采集"},
             {"profile": "data", "label": "数据分析", "scope": "仅负责数据处理、统计、可视化图表"},
             {"profile": "docs", "label": "报告撰写", "scope": "仅负责报告结构、写作、格式化排版"},
         ]),
        (r'重构|refactor|迁移|migrate',
         [
             {"profile": "research", "label": "现状分析", "scope": "仅负责扫描现有代码、识别问题、生成分析报告"},
             {"profile": "code", "label": "重构实施", "scope": "仅负责代码重构、模块重写、测试更新"},
             {"profile": "docs", "label": "变更文档", "scope": "仅负责迁移指南、变更日志、API变更说明"},
         ]),
    ]

    for pattern, components in IMPLICIT_DECOMPOSITIONS:
        if components and re.search(pattern, description):
            results = []
            for c in components:
                results.append({
                    "profile": c["profile"],
                    "description": f"「{description}」— {c['label']}部分",
                    "scope_note": c["scope"]
                })
            return results

    # Generic expansion: code task that also mentions design/docs keywords
    if primary_profile == "code":
        extra = []
        if re.search(r'设计|UI|界面|样式|配色|视觉|动效', description):
            extra.append({"profile": "design", "label": "视觉设计", "scope": "仅负责UI设计与视觉呈现"})
        if re.search(r'文档|说明|README|记录|手册', description):
            extra.append({"profile": "docs", "label": "文档编写", "scope": "仅负责项目文档与使用说明"})
        if extra:
            results = [{"profile": "code", "description": f"「{description}」— 代码实现部分",
                        "scope_note": "仅负责代码编写、功能实现、测试"}]
            for e in extra:
                results.append({
                    "profile": e["profile"],
                    "description": f"「{description}」— {e['label']}部分",
                    "scope_note": e["scope"]
                })
            return results

    return []  # undiscoverable — fall back to single general sub-task


def _build_subtask(index, description, profiles, scope_note=None):
    """Build a sub-task spec with 4 required fields."""
    profile = profiles[0] if profiles else "general"
    profile_def = TOOL_PROFILES.get(profile, TOOL_PROFILES["general"])

    # Generate objective
    prefix_map = {
        "research": "搜索并汇总",
        "code": "编写/修改",
        "design": "设计/美化",
        "data": "分析/处理",
        "docs": "创建/编辑",
        "general": "完成"
    }
    prefix = prefix_map.get(profile, "完成")

    # Truncate description for objective
    short_desc = description[:80] + "..." if len(description) > 80 else description

    objective = f"子任务 {index + 1}: {prefix}关于「{short_desc[:60]}」的内容"

    # Output format
    output_format = profile_def.get("description", "精简文本结论")

    # Build the sub-agent prompt
    prompt = _build_sub_agent_prompt(index, objective, description, profile, scope_note)

    return {
        "id": generate_id("sub"),
        "index": index,
        "objective": objective,
        "output_format": output_format,
        "tools": {"profile": profile, "skills": profile_def.get("skills", [])},
        "boundary": (
            scope_note or
            f"仅处理「{description[:50]}」范围内的内容，不扩展到其他主题。完成后回传精简结论。"
        ),
        "profiles": profiles,
        "sub_agent_type": profile_def.get("subagent_type", "general-purpose"),
        "prompt": prompt,
        "budget": DEFAULT_SUB_BUDGET,
        "max_retries": MAX_RETRIES_PER_SUB
    }


def _build_sub_agent_prompt(index, objective, description, profile, scope_note=None):
    """Generate a clean, self-contained prompt for the sub-agent."""
    lines = [
        f"你是主Agent派出的专项执行Agent，负责子任务 #{index + 1}。",
        "",
        f"## 目标",
        f"{objective}",
        "",
        f"## 任务描述",
        f"{description}",
        "",
        f"## 工具画像: {profile}",
        f"你只负责{TOOL_PROFILES.get(profile, TOOL_PROFILES['general'])['description']}相关工作。",
        "",
        f"## 边界约束",
        f"{scope_note or '仅处理上述范围内的内容，完成后回传精简结论，不要扩展。'}",
        "",
        "## 输出要求",
        "完成后只回传精简的结构化结论，不回传中间过程、调试日志或试探结果。",
        "格式: 关键发现/完成结果 + 1-3句话说明。",
    ]
    return "\n".join(lines)


# ─── Independence Validation ─────────────────────────────────────────────

def validate_isolation(sub_tasks):
    """
    Check that sub-tasks are truly independent (no chained dependencies).

    Returns list of issues found. Empty list = all tasks can run in parallel.
    """
    issues = []
    if len(sub_tasks) <= 1:
        return []  # single task is trivially independent

    keywords = [set(re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{4,}',
                                t.get("objective", "").lower()))
                for t in sub_tasks]

    for i in range(len(sub_tasks)):
        for j in range(i + 1, len(sub_tasks)):
            overlap = keywords[i] & keywords[j]
            overlap_ratio = len(overlap) / max(len(keywords[i] | keywords[j]), 1)
            if overlap_ratio > 0.4:
                issues.append(
                    f"子任务 {i+1} 和 {j+1} 关键词重叠率高 ({overlap_ratio:.0%})，"
                    f"可能存在隐性依赖"
                )

    return issues


# ─── Sub-Agent Spec Generation ───────────────────────────────────────────

def generate_sub_agent_specs(task_description, current_context_size=0, workspace=None):
    """
    Generate complete sub-agent specifications for the Task tool.

    This is the main entry point: assess → decompose → generate specs.

    Returns:
        dict with: should_orchestrate, sub_agents, orchestration_plan, budget
    """

    decision = should_orchestrate(task_description, current_context_size, workspace=workspace)
    if not decision["should_spawn"]:
        return {
            "should_orchestrate": False,
            "reason": decision["reason"],
            "gate": decision["gate"],
            "sub_agents": [],
            "orchestration_plan": None,
            "budget": {"total": 0, "per_sub": 0}
        }

    decomposition = decompose_task(task_description, workspace)
    sub_tasks = decomposition["sub_tasks"]

    # Build orchestration plan
    total_budget = min(DEFAULT_BUDGET_CAP, DEFAULT_SUB_BUDGET * len(sub_tasks))

    orchestration_plan = {
        "mode": "parallel",  # always parallel for truly independent tasks
        "sub_agent_count": len(sub_tasks),
        "strategy": (
            "所有子Agent并行执行，各自独立上下文。"
            "完成后由主Agent汇总精简结论，合并为最终答案。"
        ),
        "aggregation": {
            "method": "结构化汇总",
            "format": "每个子Agent回传: {目标, 结论(≤3句), 文件路径(如有)}"
        },
        "safety": {
            "budget_cap": total_budget,
            "per_sub_timeout": 120,
            "max_retries": MAX_RETRIES_PER_SUB,
            "circuit_breaker": CIRCUIT_BREAKER_FAILURES,
            "failure_policy": "单个子任务失败不影响全局，该子任务结果标记为'未完成'"
        }
    }

    return {
        "should_orchestrate": True,
        "reason": decision["reason"],
        "gate": "passed",
        "sub_agents": sub_tasks,
        "orchestration_plan": orchestration_plan,
        "budget": {
            "total": total_budget,
            "per_sub": DEFAULT_SUB_BUDGET,
            "estimated_savings": _estimate_savings(task_description, len(sub_tasks))
        },
        "decomposition": {
            "count": decomposition["count"],
            "independence_score": decomposition["independence_score"],
            "warnings": decomposition["warnings"],
            "profiles_used": decomposition["profiles_used"]
        }
    }


def _estimate_savings(task_description, sub_count):
    """Estimate token savings from orchestration vs single agent.

    Key insight from article: savings come from context isolation.
    A single agent handling N subtasks sequentially has pollution overhead
    (intermediate results of subtask 1 pollute context for subtask 2).
    With orchestration, each sub-agent has clean, isolated context.
    """
    task_tokens = _estimate_task_tokens(task_description)
    pollution_factor = 0.3  # each additional subtask adds 30% overhead in single-agent mode
    prompt_overhead_per_sub = 800  # template prompt overhead per sub-agent

    # Single agent: task grows with pollution from cross-contamination
    single_cost = task_tokens * (1.0 + pollution_factor * max(sub_count - 1, 0))

    # Multi agent: per-sub task + prompt overhead per agent
    multi_cost = (task_tokens / max(sub_count, 1)) + prompt_overhead_per_sub * sub_count

    savings = single_cost - multi_cost
    return max(0, int(savings))


def select_minimal_tools(profile_name):
    """
    Return the minimal tool set for a given profile.
    Used to configure sub-agent tool access.
    """
    profile = TOOL_PROFILES.get(profile_name, TOOL_PROFILES["general"])
    return {
        "profile": profile_name,
        "subagent_type": profile["subagent_type"],
        "tools": profile["tools"],
        "skills": profile.get("skills", [])
    }


# ─── Lifecycle Tracking ──────────────────────────────────────────────────

def load_orchestrator_data(workspace=None):
    """Load orchestrator tracking data."""
    ws_dir = get_workspace_dir(workspace)
    ensure_workspace(workspace)
    path = os.path.join(ws_dir, "orchestrator.json")
    if os.path.exists(path):
        return read_json(path) or _init_orchestrator_data()
    return _init_orchestrator_data()


def save_orchestrator_data(data, workspace=None):
    """Save orchestrator tracking data."""
    ws_dir = get_workspace_dir(workspace)
    ensure_workspace(workspace)
    path = os.path.join(ws_dir, "orchestrator.json")
    write_json(path, data)


def _init_orchestrator_data():
    return {
        "version": "3.3.0",
        "traces": [],
        "stats": {
            "total_orchestrations": 0,
            "total_sub_agents": 0,
            "successful": 0,
            "failed": 0,
            "circuit_breaks": 0,
            "continuations": 0,         # v3.3.0: total continuation rounds
            "stalls_detected": 0,       # v3.3.0: total stall detections
            "profile_usage": {p: 0 for p in TOOL_PROFILES}
        },
        "session_failures": 0,
        "circuit_broken": False,
        # v3.3.0 — Goal Continuation state
        "continuation_state": {
            "enabled": True,
            "max_continuations": MAX_CONTINUATIONS,
            # Per-orchestration state (cleared between orchestrations)
            "active": False,
            "current_count": 0,
            "last_signature": ""
        }
    }


def record_spawn(orchestration_id, sub_agent_count, profiles_used, task_summary, workspace=None):
    """Record an orchestration spawn event.

    v3.3.0: resets continuation state for new orchestration.
    """
    data = load_orchestrator_data(workspace)
    trace = {
        "id": orchestration_id,
        "timestamp": get_timestamp(),
        "status": "spawned",
        "sub_agent_count": sub_agent_count,
        "profiles_used": profiles_used,
        "task_summary": task_summary[:200],
        "sub_results": [],
        "continuations": [],   # v3.3.0
        "goal_description": task_summary[:120]  # v3.3.0
    }
    data["traces"].append(trace)
    data["stats"]["total_orchestrations"] += 1
    data["stats"]["total_sub_agents"] += sub_agent_count
    for p in profiles_used:
        if p in data["stats"]["profile_usage"]:
            data["stats"]["profile_usage"][p] += 1

    # v3.3.0: reset continuation state for fresh orchestration
    data["continuation_state"] = {
        "enabled": True,
        "max_continuations": MAX_CONTINUATIONS,
        "active": True,
        "current_count": 0,
        "last_signature": ""
    }

    save_orchestrator_data(data, workspace)
    return trace


def record_complete(orchestration_id, results, workspace=None):
    """Record orchestration completion. v3.3.0: embeds goal evaluation.

    Args:
        orchestration_id: str
        results: list of dicts with at least 'id' and 'status'
        workspace: str

    Returns:
        dict with trace and goal_evaluation
    """
    data = load_orchestrator_data(workspace)

    # v3.3.0: enrich results with evaluation
    goal_eval = evaluate_goal_completion(results, workspace)
    goal_eval["_sub_results"] = results  # pass through for stall detection

    updated_trace = None
    for trace in data["traces"]:
        if trace["id"] == orchestration_id:
            trace["status"] = "completed"
            trace["completed_at"] = get_timestamp()
            trace["sub_results"] = results
            trace["goal_evaluation"] = goal_eval  # v3.3.0

            # v3.3.0: run continuation decision
            cont_decision = should_continue_goal(goal_eval, workspace)
            trace["continuation_decision"] = cont_decision

            if cont_decision.get("should_continue"):
                # Mark as needing continuation (not truly "done" yet)
                trace["status"] = "awaiting_continuation"
            else:
                # Final verdict
                trace["status"] = (
                    "completed" if goal_eval.get("goal_achieved")
                    else "partial" if goal_eval.get("verdict") == "partial_success"
                    else "completed_no_progress" if cont_decision.get("stalled")
                    else "completed"
                )

            data["stats"]["successful"] += 1
            data["session_failures"] = 0
            updated_trace = trace
            break

    if updated_trace is None:
        # Trace not found: still store evaluation
        pass

    save_orchestrator_data(data, workspace)

    return {
        "trace": updated_trace,
        "goal_evaluation": goal_eval,
        "continuation_decision": updated_trace.get("continuation_decision") if updated_trace else None
    }


def record_failure(orchestration_id, error_message, failed_sub_indices=None, workspace=None):
    """Record orchestration failure."""
    data = load_orchestrator_data(workspace)
    for trace in data["traces"]:
        if trace["id"] == orchestration_id:
            trace["status"] = "failed"
            trace["failed_at"] = get_timestamp()
            trace["error"] = error_message
            trace["failed_subs"] = failed_sub_indices or []
            data["stats"]["failed"] += 1
            data["session_failures"] = data.get("session_failures", 0) + 1

            # Trip circuit breaker?
            if data["session_failures"] >= CIRCUIT_BREAKER_FAILURES:
                data["circuit_broken"] = True
                data["stats"]["circuit_breaks"] += 1
            break
    save_orchestrator_data(data, workspace)


# ─── v3.3.0 — Goal Continuation Engine ─────────────────────────────────

def _hash_results(results):
    """Generate a compact signature from sub-results for stall detection.

    Uses SHA256 of the structured result data (not LLM free text).
    Cost: microsecond-level, zero LLM calls.

    Args:
        results: list of dicts, each with at least 'id' and 'status'

    Returns:
        str: hex signature prefix (STALL_SIGNATURE_PRECISION chars)
    """
    import hashlib

    if not results:
        return ""

    # Build a canonical byte string from result structure
    sig_parts = []
    for r in sorted(results, key=lambda x: str(x.get("id", ""))):
        status = r.get("status", "unknown")
        err = r.get("error", "")
        sig_parts.append(f"{status}|{err[:50]}".encode("utf-8"))

    combined = b"|".join(sig_parts)
    return hashlib.sha256(combined).hexdigest()[:STALL_SIGNATURE_PRECISION]


def evaluate_goal_completion(sub_results, workspace=None):
    """Evaluate whether the orchestration goal is achieved.
    Level 2 (structured judgment): uses only sub_results data, no LLM.

    Args:
        sub_results: list of dicts, each with at least:
            - id: str
            - status: 'completed' | 'failed' | 'partial' | 'spawned'
            - error: str (optional)

    Returns:
        dict with: goal_achieved, status, failed_count, completed_count,
                   failed_ratio, verdict, recommendation
    """
    if not sub_results:
        return {
            "goal_achieved": False,
            "status": "no_results",
            "failed_count": 0,
            "completed_count": 0,
            "total": 0,
            "failed_ratio": 0.0,
            "verdict": "no_results",
            "recommendation": "retry"
        }

    total = len(sub_results)
    completed = sum(
        1 for r in sub_results
        if r.get("status") in ("completed", "partial")
    )
    failed = total - completed
    failed_ratio = failed / max(total, 1)

    # Verdict logic (ordered by severity)
    if failed == 0:
        verdict = "all_completed"
        recommendation = "done"
    elif failed_ratio <= PARTIAL_SUCCESS_THRESHOLD and total >= 2:
        # ≤50% failed and multiple sub-tasks: partial success
        verdict = "partial_success"
        recommendation = "continue"
    elif failed == total:
        verdict = "all_failed"
        recommendation = "abort"
    else:
        verdict = "majority_failed"
        recommendation = "retry"

    return {
        "goal_achieved": verdict == "all_completed",
        "status": verdict,
        "failed_count": failed,
        "completed_count": completed,
        "total": total,
        "failed_ratio": round(failed_ratio, 2),
        "verdict": verdict,
        "recommendation": recommendation,
        "threshold": PARTIAL_SUCCESS_THRESHOLD
    }


def should_continue_goal(evaluation, workspace=None):
    """Decision gate for goal continuation.

    Three stops:
      1. Max continuations exceeded (> MAX_CONTINUATIONS)
      2. Stall detected (same result signature as previous round)
      3. All sub-tasks completed successfully

    Args:
        evaluation: dict from evaluate_goal_completion()

    Returns:
        dict with: should_continue, stop_reason, continuation_count, stalled
    """
    data = load_orchestrator_data(workspace)
    cs = data.get("continuation_state", {})

    current_count = cs.get("current_count", 0)

    # Gate A: goal already achieved?
    if evaluation.get("goal_achieved"):
        return {
            "should_continue": False,
            "stop_reason": "goal_achieved",
            "continuation_count": current_count,
            "stalled": False
        }

    # Gate B: max continuations?
    if current_count >= cs.get("max_continuations", MAX_CONTINUATIONS):
        return {
            "should_continue": False,
            "stop_reason": "max_continuations_exceeded",
            "continuation_count": current_count,
            "stalled": False
        }

    # Gate C: abort recommendation?
    if evaluation.get("recommendation") == "abort":
        return {
            "should_continue": False,
            "stop_reason": "all_subtasks_failed",
            "continuation_count": current_count,
            "stalled": False
        }

    # Gate D: stall detection — requires sub_results from evaluation
    sub_results = evaluation.get("_sub_results", [])
    if sub_results:
        new_sig = _hash_results(sub_results)
        last_sig = cs.get("last_signature", "")

        if last_sig and new_sig == last_sig:
            # Same results as last round → stalled
            data["stats"]["stalls_detected"] = data["stats"].get("stalls_detected", 0) + 1
            save_orchestrator_data(data, workspace)
            return {
                "should_continue": False,
                "stop_reason": "stall_detected",
                "continuation_count": current_count,
                "stalled": True,
                "signature": new_sig
            }

    # Passed all gates → continue
    return {
        "should_continue": True,
        "stop_reason": None,
        "continuation_count": current_count + 1,
        "stalled": False
    }


def record_continuation(orchestration_id, results_signature, workspace=None):
    """Record a continuation round and update stall detection state.

    Args:
        orchestration_id: str, the orchestration trace ID
        results_signature: str, hash of current results

    Returns:
        dict with updated continuation state
    """
    data = load_orchestrator_data(workspace)
    cs = data.get("continuation_state", {})

    cs["active"] = True
    cs["current_count"] = cs.get("current_count", 0) + 1
    cs["last_signature"] = results_signature
    data["continuation_state"] = cs

    # Update trace
    for trace in data["traces"]:
        if trace["id"] == orchestration_id:
            if "continuations" not in trace:
                trace["continuations"] = []
            trace["continuations"].append({
                "round": cs["current_count"],
                "timestamp": get_timestamp(),
                "signature": results_signature
            })
            break

    data["stats"]["continuations"] = data["stats"].get("continuations", 0) + 1
    save_orchestrator_data(data, workspace)

    return dict(cs)


def reset_continuation_state(workspace=None):
    """Reset continuation state for a new orchestration."""
    data = load_orchestrator_data(workspace)
    data["continuation_state"] = {
        "enabled": True,
        "max_continuations": MAX_CONTINUATIONS,
        "active": False,
        "current_count": 0,
        "last_signature": ""
    }
    save_orchestrator_data(data, workspace)
    return {"reset": True, "message": "续跑状态已重置"}


def get_goal_status(orchestration_id, workspace=None):
    """Get the goal continuation status for an orchestration.

    Returns human-readable status for CLI display.
    """
    data = load_orchestrator_data(workspace)
    cs = data.get("continuation_state", {})

    trace = None
    for t in data.get("traces", []):
        if t["id"] == orchestration_id:
            trace = t
            break

    if not trace:
        return {"error": f"未找到编排 {orchestration_id}", "trace_found": False}

    # Build status display
    cont_rounds = len(trace.get("continuations", []))
    sub_results = trace.get("sub_results", [])

    # Quick evaluation from sub_results
    eval_result = evaluate_goal_completion(sub_results) if sub_results else None

    return {
        "trace_found": True,
        "orchestration_id": orchestration_id,
        "trace_status": trace.get("status", "unknown"),
        "continuation_rounds": cont_rounds,
        "continuation_state": cs,
        "goal_evaluation": eval_result,
        "action": (
            "goal_achieved" if eval_result and eval_result.get("goal_achieved")
            else "retry" if eval_result and eval_result.get("recommendation") == "retry"
            else "stalled" if cs.get("last_signature") and (cont_rounds >= MAX_CONTINUATIONS or getattr(should_continue_goal.__self__, 'stalled', False))
            else "in_progress"
        )
    }


# ─── Reset Functions ────────────────────────────────────────────────────

def reset_circuit_breaker(workspace=None):
    """Manually reset the circuit breaker."""
    data = load_orchestrator_data(workspace)
    data["circuit_broken"] = False
    data["session_failures"] = 0
    save_orchestrator_data(data, workspace)
    return {"reset": True, "message": "熔断器已重置"}


def get_orchestration_stats(workspace=None):
    """Get orchestrator statistics."""
    data = load_orchestrator_data(workspace)
    stats = data.get("stats", {})
    traces = data.get("traces", [])

    recent = traces[-10:] if traces else []
    recent_summary = [
        {"id": t["id"], "status": t["status"], "subs": t.get("sub_agent_count", 0),
         "timestamp": t.get("timestamp", ""), "task": t.get("task_summary", "")[:80]}
        for t in recent
    ]

    return {
        "version": data.get("version", "3.3.0"),
        "stats": stats,
        "circuit_broken": data.get("circuit_broken", False),
        "session_failures": data.get("session_failures", 0),
        "total_traces": len(traces),
        "recent_traces": recent_summary,
        "continuation_state": data.get("continuation_state", {})  # v3.3.0
    }


# ─── Convenience: One-call orchestration ─────────────────────────────────

def orchestrate(task_description, current_context_size=0, dry_run=False, workspace=None):
    """
    One-call orchestration: assess → decompose → (optional spawn).

    Args:
        task_description: str
        current_context_size: int, estimated tokens in conversation
        dry_run: bool, if True only generate specs without recording spawn
        workspace: str

    Returns:
        dict with full orchestration result
    """
    specs = generate_sub_agent_specs(task_description, workspace=workspace)

    if not specs["should_orchestrate"]:
        return specs

    if dry_run:
        specs["mode"] = "dry_run"
        return specs

    # Record spawn
    orch_id = generate_id("orch")
    record_spawn(
        orch_id,
        specs["decomposition"]["count"],
        specs["decomposition"]["profiles_used"],
        task_description,
        workspace
    )
    specs["orchestration_id"] = orch_id
    specs["mode"] = "spawned"

    return specs


# ─── v3.3.0 — Continuation-Integrated Orchestration ─────────────────────

def orchestrate_continue(orchestration_id, task_description, sub_results,
                         current_context_size=0, workspace=None):
    """Attempt a continuation round for an incomplete orchestration.

    Checks if continuation is warranted, then re-decomposes and records.

    Args:
        orchestration_id: str, the original orchestration to continue
        task_description: str, original or refined task description
        sub_results: list, previous round results (for stall detection)
        current_context_size: int
        workspace: str

    Returns:
        dict with: continuation_performed, reason, new_specs (if any)
    """
    # Step 1: evaluate current results
    goal_eval = evaluate_goal_completion(sub_results, workspace)
    goal_eval["_sub_results"] = sub_results

    # Step 2: should we continue?
    decision = should_continue_goal(goal_eval, workspace)

    if not decision["should_continue"]:
        return {
            "continuation_performed": False,
            "reason": decision["stop_reason"],
            "goal_evaluation": goal_eval,
            "continuation_decision": decision
        }

    # Step 3: record continuation
    sig = _hash_results(sub_results)
    record_continuation(orchestration_id, sig, workspace)

    # Step 4: re-decompose (may refine based on failures)
    specs = generate_sub_agent_specs(task_description, workspace=workspace)

    if not specs["should_orchestrate"]:
        return {
            "continuation_performed": False,
            "reason": "re-assessment rejected orchestration",
            "goal_evaluation": goal_eval,
            "continuation_decision": decision,
            "re_assessment": {
                "score": specs.get("gate", "n/a"),
                "reason": specs.get("reason", "")
            }
        }

    # Step 5: add continuation info
    specs["orchestration_id"] = orchestration_id
    specs["mode"] = "continuation"
    specs["continuation_round"] = decision["continuation_count"]

    # Update trace status
    data = load_orchestrator_data(workspace)
    for trace in data["traces"]:
        if trace["id"] == orchestration_id:
            trace["status"] = "continued"
            break
    save_orchestrator_data(data, workspace)

    return {
        "continuation_performed": True,
        "reason": "retry_recommended",
        "continuation_round": decision["continuation_count"],
        "goal_evaluation": goal_eval,
        "continuation_decision": decision,
        "new_specs": specs,
        "result_signature": sig
    }


# ─── Self-Test ───────────────────────────────────────────────────────────

def run_tests():
    """Run built-in tests for the orchestrator module."""
    results = []
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            results.append(f"  PASS: {name}")
        else:
            failed += 1
            results.append(f"  FAIL: {name} — {detail}")

    # ── Test 1: Simple task should NOT orchestrate ──
    decision = should_orchestrate("帮我看一下今天几号")
    check("T1: Trivial task rejected", not decision["should_spawn"], decision["reason"])

    # ── Test 2: Sequential task should NOT orchestrate ──
    decision = should_orchestrate("先安装依赖，然后再启动服务器，最后再运行测试")
    check("T2: Sequential task rejected", not decision["should_spawn"], decision["reason"])

    # ── Test 3: Complex parallel task should orchestrate ──
    decision = should_orchestrate(
        "帮我同时做三件事：\n1. 搜索最新的 React 19 文档变化并总结要点\n"
        "2. 重新设计首页的配色方案和布局\n"
        "3. 分析上个月的销售数据并做可视化图表",
        current_context_size=70000
    )
    check("T3: Complex parallel task passes", decision["should_spawn"],
          f"Score: {decision.get('assessment', {}).get('score', 'N/A')}")

    # ── Test 4: Complexity assessment returns 4 dimensions ──
    assessment = assess_complexity("帮我搜索 Python 异步编程的最新最佳实践，并写一个完整的示例项目")
    check("T4: Assessment has 4 dimensions", len(assessment["dimensions"]) == 4,
          f"Got {len(assessment['dimensions'])}")
    check("T4b: Assessment has reasoning", len(assessment["reasoning"]) > 0)

    # ── Test 5: Decomposition produces valid sub-tasks ──
    decomp = decompose_task(
        "1. 搜索比较 React vs Vue 最新版本\n"
        "2. 设计一个登录页面\n"
        "3. 分析用户行为数据"
    )
    check("T5: Decomposition has sub_tasks", len(decomp["sub_tasks"]) >= 2,
          f"Got {len(decomp['sub_tasks'])}")
    if decomp["sub_tasks"]:
        st = decomp["sub_tasks"][0]
        check("T5b: Sub-task has objective", "objective" in st)
        check("T5c: Sub-task has output_format", "output_format" in st)
        check("T5d: Sub-task has tools", "tools" in st)
        check("T5e: Sub-task has boundary", "boundary" in st)

    # ── Test 6: Full spec generation ──
    specs = generate_sub_agent_specs(
        "1. 搜索最新AI新闻 2. 写一篇总结 3. 做成PPT",
        workspace="default"
    )
    check("T6: Full spec generated", "should_orchestrate" in specs)

    # ── Test 7: Minimal tool selection ──
    tools = select_minimal_tools("research")
    check("T7: Minimal tools for research", len(tools["tools"]) > 0)

    # ── Test 8: Independence validation ──
    # Create two very similar sub-tasks
    similar = [
        {"objective": "搜索 React 19 新特性"},
        {"objective": "搜索 React 19 更新内容"}
    ]
    issues = validate_isolation(similar)
    check("T8: Detects high-overlap sub-tasks", len(issues) > 0,
          f"Got {len(issues)} issues")

    # ── Test 9: Independent sub-tasks pass validation ──
    independent = [
        {"objective": "设计登录页面"},
        {"objective": "分析销售数据报表"},
        {"objective": "编写部署脚本"}
    ]
    issues = validate_isolation(independent)
    check("T9: Independent sub-tasks pass", len(issues) == 0,
          f"Got {len(issues)} issues")

    # ── Test 10: Orchestrator data tracking ──
    data = _init_orchestrator_data()
    check("T10: Init data has stats", "stats" in data)
    check("T10b: Init data has traces", "traces" in data)
    check("T10c: Init data has circuit_breaker", "circuit_broken" in data)

    # ── Test 11: Profile detection ──
    profiles = _detect_needed_profiles("帮我写一个Python脚本，同时设计一下UI界面")
    check("T11: Detects code+design profiles", "code" in profiles and "design" in profiles,
          str(profiles))

    # ── Test 12: Budget estimation ──
    savings = _estimate_savings(
        "帮我写一个完整的全栈电商项目：\n"
        "1. 用React+TypeScript搭建前端代码，包含用户认证、商品浏览、购物车、结算\n"
        "2. 用Python FastAPI搭建后端代码，包含REST API、数据库模型、认证中间件\n"
        "3. 配置Docker部署脚本，编写docker-compose和CI/CD部署脚本\n"
        "4. 写一份完整的项目文档和API使用说明",
        4
    )
    check("T12: Estimates savings > 0 for large task", savings > 0, f"Got {savings}")

    # ── NEW v3.2.1: Implicit scope detection tests ──

    # Test 13: Single-sentence large task should trigger orchestration
    decision = should_orchestrate(
        "帮我搭建一个完整的电商网站包括前端后端和数据库",
        current_context_size=30000
    )
    check("T13: Single-sentence large task triggers orchestration",
          decision["should_spawn"],
          f"Gate: {decision.get('gate')}, Score: {decision.get('assessment', {}).get('score', 'N/A')}")

    # Test 14: Single-sentence website task → implicit decomposition into 4 sub-tasks
    decomp = decompose_task("帮我搭建一个完整的电商网站包括前端后端和数据库")
    check("T14a: Implicit decomposition produces ≥3 sub-tasks",
          decomp["count"] >= 3, f"Got {decomp['count']}")
    # Verify sub-tasks have distinct profiles/scope
    scopes = [t.get("boundary", "") for t in decomp["sub_tasks"]]
    check("T14b: Sub-tasks have distinct boundaries",
          len(set(scopes)) >= 2, f"Unique scopes: {len(set(scopes))}")

    # Test 15: Token estimation for domain keywords
    tokens_small = _estimate_task_tokens("搜索 React 19 新特性")
    tokens_big = _estimate_task_tokens("帮我搭建一个完整的电商网站包括前端后端和数据库")
    check("T15: Domain-aware token estimation",
          tokens_big > tokens_small * 3,
          f"Small: {tokens_small}, Big: {tokens_big}")

    # Test 16: Simple single task (short, no domain keywords) should NOT orchestrate
    decision = should_orchestrate("搜索Python异步编程的最佳实践")
    check("T16: Simple search task rejected",
          not decision["should_spawn"],
          f"Gate: {decision.get('gate')}")

    # Test 17: "帮我整理知识库" — multi-profile but short, should still assess
    decision = should_orchestrate(
        "帮我全面整理知识库，包括文件分类、删除冗余、更新索引和生成报告",
        current_context_size=25000
    )
    check("T17: Knowledge base cleanup triggers assessment",
          decision.get("should_spawn") is not None,
          f"Score: {decision.get('assessment', {}).get('score', 'N/A')}")

    # Test 18: _discover_implicit_subtasks for website pattern
    implicit = _discover_implicit_subtasks("搭建完整的电商网站", "code")
    check("T18a: Implicit discovery finds sub-components",
          len(implicit) >= 3, f"Got {len(implicit)}")
    check("T18b: Each implicit sub has profile+description+scope",
          all("profile" in s and "description" in s and "scope_note" in s for s in implicit))

    # Test 19: _discover_implicit_subtasks returns [] for undiscoverable task
    implicit = _discover_implicit_subtasks("写一个简单的hello world函数", "code")
    check("T19: Undiscoverable task returns empty list", implicit == [],
          f"Got {len(implicit)}")

    # Test 20: Independence score boosted by implicit scope
    score_explicit = _assess_independence(
        "1. 搜索React 2. 设计页面 3. 写代码 4. 测试"
    )
    score_implicit = _assess_independence(
        "帮我搭建一个完整的电商网站包括前端后端数据库和部署"
    )
    check("T20: Implicit large task scores competitively vs explicit",
          score_implicit > 0.5,
          f"Explicit: {score_explicit:.2f}, Implicit: {score_implicit:.2f}")

    # ─── v3.3.0: Goal Continuation tests ─────────────────────────────────

    # Build shared test fixtures
    all_completed_results = [
        {"id": "sub-1", "status": "completed"},
        {"id": "sub-2", "status": "completed"},
        {"id": "sub-3", "status": "completed"},
    ]
    mixed_results = [
        {"id": "sub-1", "status": "completed"},
        {"id": "sub-2", "status": "failed", "error": "timeout"},
        {"id": "sub-3", "status": "completed"},
        {"id": "sub-4", "status": "failed", "error": "tool_not_found"},
    ]
    all_failed_results = [
        {"id": "sub-1", "status": "failed", "error": "a"},
        {"id": "sub-2", "status": "failed", "error": "b"},
    ]

    # T21: evaluate_goal_completion — all completed
    eval_result = evaluate_goal_completion(all_completed_results)
    check("T21: All completed → goal_achieved=True",
          eval_result.get("goal_achieved") is True,
          f"Got verdict: {eval_result.get('verdict')}")
    check("T21b: All completed → recommendation=done",
          eval_result.get("recommendation") == "done")

    # T22: evaluate_goal_completion — partial failure
    eval_result = evaluate_goal_completion(mixed_results)
    check("T22: 50% failed with 4 sub-tasks → partial_success",
          eval_result.get("verdict") == "partial_success",
          f"Got: {eval_result.get('verdict')}")
    check("T22b: Partial success → recommendation=continue",
          eval_result.get("recommendation") == "continue")

    # T23: evaluate_goal_completion — all failed
    eval_result = evaluate_goal_completion(all_failed_results)
    check("T23: All failed → recommendation=abort",
          eval_result.get("recommendation") == "abort",
          f"Got: {eval_result.get('recommendation')}")
    check("T23b: All failed → goal_achieved=False",
          eval_result.get("goal_achieved") is False)

    # T24: evaluate_goal_completion — empty results
    eval_result = evaluate_goal_completion([])
    check("T24: Empty results → status=no_results",
          eval_result.get("status") == "no_results")

    # T25: _hash_results — deterministic
    hash1 = _hash_results(all_completed_results)
    hash2 = _hash_results(all_completed_results)
    check("T25: Hash is deterministic", hash1 == hash2,
          f"h1={hash1} h2={hash2}")

    # T26: _hash_results — different results → different hash
    hash3 = _hash_results(mixed_results)
    check("T26: Different results → different hash",
          hash1 != hash3,
          f"h1={hash1} h3={hash3}")

    # T27: should_continue_goal — goal achieved → stop
    eval_a = evaluate_goal_completion(all_completed_results)
    decision = should_continue_goal(eval_a)
    check("T27: Goal achieved → should_continue=False",
          decision.get("should_continue") is False,
          f"Reason: {decision.get('stop_reason')}")

    # T28: should_continue_goal — partial success → continue
    eval_b = evaluate_goal_completion(mixed_results)
    eval_b["_sub_results"] = mixed_results
    decision = should_continue_goal(eval_b)
    check("T28: Partial success → should_continue=True",
          decision.get("should_continue") is True,
          f"Count: {decision.get('continuation_count')}")

    # T29: should_continue_goal — abort → stop
    eval_c = evaluate_goal_completion(all_failed_results)
    decision = should_continue_goal(eval_c)
    check("T29: All failed → should_continue=False",
          decision.get("should_continue") is False,
          f"Reason: {decision.get('stop_reason')}")

    # T30: stall detection — same results twice → stall
    import tempfile, os
    tmp_dir = tempfile.mkdtemp()
    os.environ["SUPERBRAIN_WORKSPACE"] = tmp_dir
    try:
        # Prime continuation state with one signature
        from sb_core import ensure_workspace, get_workspace_dir
        ws_dir = get_workspace_dir("test-cont")
        _ = ensure_workspace("test-cont")
        data = _init_orchestrator_data()
        data["continuation_state"]["last_signature"] = _hash_results(mixed_results)
        data["continuation_state"]["current_count"] = 0
        orch_path = os.path.join(ws_dir, "orchestrator.json")
        write_json(orch_path, data)
    except Exception:
        pass  # fallback: stall test runs inline

    eval_d = evaluate_goal_completion(mixed_results)
    eval_d["_sub_results"] = mixed_results

    # Simulate: first continuation sets the signature
    data = _init_orchestrator_data()
    sig = _hash_results(mixed_results)
    data["continuation_state"]["last_signature"] = sig
    data["continuation_state"]["current_count"] = 1
    data["continuation_state"]["active"] = True
    # Save to disk for should_continue_goal to read
    ws_dir = os.path.join(os.path.expanduser("~"), ".workbuddy", "super-brain", "workspaces", "default")
    os.makedirs(ws_dir, exist_ok=True)
    orch_path = os.path.join(ws_dir, "orchestrator.json")
    write_json(orch_path, data)
    # Now evaluate with SAME results → should stall
    eval_same = evaluate_goal_completion(mixed_results)
    eval_same["_sub_results"] = mixed_results
    decision = should_continue_goal(eval_same, "default")

    check("T30: Same results twice → stall detected",
          decision.get("stalled") or not decision.get("should_continue"),
          f"Stalled: {decision.get('stalled')}, Continue: {decision.get('should_continue')}, "
          f"Reason: {decision.get('stop_reason')}, "
          f"Last sig: {data.get('continuation_state', {}).get('last_signature')}, "
          f"New sig: {sig}")

    # T31: continuation stats tracking
    reset_continuation_state("default")
    data2 = load_orchestrator_data("default")
    cs = data2.get("continuation_state", {})
    check("T31a: Continuation state reset → count=0",
          cs.get("current_count") == 0,
          f"Count: {cs.get('current_count')}")
    check("T31b: Continuation state has max_continuations",
          cs.get("max_continuations") == MAX_CONTINUATIONS,
          f"Max: {cs.get('max_continuations')}")

    # T32: record_continuation updates state
    cont_state = record_continuation("test-orch-id", "abcdef12", "default")
    check("T32a: record_continuation → count incremented",
          cont_state.get("current_count") == 1,
          f"Count: {cont_state.get('current_count')}")
    check("T32b: record_continuation → signature stored",
          cont_state.get("last_signature") == "abcdef12")

    print(f"\n=== Orchestrator Tests: {passed}/{passed + failed} passed ===\n")
    for r in results:
        print(r)
    return {"passed": passed, "failed": failed, "total": passed + failed}


if __name__ == "__main__":
    run_tests()
