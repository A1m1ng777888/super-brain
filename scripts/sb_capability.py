#!/usr/bin/env python3
"""
SuperBrain Capability-Aware Router v3.7
========================================
Implements "Jagged Intelligence" self-awareness (Karpathy 蒸馏):
  - Capability Profile: a scored map of what super-brain is good/bad at
  - Capability Check: query a capability's reliability before routing
  - Orchestrator Integration: warn when a subtask falls on a known weak spot

The core insight: LLM ability is jagged — some dimensions superhuman,
others surprisingly dumb. Super-brain should know its own jagged edges
and degrade gracefully instead of hiding failures.

Pure standard library. No external dependencies.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    read_json, write_json, get_workspace_dir,
    get_timestamp, ensure_dir
)

# --- Defaults ------------------------------------------------------------
RELIABILITY_THRESHOLD = 0.5     # Below this → trigger degradation
CRITICAL_THRESHOLD = 0.3        # Below this → must ask user

# --- Default Capability Profile ------------------------------------------
# Scores calibrated conservatively (~10-15% below actual observed reliability)
# Each capability maps to: label, score, degradation_strategy, ask_user
DEFAULT_CAPABILITIES = {
    "memory_parallel_write": {
        "label": "并行写入记忆（多进程）",
        "score": 0.1,   # ⚠️ CORRUPTION HISTORY: v3.6.1 批量入库竞态导致文件损坏
        "evidence": "v3.6.1: 7 进程并行写 memories.json → JSON 双重数组竞态损坏",
        "last_updated": "2026-07-08",
        "degradation_strategy": "serialize",
        "ask_user": False
    },
    "large_file_atomic_read": {
        "label": "大文件原子读取（>100KB）",
        "score": 0.6,
        "evidence": "v3.4.3: read_json 损坏时备�份+返回[]，但竞态读取未覆盖",
        "last_updated": "2026-07-06",
        "degradation_strategy": "backup_first",
        "ask_user": False
    },
    "cross_workspace_consistency": {
        "label": "跨工作空间一致性",
        "score": 0.4,
        "evidence": "未测试跨 workspace 的并行操作；observed_index 未跨 workspace",
        "last_updated": "2026-07-08",
        "degradation_strategy": "ask_user",
        "ask_user": True
    },
    "multi_hop_reasoning": {
        "label": "多跳推理（≥3步因果链）",
        "score": 0.5,
        "evidence": "reasoning 模块为纯规则引擎（无 LLM 辅助），3 跳以上不可靠",
        "last_updated": "2026-07-08",
        "degradation_strategy": "flag_low_confidence",
        "ask_user": False
    },
    "bulk_memory_ingest": {
        "label": "批量记忆入库（>10条/次）",
        "score": 0.3,
        "evidence": "无批量 API；逐条 add_memory 在 >50 条时慢且可能触发竞态",
        "last_updated": "2026-07-08",
        "degradation_strategy": "serialize_and_warn",
        "ask_user": True
    },
    "gating_chain_ignite": {
        "label": "门控链式点燃（推理链晋升）",
        "score": 0.7,
        "evidence": "v3.6.1 已实现 chain_ignite + gating_override；36 测试全过",
        "last_updated": "2026-07-08",
        "degradation_strategy": None,
        "ask_user": False
    },
    "token_roi_calculation": {
        "label": "Token ROI 量化",
        "score": 0.85,
        "evidence": "v3.5.0 上线，49 测试全过，实际使用多次验证",
        "last_updated": "2026-07-07",
        "degradation_strategy": None,
        "ask_user": False
    },
    "json_file_parallel_access": {
        "label": "JSON 文件并行读写",
        "score": 0.15,  # ⚠️ NO FILE LOCK — any parallel write is hazardous
        "evidence": "sb_core read/write 无文件锁；v3.6.1 事故为直接证据",
        "last_updated": "2026-07-08",
        "degradation_strategy": "serialize",
        "ask_user": True
    }
}


# --- Profile I/O ----------------------------------------------------------

def _get_profile_path(workspace=None):
    ws_dir = get_workspace_dir(workspace)
    return os.path.join(ws_dir, "capability_profile.json")


def _load_profile(workspace=None):
    """Load capability profile, or initialize with defaults."""
    path = _get_profile_path(workspace)
    profile = read_json(path)
    if not profile:
        profile = {"capabilities": DEFAULT_CAPABILITIES,
                   "RELIABILITY_THRESHOLD": RELIABILITY_THRESHOLD,
                   "CRITICAL_THRESHOLD": CRITICAL_THRESHOLD}
        ensure_dir(os.path.dirname(path))
        write_json(path, profile)
    return profile


def _save_profile(profile, workspace=None):
    write_json(_get_profile_path(workspace), profile)


# --- Capability Checks ----------------------------------------------------

def check_capability(cap_id, workspace=None):
    """
    Query a capability's reliability score and degradation strategy.

    Returns: (score, strategy, should_ask_user)
      - score: 0.0-1.0 reliability rating
      - strategy: degradation strategy name or None if reliable
      - should_ask_user: whether user confirmation is recommended
    """
    profile = _load_profile(workspace)
    cap = profile.get("capabilities", {}).get(cap_id)

    if not cap:
        # Unknown capability → optimistic default
        return (0.8, None, False)

    score = cap.get("score", 0.5)
    critical = profile.get("CRITICAL_THRESHOLD", CRITICAL_THRESHOLD)
    reliable = profile.get("RELIABILITY_THRESHOLD", RELIABILITY_THRESHOLD)

    if score < critical:
        return (score, cap.get("degradation_strategy"), True)
    elif score < reliable:
        return (score, cap.get("degradation_strategy"), cap.get("ask_user", False))
    else:
        return (score, None, False)


def check_capabilities(cap_ids, workspace=None):
    """
    Batch-check multiple capabilities.
    Returns dict: cap_id → {score, strategy, should_ask_user}
    """
    result = {}
    for cid in cap_ids:
        score, strategy, ask = check_capability(cid, workspace)
        result[cid] = {"score": score, "strategy": strategy, "should_ask_user": ask}
    return result


def list_capabilities(workspace=None):
    """List all known capabilities with scores."""
    profile = _load_profile(workspace)
    caps = profile.get("capabilities", {})
    result = []
    for cid, cap in caps.items():
        result.append({
            "id": cid,
            "label": cap.get("label", cid),
            "score": cap.get("score", 0.5),
            "degradation_strategy": cap.get("degradation_strategy"),
            "ask_user": cap.get("ask_user", False)
        })
    result.sort(key=lambda c: c["score"])
    return {
        "capabilities": result,
        "thresholds": {
            "reliable": profile.get("RELIABILITY_THRESHOLD", RELIABILITY_THRESHOLD),
            "critical": profile.get("CRITICAL_THRESHOLD", CRITICAL_THRESHOLD)
        },
        "total": len(result)
    }


def update_capability(cap_id, score=None, evidence=None, strategy=None,
                      ask_user=None, workspace=None):
    """Update a capability's score or metadata."""
    profile = _load_profile(workspace)
    if cap_id not in profile.get("capabilities", {}):
        return {"updated": False, "reason": f"capability '{cap_id}' not found"}

    cap = profile["capabilities"][cap_id]
    if score is not None:
        cap["score"] = max(0.0, min(1.0, float(score)))
    if evidence is not None:
        cap["evidence"] = evidence
    if strategy is not None:
        cap["degradation_strategy"] = strategy
    if ask_user is not None:
        cap["ask_user"] = bool(ask_user)
    cap["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    profile["capabilities"][cap_id] = cap
    _save_profile(profile, workspace)
    return {"updated": True, "capability": cap}


# --- Orchestrator Integration Helpers ------------------------------------

def assess_task_capabilities(task_description, workspace=None):
    """
    Given a task description, scan it for capability requirements
    and return any warnings about weak spots.
    Designed to be called from sb_orchestrator.assess_task().
    """
    desc_lower = task_description.lower()
    warnings = []

    # Simple keyword-based capability mapping
    CAPABILITY_KEYWORDS = {
        "memory_parallel_write": ["并行", "批量导入", "同时写", "parallel write", "bulk"],
        "json_file_parallel_access": ["并行", "同时", "parallel", "concurrent"],
        "cross_workspace_consistency": ["跨工作空间", "多工作空间", "cross workspace", "迁移"],
        "multi_hop_reasoning": ["推理链", "多步推理", "因果链", "推理", "reasoning chain"],
        "bulk_memory_ingest": ["批量入库", "大量导入", "大量记忆", "批量", "bulk ingest"],
    }

    triggered_caps = set()
    for cap_id, keywords in CAPABILITY_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower:
                triggered_caps.add(cap_id)
                break

    for cap_id in triggered_caps:
        score, strategy, ask = check_capability(cap_id, workspace)
        if strategy:  # Only flag if a degradation strategy exists
            warnings.append({
                "capability": cap_id,
                "score": score,
                "strategy": strategy,
                "should_ask_user": ask
            })

    return {
        "triggered_capabilities": list(triggered_caps),
        "warnings": warnings,
        "has_critical_warnings": any(w["should_ask_user"] for w in warnings)
    }
