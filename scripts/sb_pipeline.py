#!/usr/bin/env python3
"""
SuperBrain Classification Pipeline v3.0.0
Classifies content into definition vs chitchat categories with different decay rates.

Definition class (定义类): Facts, preferences, decisions, technical knowledge
  - Slow decay: long retention (default 365 days half-life)
  - High storage priority
  - Always searchable

Chitchat class (闲聊类): Casual conversation, greetings, transient comments
  - Fast decay: short retention (default 7 days half-life)
  - Low storage priority
  - Auto-archived after decay period

This module saves storage space by applying differentiated retention policies.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import re
from datetime import datetime, timezone, timedelta
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_json, write_json, ensure_workspace, get_timestamp, load_config
from sb_search import tokenize, tf_idf_cosine_similarity


# Content categories
CATEGORY_DEFINITION = "definition"
CATEGORY_CHITCHAT = "chitchat"
CATEGORY_HYBRID = "hybrid"  # Contains both definition and chitchat elements

# Decay configuration (in days)
DECAY_CONFIG = {
    CATEGORY_DEFINITION: {
        "half_life_days": 365,
        "min_confidence": 0.6,
        "auto_archive_days": 730,
        "hard_delete_retention": 0.05,    # v3.1.0: retention below this → mark deprecated
        "deprecated_grace_days": 90,       # v3.1.0: days after deprecation before hard delete
    },
    CATEGORY_CHITCHAT: {
        "half_life_days": 7,
        "min_confidence": 0.3,
        "auto_archive_days": 30,
        "hard_delete_retention": 0.10,     # v3.1.0
        "deprecated_grace_days": 0,         # v3.1.0: chitchat → delete immediately (no grace)
    },
    CATEGORY_HYBRID: {
        "half_life_days": 90,
        "min_confidence": 0.4,
        "auto_archive_days": 180,
        "hard_delete_retention": 0.08,     # v3.1.0
        "deprecated_grace_days": 60,        # v3.1.0
    }
}

# Definition indicators: patterns that suggest factual/definitional content
DEFINITION_PATTERNS = [
    r'(?:等于|意味着|定义为|指的是|就是|也就是)',  # v3.9.2: 去掉裸"是"防"是的"误判
    r'(?:因为|所以|由于|导致|引起|使得)',
    r'(?:必须|需要|要求|应该|应当)',
    r'(?:规则|原则|定律|定理|公式|算法)',
    r'(?:架构|设计|方案|策略|模式|流程)',
    r'(?:版本|配置|环境|依赖|安装|部署)',
    r'(?:\bis\b|\bare\b|\bequals\b|\bmeans\b|\bdefined as\b|\brefers to\b)',  # v3.9.2: 加词边界
    r'(?:\bbecause\b|\btherefore\b|\bdue to\b|\bcauses?\b|\bresults in\b)',
    r'(?:\bmust\b|\bshould\b|\brequires?\b|\bneeds to\b)',
    r'(?:\brule\b|\bprinciple\b|\blaw\b|\btheorem\b|\bformula\b|\balgorithm\b)',
]

# Chitchat indicators: patterns that suggest casual conversation
CHITCHAT_PATTERNS = [
    r'(?:哈哈|嘿嘿|呵呵|嗯嗯|哦哦|好的|收到|明白|了解)',
    r'(?:谢谢|感谢|辛苦了|多谢|thx|thanks)',
    r'(?:你好|hi|hello|hey|嗨|早上好|晚上好)',
    r'(?:再见|拜拜|bye|晚安|回头见)',
    r'(?:随便|都行|无所谓|看情况)',
    r'(?:感觉|觉得|好像|似乎|大概|可能吧)',
    r'(?:试试|看看|搞一下|弄一下|整一下)',
    r'(?:天气|吃饭|休息|睡觉|周末|放假)',
]

# Compile patterns
DEFINITION_REGEX = [re.compile(p, re.IGNORECASE) for p in DEFINITION_PATTERNS]
CHITCHAT_REGEX = [re.compile(p, re.IGNORECASE) for p in CHITCHAT_PATTERNS]


def classify_content(text):
    """
    Classify content as definition, chitchat, or hybrid.
    
    Uses pattern matching + structural analysis:
    - Count definition vs chitchat indicator patterns
    - Analyze text structure (length, formality, information density)
    - Compute information density score
    
    Returns:
        dict with:
        - category: "definition" | "chitchat" | "hybrid"
        - confidence: 0.0-1.0
        - definition_score: 0.0-1.0
        - chitchat_score: 0.0-1.0
        - reasoning: str explaining the classification
    """
    if not text or len(text.strip()) < 2:
        return {
            "category": CATEGORY_CHITCHAT,
            "confidence": 0.5,
            "definition_score": 0.0,
            "chitchat_score": 0.5,
            "reasoning": "Too short to be definitional"
        }
    
    text_lower = text.lower()
    
    # Count pattern matches
    def_matches = sum(1 for regex in DEFINITION_REGEX if regex.search(text))
    chat_matches = sum(1 for regex in CHITCHAT_REGEX if regex.search(text))
    
    # Structural analysis
    tokens = tokenize(text)
    token_count = len(tokens)
    unique_tokens = len(set(tokens))
    
    # Information density: ratio of unique tokens to total tokens
    info_density = unique_tokens / max(token_count, 1)
    
    # Length factor: longer text more likely to be definitional
    length_factor = min(1.0, len(text) / 100)
    
    # Formality check: presence of punctuation, structured sentences
    has_period = '。' in text or '.' in text
    has_comma = '，' in text or ',' in text
    has_colon = '：' in text or ':' in text
    formality = sum([has_period, has_comma, has_colon]) / 3.0
    
    # Compute scores
    definition_score = min(1.0, (def_matches * 0.25) + (info_density * 0.3) + (length_factor * 0.2) + (formality * 0.25))
    chitchat_score = min(1.0, (chat_matches * 0.35) + ((1 - info_density) * 0.25) + ((1 - length_factor) * 0.2) + ((1 - formality) * 0.2))
    
    # Determine category
    if definition_score > chitchat_score * 1.3 and definition_score > 0.35:
        category = CATEGORY_DEFINITION
        confidence = min(1.0, definition_score)
        reasoning = f"Definition indicators: {def_matches} patterns, info_density={info_density:.2f}, formality={formality:.2f}"
    elif chitchat_score > definition_score * 1.3 and chitchat_score > 0.35:
        category = CATEGORY_CHITCHAT
        confidence = min(1.0, chitchat_score)
        reasoning = f"Chitchat indicators: {chat_matches} patterns, info_density={info_density:.2f}, casual tone"
    elif definition_score > 0.3 and chitchat_score > 0.3:
        category = CATEGORY_HYBRID
        confidence = 0.6
        reasoning = f"Mixed content: def={definition_score:.2f}, chat={chitchat_score:.2f}"
    elif definition_score > chitchat_score:
        category = CATEGORY_DEFINITION
        confidence = max(0.5, definition_score)
        reasoning = f"Lean definition: def={definition_score:.2f}, chat={chitchat_score:.2f}"
    else:
        category = CATEGORY_CHITCHAT
        confidence = max(0.5, chitchat_score)
        reasoning = f"Lean chitchat: def={definition_score:.2f}, chat={chitchat_score:.2f}"
    
    return {
        "category": category,
        "confidence": round(confidence, 3),
        "definition_score": round(definition_score, 3),
        "chitchat_score": round(chitchat_score, 3),
        "reasoning": reasoning
    }


def compute_decay_factor(memory, category=None, now=None):
    """
    Compute decay factor for a memory based on its category and age.
    
    Definition memories decay slowly (365-day half-life).
    Chitchat memories decay fast (7-day half-life).
    
    Returns: float 0.0-1.0 (1.0 = fresh, 0.0 = fully decayed)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    
    if category is None:
        category = memory.get("attributes", {}).get("content_category", CATEGORY_HYBRID)
    
    decay_config = DECAY_CONFIG.get(category, DECAY_CONFIG[CATEGORY_HYBRID])
    half_life = decay_config["half_life_days"]
    
    # Parse timestamp
    ts_str = memory.get("timestamp", "")
    try:
        if "T" in ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        else:
            ts = datetime.fromisoformat(ts_str + "T00:00:00+00:00")
        # Ensure timezone-aware
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 1.0  # Can't parse, assume fresh
    
    age_days = (now - ts).days
    if age_days <= 0:
        return 1.0
    
    # Exponential decay: factor = 0.5^(age / half_life)
    decay_factor = 0.5 ** (age_days / half_life)
    
    # Access count boost: frequently accessed memories decay slower
    access_count = memory.get("access_count", 0)
    access_boost = min(0.3, access_count * 0.05)  # Up to 30% boost
    
    # Confidence boost: high-confidence memories decay slower
    confidence = memory.get("confidence", 0.5)
    confidence_boost = (confidence - 0.5) * 0.2  # +/- 10% based on confidence
    
    return max(0.0, min(1.0, decay_factor + access_boost + confidence_boost))


def should_archive(memory, category=None, now=None):
    """
    Determine if a memory should be archived based on decay.
    
    Returns: (should_archive: bool, reason: str)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    
    if category is None:
        category = memory.get("attributes", {}).get("content_category", CATEGORY_HYBRID)
    
    decay_config = DECAY_CONFIG.get(category, DECAY_CONFIG[CATEGORY_HYBRID])
    auto_archive_days = decay_config["auto_archive_days"]
    
    ts_str = memory.get("timestamp", "")
    try:
        if "T" in ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        else:
            ts = datetime.fromisoformat(ts_str + "T00:00:00+00:00")
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return (False, "unparseable timestamp")
    
    age_days = (now - ts).days
    access_count = memory.get("access_count", 0)
    
    if age_days > auto_archive_days and access_count == 0:
        return (True, f"aged {age_days}d without access (category={category})")
    
    decay = compute_decay_factor(memory, category, now)
    if decay < 0.05:
        return (True, f"decay factor {decay:.3f} below threshold (category={category})")
    
    return (False, "within retention window")


def apply_decay_to_search(results, workspace=None):
    """
    Apply decay-weighted scoring to search results.
    Memories with lower decay factors get reduced scores.
    
    Args:
        results: list of (memory, score, match_type) tuples
        workspace: workspace name
    
    Returns: adjusted results list
    """
    now = datetime.now(timezone.utc)
    adjusted = []
    
    for mem, score, match_type in results:
        category = mem.get("attributes", {}).get("content_category", CATEGORY_HYBRID)
        decay = compute_decay_factor(mem, category, now)
        adjusted_score = score * (0.3 + 0.7 * decay)  # Min 30% of original score
        adjusted.append((mem, adjusted_score, match_type))
    
    adjusted.sort(key=lambda x: x[1], reverse=True)
    return adjusted


def get_pipeline_stats(workspace=None):
    """Get classification pipeline statistics."""
    from sb_memory import read_memories
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    category_counts = {CATEGORY_DEFINITION: 0, CATEGORY_CHITCHAT: 0, CATEGORY_HYBRID: 0}
    category_confidence = {CATEGORY_DEFINITION: [], CATEGORY_CHITCHAT: [], CATEGORY_HYBRID: 0}
    
    now = datetime.now(timezone.utc)
    total_decay = 0.0
    
    for m in active:
        cat = m.get("attributes", {}).get("content_category")
        if cat is None:
            # Auto-classify unclassified memories
            result = classify_content(m.get("content", ""))
            cat = result["category"]
        
        category_counts[cat] = category_counts.get(cat, 0) + 1
        decay = compute_decay_factor(m, cat, now)
        total_decay += decay
    
    avg_decay = total_decay / max(len(active), 1)
    
    return {
        "total_memories": len(active),
        "category_distribution": category_counts,
        "avg_decay_factor": round(avg_decay, 3),
        "decay_config": {k: {"half_life_days": v["half_life_days"], "auto_archive_days": v["auto_archive_days"]} for k, v in DECAY_CONFIG.items()}
    }


# ===================================================================
# v3.1.0: Hard Delete Lifecycle (退场生命周期)
# ===================================================================

def cleanup_memories(workspace=None, dry_run=False, force=False):
    """
    v3.1.0: Clean up decayed memories with a staged lifecycle.
    
    Stage 1 (deprecate): retention < hard_delete_retention → mark "deprecated"
    Stage 2 (delete): deprecated for > deprecated_grace_days → hard delete
    
    Auto-backs up memories before any destructive action.
    
    Args:
        workspace: workspace name
        dry_run: if True, only report what would be deleted
        force: if True, skip confirmation and auto-backup
    
    Returns:
        dict with cleanup report
    """
    from sb_memory import read_memories, write_memories
    import shutil
    
    memories = read_memories(workspace)
    ws_dir = ensure_workspace(workspace)
    now = datetime.now(timezone.utc)
    
    # Auto-backup before cleanup (unless dry_run)
    if not dry_run and memories:
        backup_path = os.path.join(ws_dir, f"memories_backup_{now.strftime('%Y%m%d_%H%M%S')}.json")
        try:
            write_json(backup_path, memories)
        except Exception as e:
            # v3.9.2: 备份失败即中止，防止无安全网下覆写主存储
            print(f"  ⚠ cleanup_memories: backup failed, aborting: {e}", file=sys.stderr)
            return {"deprecated": [], "deleted": [], "skipped": 0,
                    "total": len(memories), "timestamp": now.isoformat(),
                    "dry_run": dry_run, "error": f"backup_failed: {e}"}
    
    report = {
        "deprecated": [],
        "deleted": [],
        "skipped": 0,
        "total": len(memories),
        "timestamp": now.isoformat(),
        "dry_run": dry_run
    }
    
    active = [m for m in memories]
    for m in active:
        cat = m.get("attributes", {}).get("content_category")
        if cat is None:
            result = classify_content(m.get("content", ""))
            cat = result["category"]
        
        config = DECAY_CONFIG.get(cat, DECAY_CONFIG[CATEGORY_HYBRID])
        retention = compute_decay_factor(m, cat, now)
        status = m.get("status", "active")
        
        # Stage 1: Mark as deprecated if retention is critically low
        if retention <= config.get("hard_delete_retention", 0.05) and status == "active":
            if not dry_run:
                m["status"] = "deprecated"
                m["deprecated_at"] = now.isoformat()
                m["deprecated_retention"] = round(retention, 4)
            report["deprecated"].append({
                "id": m["id"],
                "content": m.get("content", "")[:60],
                "category": cat,
                "retention": round(retention, 4)
            })
            continue
        
        # Stage 2: Hard delete if deprecated past grace period
        if status == "deprecated" and "deprecated_at" in m:
            try:
                dep_dt = datetime.fromisoformat(m["deprecated_at"].replace("Z", "+00:00"))
                if dep_dt.tzinfo is None:
                    dep_dt = dep_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                dep_dt = now
            
            grace = config.get("deprecated_grace_days", 90)
            days_deprecated = (now - dep_dt).days
            
            if grace == 0 or days_deprecated >= grace:
                report["deleted"].append({
                    "id": m["id"],
                    "content": m.get("content", "")[:60],
                    "category": cat,
                    "retention": round(retention, 4),
                    "days_deprecated": days_deprecated
                })
                if not dry_run:
                    memories.remove(m)
    
    if not dry_run:
        write_memories(memories, workspace)
    
    report["deprecated_count"] = len(report["deprecated"])
    report["deleted_count"] = len(report["deleted"])
    
    return report
