#!/usr/bin/env python3
"""
SuperBrain Self-Check System
Periodic diagnostics: consistency, timeliness, temporal_validity (v2.1.0),
completeness, orphans, duplicates.
Generates health reports and can auto-fix safe issues.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    get_timestamp, read_memories, write_memories,
    read_graph, write_graph, read_meta, update_meta,
    get_health_dir, write_json, read_json, print_json, load_config
)
from sb_search import find_duplicates, simhash, simhash_similarity
from sb_memory import find_issues, get_stats as get_mem_stats
from sb_graph import get_stats as get_graph_stats


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
    Run all self-check diagnostics.
    If auto_fix=True, automatically resolve safe issues (e.g., archive confirmed duplicates).
    """
    results = {
        "timestamp": get_timestamp(),
        "workspace": workspace or "default",
        "checks": {},
        "overall_status": "healthy",
        "total_issues": 0,
        "auto_fixed": 0
    }

    # Run all checks
    checks = [
        check_consistency(workspace),
        check_timeliness(workspace),
        check_temporal_validity(workspace),  # v2.1.0
        check_completeness(workspace),
        check_orphans(workspace),
        check_duplicates(workspace)
    ]

    for check in checks:
        check_name = check["check"]
        results["checks"][check_name] = check
        if check["status"] != "healthy":
            results["overall_status"] = "needs_attention"
            results["total_issues"] += check["issues_found"]

    # Auto-fix safe issues
    if auto_fix:
        fixed = 0
        # Auto-archive very low confidence stale memories (confidence < 0.3)
        timeliness = results["checks"]["timeliness"]
        if timeliness["status"] != "healthy":
            for item in timeliness.get("details", []):
                if item.get("confidence", 1.0) < 0.3:
                    from sb_memory import update_memory
                    update_memory(item["id"], status="archived", workspace=workspace)
                    fixed += 1

        # Auto-merge very high similarity duplicates (similarity > 0.95)
        duplicates = results["checks"]["duplicates"]
        if duplicates["status"] != "healthy":
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
    Factors: consistency, timeliness, completeness, graph connectivity, duplication.
    """
    report = get_health_report(workspace)
    checks = report.get("checks", {})

    score = 100
    # Each issue reduces score
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
