#!/usr/bin/env python3
"""
SuperBrain Workspace Gating Layer v3.6.0
=========================================
Implements the "global workspace" selectivity principle inspired by
Anthropic's "A Global Workspace in Language Models" (2026-07-06):

  The active workspace is a PRIVILEGED SUBSET of all stored memories.
  Most processing runs automatically on cold storage; only memories that
  cross a salience threshold get "promoted" into the workspace that
  participates in reasoning and gets injected into context.

This module provides:
  - compute_salience(mem)        : score a memory's promotion worthiness [0,1]
  - get_threshold / set_threshold : per-workspace promotion threshold (default 0.35)
  - is_promoted(mem)              : salience >= threshold AND active
  - chain_ignite(workspace)       : if any node of a reasoning chain is promoted,
                                    the whole chain ignites (paper's Ignition idea)
  - get_active_workspace(...)     : the promoted, capacity-capped workspace
  - promote / demote              : manual override of a single memory
  - calibrate(workspace)          : report promotion ratio at a threshold (tuning aid)

Pure standard library. No external dependencies (consistent with the skill).

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    read_memories, write_memories, read_meta, update_meta, get_timestamp,
    read_json, write_json, get_workspace_dir, generate_id
)

# --- Defaults -------------------------------------------------------------
DEFAULT_THRESHOLD = 0.35
DEFAULT_CAP = 50

# Type-level baseline adjustment to salience (added into the [0,1] mapping).
# preference/decision are worth keeping hot; reasoning_intermediate starts
# cooler so it does not flood the workspace unless its chain ignites.
TYPE_BASELINE = {
    "preference": 0.15,
    "decision": 0.12,
    "task": 0.05,
    "event": 0.03,
    "relationship": 0.0,
    "fact": 0.0,
    "context": -0.05,
    "reasoning_intermediate": -0.25,
}


# --- Helpers --------------------------------------------------------------
def _parse_ts(ts):
    """Parse a SuperBrain timestamp into a timezone-aware datetime, or None."""
    if not ts:
        return None
    s = str(ts).replace("Z", "+00:00")
    try:
        if "T" in s:
            dt = datetime.fromisoformat(s)
        else:
            dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _days_since(ts):
    """Days since a timestamp; very large if missing/parseable."""
    dt = _parse_ts(ts)
    if dt is None:
        return 999.0
    now = datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def get_threshold(workspace=None):
    """Read the promotion threshold for this workspace (default 0.35)."""
    try:
        meta = read_meta(workspace)
        return float(meta.get("gating_threshold", DEFAULT_THRESHOLD))
    except Exception:
        return float(DEFAULT_THRESHOLD)


def set_threshold(value, workspace=None):
    """Persist the promotion threshold for this workspace."""
    v = float(value)
    if not (0.0 <= v <= 1.0):
        raise ValueError("threshold must be in [0, 1]")
    update_meta("gating_threshold", v, workspace)
    return v


# --- Core salience --------------------------------------------------------
def compute_salience(mem, workspace=None):
    """
    Compute a memory's salience in [0, 1] from multiple signals:

      confidence   : how sure we are of the memory
      recency      : exponential decay (half-life ~30 days) of last_accessed
      access_count : log-saturating usage frequency (cap ~10)
      entanglement : number of related_nodes (graph connectivity)
      type         : baseline adjustment (preference/decision hotter,
                     reasoning_intermediate cooler)

    The final score is a weighted sum mapped into [0, 1].
    """
    mem_type = mem.get("type", "fact")
    confidence = float(mem.get("confidence", 0.5))
    recency_days = _days_since(mem.get("last_accessed") or mem.get("timestamp"))
    access = int(mem.get("access_count", 0))
    entanglement = len(mem.get("related_nodes", []) or [])

    recency = 0.5 ** (recency_days / 30.0)               # 1.0 fresh -> 0.0 old
    access_score = min(1.0, (access ** 0.5) / (10 ** 0.5))
    ent_score = min(1.0, entanglement / 5.0)
    baseline = TYPE_BASELINE.get(mem_type, 0.0)

    # Map baseline (-0.25 .. +0.15) into a 0..1 contribution via (baseline + 0.5).
    sal = (0.30 * confidence
           + 0.25 * recency
           + 0.20 * access_score
           + 0.15 * ent_score
           + 0.10 * (baseline + 0.5))
    sal = max(0.0, min(1.0, sal))
    return round(sal, 4)


def is_promoted(mem, workspace=None):
    """True if the memory is active and its salience crosses the threshold."""
    if mem.get("status") != "active":
        return False
    return compute_salience(mem, workspace) >= get_threshold(workspace)


# --- Ignition & active workspace ------------------------------------------
def chain_ignite(workspace=None):
    """
    Paper's Ignition: if ANY node of a reasoning chain is promoted (by salience
    or by manual override), the WHOLE chain ignites into the workspace. This
    prevents intermediate reasoning nodes from being starved when only one
    link happens to be retrieved.
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    threshold = get_threshold(workspace)

    chain_promoted = set()
    for m in active:
        cid = m.get("chain_id")
        if not cid:
            continue
        if m.get("workspace_promoted", False) or compute_salience(m, workspace) >= threshold:
            chain_promoted.add(cid)

    changed = 0
    for m in active:
        cid = m.get("chain_id")
        if cid in chain_promoted and not m.get("workspace_promoted", False):
            before = {"workspace_promoted": False}
            m["workspace_promoted"] = True
            after = {"workspace_promoted": True}
            changed += 1
            # v3.7: audit trail — chain ignite is reversible
            _audit_log("chain_ignite", m["id"],
                       f"Chain ignited via chain_id={cid}",
                       before, after, reversible=True, workspace=workspace)

    if changed:
        write_memories(memories, workspace)
    return {"chain_promoted": len(chain_promoted), "changed": changed}


def get_active_workspace(workspace=None, cap=DEFAULT_CAP):
    """
    Return the promoted memories (the 'global workspace' analog).

    Promotion rule:
      1. A memory is promoted if salience >= threshold OR manually flagged.
      2. Chain ignition: any promoted chain node promotes its whole chain.
      3. The result is sorted by salience and capped to `cap` (capacity limit),
         mirroring GWT's limited workspace capacity.
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    threshold = get_threshold(workspace)

    # v3.6.1: gating_override 优先（手动 promote/demote 不被 salience 重算覆盖）
    for m in active:
        ov = m.get("gating_override")
        if ov == "promote":
            m["workspace_promoted"] = True
        elif ov == "demote":
            m["workspace_promoted"] = False
        elif not m.get("workspace_promoted", False):
            m["workspace_promoted"] = compute_salience(m, workspace) >= threshold

    chain_promoted = set()
    for m in active:
        cid = m.get("chain_id")
        if cid and (m.get("workspace_promoted", False) or compute_salience(m, workspace) >= threshold):
            chain_promoted.add(cid)
    for m in active:
        cid = m.get("chain_id")
        if cid in chain_promoted:
            m["workspace_promoted"] = True

    promoted = [m for m in active if m.get("workspace_promoted")]
    promoted.sort(key=lambda m: compute_salience(m, workspace), reverse=True)
    if cap and len(promoted) > cap:
        promoted = promoted[:cap]

    write_memories(memories, workspace)
    return promoted


# --- Manual override ------------------------------------------------------
def promote(mem_id, workspace=None):
    """Force-promote a single memory into the workspace (manual override)."""
    memories = read_memories(workspace)
    for m in memories:
        if m["id"] == mem_id and m.get("status") == "active":
            before = {"workspace_promoted": m.get("workspace_promoted", False)}
            m["gating_override"] = "promote"
            m["workspace_promoted"] = True
            m["salience"] = max(m.get("salience", 0.0), get_threshold(workspace))
            after = {"workspace_promoted": True, "gating_override": "promote"}
            write_memories(memories, workspace)
            # v3.7: audit trail
            _audit_log("manual_promote", mem_id,
                       f"Manual promote override (salience >= {get_threshold(workspace)})",
                       before, after, reversible=False, workspace=workspace)
            return {"id": mem_id, "promoted": True}
    return {"id": mem_id, "promoted": False, "reason": "not found or inactive"}


def demote(mem_id, workspace=None):
    """Force-demote a single memory out of the workspace (manual override)."""
    memories = read_memories(workspace)
    for m in memories:
        if m["id"] == mem_id:
            before = {"workspace_promoted": m.get("workspace_promoted", False)}
            m["gating_override"] = "demote"
            m["workspace_promoted"] = False
            after = {"workspace_promoted": False, "gating_override": "demote"}
            write_memories(memories, workspace)
            # v3.7: audit trail
            _audit_log("manual_demote", mem_id,
                       "Manual demote override",
                       before, after, reversible=False, workspace=workspace)
            return {"id": mem_id, "demoted": True}
    return {"id": mem_id, "demoted": False, "reason": "not found"}


# --- v3.7: Audit Log & Rollback (Karpathy Iron Man 套装固化) -----------------
_MAX_AUDIT_ENTRIES = 500


def _audit_log(action, target_id, reason, before, after, reversible=True, workspace=None):
    """
    Record a gating action to the audit trail.
    All auto/manual promote/demote/chain_ignite flow through here.
    """
    ws_dir = get_workspace_dir(workspace)
    log_path = os.path.join(ws_dir, "audit_log.json")
    log = read_json(log_path) or {"entries": []}

    entry = {
        "id": f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}",
        "timestamp": get_timestamp(),
        "action": action,
        "target_id": target_id,
        "target_type": "memory",
        "reason": reason,
        "before_state": before,
        "after_state": after,
        "reversible": reversible,
        "reverted": False
    }
    log["entries"].append(entry)

    # Trim to max entries
    if len(log["entries"]) > _MAX_AUDIT_ENTRIES:
        log["entries"] = log["entries"][-_MAX_AUDIT_ENTRIES:]

    write_json(log_path, log)
    return entry


def _get_audit_entries_for(mem_id, workspace=None):
    """Retrieve all audit entries for a specific memory."""
    ws_dir = get_workspace_dir(workspace)
    log_path = os.path.join(ws_dir, "audit_log.json")
    log = read_json(log_path)
    if not log:
        return []
    return [e for e in log.get("entries", []) if e.get("target_id") == mem_id]


def get_audit_log(limit=20, workspace=None):
    """Retrieve recent audit entries."""
    ws_dir = get_workspace_dir(workspace)
    log_path = os.path.join(ws_dir, "audit_log.json")
    log = read_json(log_path)
    if not log:
        return {"entries": [], "total": 0}
    entries = log.get("entries", [])
    return {"entries": entries[-limit:], "total": len(entries)}


def rollback(n=1, workspace=None):
    """
    Rollback the last N reversible auto-actions.
    Manual overrides (manual_promote/manual_demote) are not auto-rolled back.
    Returns list of rolled-back entry IDs.
    """
    ws_dir = get_workspace_dir(workspace)
    log_path = os.path.join(ws_dir, "audit_log.json")
    log = read_json(log_path)
    if not log:
        return {"rolled_back": 0, "ids": []}

    rolled_back = []
    count = 0
    memories = read_memories(workspace)

    for entry in reversed(log["entries"]):
        if count >= n:
            break
        if not entry.get("reversible", False):
            continue
        if entry.get("reverted", False):
            continue
        # Only auto-rollback non-manual actions
        if entry["action"].startswith("manual_"):
            continue

        target_id = entry["target_id"]
        before = entry.get("before_state", {})

        # Restore before_state
        for m in memories:
            if m["id"] == target_id:
                for key, val in before.items():
                    if key in ("workspace_promoted", "gating_override", "salience"):
                        m[key] = val
                break

        entry["reverted"] = True
        rolled_back.append(entry["id"])
        count += 1

    if rolled_back:
        write_memories(memories, workspace)
        write_json(log_path, log)

    return {"rolled_back": len(rolled_back), "ids": rolled_back}


def explain(mem_id, workspace=None):
    """
    Return a human-readable explanation of a memory's gating state:
    current salience, why promoted/demoted, full audit trail.
    """
    memories = read_memories(workspace)
    mem = next((m for m in memories if m["id"] == mem_id), None)

    if not mem:
        return {"memory_id": mem_id, "found": False, "reason": "memory not found"}

    audit = _get_audit_entries_for(mem_id, workspace)

    # Build salience breakdown
    mem_type = mem.get("type", "fact")
    confidence = float(mem.get("confidence", 0.5))
    access = int(mem.get("access_count", 0))
    entanglement = len(mem.get("related_nodes", []) or [])
    recency_days = _days_since(mem.get("last_accessed") or mem.get("timestamp"))

    return {
        "memory_id": mem_id,
        "found": True,
        "current_salience": mem.get("salience"),
        "current_promoted": mem.get("workspace_promoted", False),
        "gating_override": mem.get("gating_override"),
        "provenance": mem.get("provenance", "unknown"),
        "salience_breakdown": {
            "confidence": confidence,
            "recency_days": round(recency_days, 1),
            "access_count": access,
            "entanglement": entanglement,
            "type": mem_type,
            "type_baseline": TYPE_BASELINE.get(mem_type, 0.0)
        },
        "audit_trail": audit
    }


# --- Diagnostics ----------------------------------------------------------
def calibrate(workspace=None, threshold=None):
    """
    Report the promotion ratio at a given threshold. Use this to tune the
    threshold toward the GWT-aligned band (~8-25% of active memories promoted).
    """
    threshold = float(threshold) if threshold is not None else get_threshold(workspace)
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    promoted = [m for m in active if compute_salience(m, workspace) >= threshold]
    ratio = len(promoted) / max(len(active), 1)

    if ratio > 0.25:
        recommendation = "ratio too high (>25%): raise threshold to shrink the workspace"
    elif ratio < 0.08:
        recommendation = "ratio too low (<8%): lower threshold to grow the workspace"
    else:
        recommendation = "within GWT-aligned 8-25% band"

    return {
        "total_active": len(active),
        "promoted": len(promoted),
        "promotion_ratio": round(ratio, 3),
        "threshold": threshold,
        "recommendation": recommendation,
    }


def get_status(workspace=None):
    """Compact status snapshot for CLI / diagnostics."""
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    promoted = get_active_workspace(workspace)
    return {
        "threshold": get_threshold(workspace),
        "total_active": len(active),
        "promoted": len(promoted),
        "promotion_ratio": round(len(promoted) / max(len(active), 1), 3),
    }
