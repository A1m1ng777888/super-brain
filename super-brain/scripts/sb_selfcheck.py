#!/usr/bin/env python3
"""
SuperBrain Self-Check System v3.4.0
====================================
v3.4.0 升级：物理层自检（文件完整性+索引可重建性+备份时效）+ 修复前自动备份
v2.1.0-base: consistency, timeliness, temporal_validity, completeness, orphans, duplicates.
Generates health reports and can auto-fix safe issues.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import json
import shutil
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone as dt_tz
from sb_core import (
    get_timestamp, read_memories, write_memories,
    read_graph, write_graph, read_meta, update_meta,
    get_health_dir, write_json, read_json, print_json, load_config,
    get_workspace_dir, ensure_dir
)
from sb_search import find_duplicates, simhash, simhash_similarity
from sb_memory import find_issues, get_stats as get_mem_stats
from sb_graph import get_stats as get_graph_stats


# ===== v3.4.0: 自动备份 =====

def _create_backup(workspace=None, reason="selfcheck_fix"):
    """修复前自动备份当前工作区数据"""
    ws_dir = get_workspace_dir(workspace)
    backup_dir = os.path.join(ws_dir, "backups")
    ensure_dir(backup_dir)

    timestamp = datetime.now(dt_tz.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"backup_{reason}_{timestamp}")
    ensure_dir(backup_path)

    files_to_backup = ["memories.json", "graph.json", "meta.json", "index.json"]
    backed_up = []
    for fname in files_to_backup:
        src = os.path.join(ws_dir, fname)
        if os.path.exists(src):
            dst = os.path.join(backup_path, fname)
            shutil.copy2(src, dst)
            backed_up.append(fname)

    # Clean old backups (keep last 5)
    existing = sorted(
        [d for d in os.listdir(backup_dir) if d.startswith("backup_")],
        reverse=True
    )
    for old in existing[5:]:
        old_path = os.path.join(backup_dir, old)
        if os.path.isdir(old_path):
            shutil.rmtree(old_path, ignore_errors=True)

    return {
        "backup_path": backup_path,
        "files": backed_up,
        "reason": reason
    }


# ===== v3.4.0: 物理层检查 =====

def check_file_integrity(workspace=None):
    """
    v3.4.0: Check physical file integrity.
    Verifies memory/graph files exist and contain valid JSON.
    """
    ws_dir = get_workspace_dir(workspace)
    required_files = {
        "memories.json": "记忆数据",
        "graph.json": "知识图谱",
        "meta.json": "元数据"
    }
    issues = []

    for fname, label in required_files.items():
        fpath = os.path.join(ws_dir, fname)
        if not os.path.exists(fpath):
            issues.append({"file": fname, "label": label, "problem": "文件不存在"})
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            issues.append({"file": fname, "label": label, "problem": f"JSON格式损坏: {e}"})
        except Exception as e:
            issues.append({"file": fname, "label": label, "problem": f"读取失败: {e}"})

    # Also check index file if exists
    idx_path = os.path.join(ws_dir, "index.json")
    if os.path.exists(idx_path):
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                idx_data = json.load(f)
            # Verify index has expected structure
            if "ternary_buckets" not in idx_data and "word_network" not in idx_data:
                issues.append({"file": "index.json", "label": "检索索引", "problem": "索引结构不完整，可能需重建"})
        except:
            issues.append({"file": "index.json", "label": "检索索引", "problem": "索引文件损坏，需重建"})

    return {
        "check": "file_integrity",
        "status": "critical" if issues else "healthy",
        "issues_found": len(issues),
        "details": issues,
        "recommendation": (
            "部分数据文件缺失或损坏，请运行 'python superbrain.py init --fix' 修复，"
            "或从备份恢复。修复前会自动备份当前状态。"
        ) if issues else "所有数据文件完整且格式正确。"
    }


def check_index_integrity(workspace=None):
    """
    v3.4.0: Check search index rebuildability.
    Verifies that ternary hash index and inverted index can be rebuilt from memory data.
    """
    from sb_search import ternary_hash, build_word_network_from_memories, get_word_network
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]

    issues = []
    rebuild_estimate = 0

    for m in active:
        content = m.get("content", "")
        if content:
            try:
                h = ternary_hash(content)
                rebuild_estimate += 1
            except Exception:
                issues.append({"id": m["id"], "problem": f"无法计算三进制哈希: {content[:40]}..."})

    # Check word network
    wn = get_word_network(workspace)
    wn_tokens = len(wn.tokens) if wn and hasattr(wn, 'tokens') else 0

    return {
        "check": "index_integrity",
        "status": "warning" if issues else "healthy",
        "issues_found": len(issues),
        "details": {
            "rebuildable_count": rebuild_estimate,
            "total_active": len(active),
            "word_network_tokens": wn_tokens,
            "failed_items": issues[:10]
        },
        "recommendation": (
            f"索引可重建：{rebuild_estimate}/{len(active)} 条。"
            f"运行 'python superbrain.py longterm index' 可重建索引。"
        )
    }


def check_backup_freshness(workspace=None):
    """
    v3.4.0: Check backup freshness.
    Warns if the last backup is older than 30 days or if no backups exist.
    """
    ws_dir = get_workspace_dir(workspace)
    backup_dir = os.path.join(ws_dir, "backups")
    ensure_dir(backup_dir)

    backups = sorted(
        [d for d in os.listdir(backup_dir) if d.startswith("backup_") and os.path.isdir(os.path.join(backup_dir, d))],
        key=lambda x: x,
        reverse=True
    )

    if not backups:
        return {
            "check": "backup_freshness",
            "status": "warning",
            "issues_found": 1,
            "details": {"last_backup": None, "total_backups": 0},
            "recommendation": "尚无任何数据备份。建议定期备份：'python superbrain.py backup create'。"
        }

    # Get latest backup age
    latest = os.path.join(backup_dir, backups[0])
    latest_mtime = os.path.getmtime(latest)
    latest_time = datetime.fromtimestamp(latest_mtime, dt_tz.utc)
    age_days = (datetime.now(dt_tz.utc) - latest_time).days

    # Count files in latest backup
    backup_files = len([f for f in os.listdir(latest) if os.path.isfile(os.path.join(latest, f))])

    return {
        "check": "backup_freshness",
        "status": "warning" if age_days > 30 else "healthy",
        "issues_found": 1 if age_days > 30 else 0,
        "details": {
            "last_backup": latest_time.strftime("%Y-%m-%d %H:%M"),
            "age_days": age_days,
            "total_backups": len(backups),
            "backup_files": backup_files
        },
        "recommendation": (
            f"最近备份于 {age_days} 天前（超过30天），建议执行新的备份。"
        ) if age_days > 30 else f"最近备份于 {age_days} 天前，状态正常。"
    }


def check_consistency(workspace=None):
    """
    Check for logical contradictions in memories.
    Flags memories with same entity+type but potentially conflicting content.
    """
    issues = find_issues(workspace)
    contradictions = issues.get("potential_contradictions", [])
    return {
        "check": "consistency",
        "status": "warning" if contradictions else "healthy",
        "issues_found": len(contradictions),
        "details": contradictions[:20],
        "recommendation": "Review flagged memory pairs for potential contradictions. Use 'memory merge' if they are duplicates." if contradictions else "No contradictions detected."
    }


def check_timeliness(workspace=None):
    """
    Check for potentially outdated information.
    Flags memories older than a threshold with low access counts.
    """
    from datetime import datetime, timedelta, timezone
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]

    config = load_config()
    stale_days = config.get("stale_threshold_days", 90)
    now = datetime.now(timezone.utc)
    stale_memories = []

    for m in active:
        # Parse timestamp
        ts_str = m.get("timestamp", "")
        try:
            if "T" in ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            else:
                ts = datetime.fromisoformat(ts_str + "T00:00:00+00:00")
            age_days = (now - ts).days
            access_count = m.get("access_count", 0)
            confidence = m.get("confidence", 0.5)

            # Flag if: old AND rarely accessed AND not high confidence
            if age_days > stale_days and access_count == 0 and confidence < 0.9:
                stale_memories.append({
                    "id": m["id"],
                    "type": m["type"],
                    "entity": m["entity"],
                    "content": m["content"][:80],
                    "age_days": age_days,
                    "last_accessed": m.get("last_accessed", "never"),
                    "confidence": confidence
                })
        except (ValueError, TypeError):
            continue

    return {
        "check": "timeliness",
        "status": "warning" if stale_memories else "healthy",
        "issues_found": len(stale_memories),
        "details": stale_memories[:20],
        "recommendation": "Consider archiving or updating stale memories. Low-confidence, rarely-accessed, old memories may be outdated." if stale_memories else "All memories are within freshness window."
    }


def check_temporal_validity(workspace=None):
    """
    v2.1.0: Check for memories with expired temporal validity.
    Flags active memories whose valid_until is in the past but status is still 'active'.
    """
    from datetime import datetime, timezone as tz
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    now = datetime.now(tz.utc).strftime("%Y-%m-%d")

    expired = []
    chained = []
    for m in active:
        valid_until = m.get("valid_until")
        if valid_until and valid_until < now:
            expired.append({
                "id": m["id"],
                "type": m["type"],
                "entity": m["entity"],
                "content": m["content"][:80],
                "valid_from": m.get("valid_from", "?"),
                "valid_until": valid_until,
                "confidence": m["confidence"]
            })
        if m.get("replaces") or m.get("replaced_by"):
            chained.append(m["id"])

    return {
        "check": "temporal_validity",
        "status": "warning" if expired else "healthy",
        "issues_found": len(expired),
        "details": expired[:20],
        "recommendation": (
            "Some memories have expired temporal validity but are still active. "
            "Use 'memory update --id <id> --status superseded' to mark them, "
            "or update valid_until if the fact is still current."
        ) if expired else "No expired memories detected.",
        "chain_linked_count": len(chained)
    }


    """
    Check for potentially outdated information.
    Flags memories older than a threshold with low access counts.
    """
    from datetime import datetime, timedelta, timezone
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]

    config = load_config()
    stale_days = config.get("stale_threshold_days", 90)
    now = datetime.now(timezone.utc)
    stale_memories = []

    for m in active:
        # Parse timestamp
        ts_str = m.get("timestamp", "")
        try:
            if "T" in ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            else:
                ts = datetime.fromisoformat(ts_str + "T00:00:00+00:00")
            age_days = (now - ts).days
            access_count = m.get("access_count", 0)
            confidence = m.get("confidence", 0.5)

            # Flag if: old AND rarely accessed AND not high confidence
            if age_days > stale_days and access_count == 0 and confidence < 0.9:
                stale_memories.append({
                    "id": m["id"],
                    "type": m["type"],
                    "entity": m["entity"],
                    "content": m["content"][:80],
                    "age_days": age_days,
                    "last_accessed": m.get("last_accessed", "never"),
                    "confidence": confidence
                })
        except (ValueError, TypeError):
            continue

    return {
        "check": "timeliness",
        "status": "warning" if stale_memories else "healthy",
        "issues_found": len(stale_memories),
        "details": stale_memories[:20],
        "recommendation": "Consider archiving or updating stale memories. Low-confidence, rarely-accessed, old memories may be outdated." if stale_memories else "All memories are within freshness window."
    }


def check_completeness(workspace=None):
    """
    Check for incomplete tasks or projects.
    Flags 'task' type memories that don't have a completion status.
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]

    incomplete = []
    for m in active:
        if m.get("type") == "task":
            attrs = m.get("attributes", {})
            completed = attrs.get("completed", False)
            status = attrs.get("task_status", "unknown")
            if not completed and status not in ("done", "completed", "cancelled"):
                incomplete.append({
                    "id": m["id"],
                    "entity": m["entity"],
                    "content": m["content"][:80],
                    "status": status,
                    "confidence": m["confidence"]
                })

    return {
        "check": "completeness",
        "status": "warning" if incomplete else "healthy",
        "issues_found": len(incomplete),
        "details": incomplete[:20],
        "recommendation": "Review incomplete tasks. Update status or archive if no longer relevant." if incomplete else "No incomplete tasks detected."
    }


def check_orphans(workspace=None):
    """
    Check for orphan nodes in the knowledge graph (nodes with no connections).
    """
    graph_stats = get_graph_stats(workspace)
    orphan_ids = graph_stats.get("orphan_ids", [])
    orphan_count = graph_stats.get("orphan_nodes", 0)

    # Get details of orphan nodes
    graph = read_graph(workspace)
    orphan_details = []
    for oid in orphan_ids[:20]:
        node = graph.get("nodes", {}).get(oid)
        if node:
            orphan_details.append({
                "id": oid,
                "name": node.get("name", "unknown"),
                "type": node.get("type", "unknown"),
                "created_at": node.get("created_at", "")
            })

    return {
        "check": "orphans",
        "status": "warning" if orphan_count > 0 else "healthy",
        "issues_found": orphan_count,
        "details": orphan_details,
        "recommendation": "Connect orphan nodes to related entities or remove if no longer relevant." if orphan_count > 0 else "All nodes are connected in the graph."
    }


def check_duplicates(workspace=None):
    """
    Check for duplicate memories using SimHash similarity.
    """
    issues = find_issues(workspace)
    duplicates = issues.get("duplicates", [])

    return {
        "check": "duplicates",
        "status": "warning" if duplicates else "healthy",
        "issues_found": len(duplicates),
        "details": duplicates[:20],
        "recommendation": "Use 'memory merge <id1> <id2>' to merge duplicate memories." if duplicates else "No duplicates detected."
    }


def run_full_check(workspace=None, auto_fix=False):
    """
    Run all self-check diagnostics (v3.4.0: 9项 = 3物理 + 6逻辑).
    If auto_fix=True, backup first, then resolve safe issues.
    """
    results = {
        "timestamp": get_timestamp(),
        "workspace": workspace or "default",
        "checks": {},
        "overall_status": "healthy",
        "total_issues": 0,
        "auto_fixed": 0,
        "backup_info": None
    }

    # Run all checks (physical first, then logical)
    checks = [
        # v3.4.0: 物理层
        check_file_integrity(workspace),
        check_index_integrity(workspace),
        check_backup_freshness(workspace),
        # 逻辑层
        check_consistency(workspace),
        check_timeliness(workspace),
        check_temporal_validity(workspace),
        check_completeness(workspace),
        check_orphans(workspace),
        check_duplicates(workspace)
    ]

    for check in checks:
        check_name = check["check"]
        results["checks"][check_name] = check
        if check["status"] in ("warning", "critical"):
            if results["overall_status"] != "critical":
                results["overall_status"] = (
                    "critical" if check["status"] == "critical" else "needs_attention"
                )
            results["total_issues"] += check["issues_found"]

    # v3.4.0: Auto-fix with backup
    if auto_fix and results["total_issues"] > 0:
        results["backup_info"] = _create_backup(workspace, reason="pre_fix")
        fixed = 0

        # Physical: rebuild index if needed
        idx_check = results["checks"].get("index_integrity", {})
        if idx_check.get("status") != "healthy":
            try:
                from sb_longterm import build_index
                build_index(workspace)
                fixed += 1
            except Exception:
                pass

        # Logical: archive low-confidence stale, merge high-sim duplicates
        timeliness = results["checks"].get("timeliness", {})
        if timeliness.get("status") != "healthy":
            for item in timeliness.get("details", []):
                if item.get("confidence", 1.0) < 0.3:
                    from sb_memory import update_memory
                    update_memory(item["id"], status="archived", workspace=workspace)
                    fixed += 1

        duplicates = results["checks"].get("duplicates", {})
        if duplicates.get("status") != "healthy":
            from sb_memory import merge_memories
            for dup in duplicates.get("details", []):
                if dup.get("similarity", 0) > 0.95:
                    merge_memories(dup["id1"], dup["id2"], workspace=workspace)
                    fixed += 1

        results["auto_fixed"] = fixed

    # Update meta
    update_meta("last_self_check", get_timestamp(), workspace)

    # Save report
    health_dir = get_health_dir()
    report_path = os.path.join(health_dir, f"report_{get_timestamp().replace(':', '-')}.json")
    write_json(report_path, results)
    # Also save as latest
    write_json(os.path.join(health_dir, "latest_report.json"), results)

    return results


def get_health_report(workspace=None):
    """Get the latest health report."""
    health_dir = get_health_dir()
    latest = read_json(os.path.join(health_dir, "latest_report.json"))
    if latest:
        return latest
    # No report yet, run a check
    return run_full_check(workspace)


def get_health_score(workspace=None):
    """
    Calculate a health score (0-100) based on the latest check.
    v3.4.0: includes physical integrity + backup + logical checks.
    """
    report = get_health_report(workspace)
    checks = report.get("checks", {})

    score = 100
    # Physical checks (high penalty)
    for chk in ["file_integrity", "index_integrity"]:
        if chk in checks:
            score -= min(30, checks[chk].get("issues_found", 0) * 15)
    # Backup freshness
    if "backup_freshness" in checks:
        b_details = checks["backup_freshness"].get("details", {})
        age = b_details.get("age_days", 0)
        if age > 90: score -= 15
        elif age > 30: score -= 5

    # Logical checks
    for check_name, check in checks.items():
        issues = check.get("issues_found", 0)
        if check_name == "duplicates":
            score -= min(20, issues * 5)
        elif check_name == "consistency":
            score -= min(25, issues * 8)
        elif check_name == "timeliness":
            score -= min(15, issues * 3)
        elif check_name == "completeness":
            score -= min(15, issues * 3)
        elif check_name == "temporal_validity":
            score -= min(10, issues * 2)
        elif check_name == "orphans":
            score -= min(10, issues * 2)
    for check_name, check in checks.items():
        issues = check.get("issues_found", 0)
        if check_name == "duplicates":
            score -= min(20, issues * 5)
        elif check_name == "consistency":
            score -= min(25, issues * 8)
        elif check_name == "timeliness":
            score -= min(15, issues * 3)
        elif check_name == "completeness":
            score -= min(15, issues * 3)
        elif check_name == "temporal_validity":
            score -= min(10, issues * 2)
        elif check_name == "orphans":
            score -= min(10, issues * 2)

    return max(0, score)
