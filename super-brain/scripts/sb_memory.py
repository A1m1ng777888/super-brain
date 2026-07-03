#!/usr/bin/env python3
"""
SuperBrain Memory Engine v3.0.0
Memory CRUD, confidence management, merging, time-decay retrieval.
v3.0.0: Auto-store, cross-session association, typo correction, expression learning.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import re
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    generate_id, get_timestamp, read_memories, write_memories,
    read_graph, write_graph, update_meta, print_json, print_table,
    ensure_workspace, load_config, read_json, write_json, get_workspace_dir
)
from sb_search import (
    simhash, search_memories, find_duplicates,
    ternary_hash, fuzzy_match, fuzzy_token_match, levenshtein_distance,
    tokenize
)


# Memory types
MEMORY_TYPES = ["fact", "preference", "event", "relationship", "task", "decision", "context"]

# Default attributes for each type
TYPE_DEFAULTS = {
    "fact": {"scope": "global", "category": "knowledge"},
    "preference": {"scope": "global", "category": "personal"},
    "event": {"scope": "workspace", "category": "history"},
    "relationship": {"scope": "global", "category": "social"},
    "task": {"scope": "workspace", "category": "work"},
    "decision": {"scope": "workspace", "category": "work"},
    "context": {"scope": "session", "category": "background"}
}


def add_memory(content, mem_type="fact", entity=None, confidence=0.8,
               source=None, attributes=None, tags=None, workspace=None,
               valid_from=None, valid_until=None, replaces=None):
    """
    Add a new memory to the store.
    
    Temporal parameters (v2.1.0):
        valid_from: ISO date string (e.g. "2023-01-01") — when this fact became true
        valid_until: ISO date string (e.g. "2025-12-31") — when this fact ceased to be true
        replaces: Memory ID of an older memory this one supersedes
        
    When replaces is provided, the old memory is marked as 'superseded'
    and linked via replaced_by. Conflict detection warns on overlapping
    temporal ranges for the same entity+type.
    
    Returns the created memory dict.
    """
    if mem_type not in MEMORY_TYPES:
        raise ValueError(f"Invalid memory type: {mem_type}. Must be one of {MEMORY_TYPES}")

    memories = read_memories(workspace)
    config = load_config()

    # Merge default attributes with provided ones
    default_attrs = TYPE_DEFAULTS.get(mem_type, {}).copy()
    if attributes:
        default_attrs.update(attributes)
    if tags:
        default_attrs["tags"] = tags if isinstance(tags, list) else [tags]

    # --- Temporal: handle replaces (v2.1.0) ---
    if replaces:
        # Link to old memory — mark it superseded
        for old_mem in memories:
            if old_mem["id"] == replaces and old_mem.get("status") == "active":
                old_mem["status"] = "superseded"
                old_mem["replaced_by"] = generate_id("mem")  # placeholder, will update below
                break

    # --- Temporal: conflict detection (v2.1.0) ---
    conflict = False
    if config.get("temporal", {}).get("conflict_detection", True) and valid_from:
        entity_key = (entity or "general").lower()
        for existing in memories:
            if existing.get("entity", "").lower() != entity_key:
                continue
            if existing.get("type") != mem_type:
                continue
            if existing.get("status") not in ("active", "superseded"):
                continue
            ex_from = existing.get("valid_from")
            if not ex_from:
                continue
            # Check for temporal overlap
            ex_until = existing.get("valid_until") or "9999-12-31"
            new_until = valid_until or "9999-12-31"
            if valid_from <= ex_until and new_until >= ex_from:
                if config.get("temporal", {}).get("conflict_overlap_warning", True):
                    print(f"  ⚠ Temporal overlap detected with memory {existing['id']}")
                    print(f"    Existing: {existing.get('valid_from', '?')} → {existing.get('valid_until', 'ongoing')}")
                    print(f"    New:      {valid_from} → {valid_until or 'ongoing'}")
                    print(f"    Tip: use --replaces {existing['id']} if this supersedes the old fact.")
                conflict = True
                break

    # Generate SimHash for the content
    full_text = f"{entity or ''} {content}"
    sh = simhash(full_text, config.get("simhash_bits", 64))
    
    # v3.0.0: Generate ternary hash for enhanced discrimination
    th = ternary_hash(full_text, config.get("simhash_bits", 64))

    new_id = generate_id("mem")
    memory = {
        "id": new_id,
        "timestamp": get_timestamp(),
        "type": mem_type,
        "entity": entity or "general",
        "content": content,
        "attributes": default_attrs,
        "source_session": source or "unknown",
        "confidence": confidence,
        "last_accessed": get_timestamp(),
        "access_count": 0,
        "status": "active",
        "simhash": sh,
        "ternary_hash": th,  # v3.0.0
        "related_nodes": [],
        "valid_from": valid_from,
        "valid_until": valid_until,
        "replaces": replaces,
        "replaced_by": None
    }

    # --- Temporal: update replaced_by on old memory (v2.1.0) ---
    if replaces:
        for old_mem in memories:
            if old_mem["id"] == replaces:
                old_mem["replaced_by"] = new_id
                break

    memories.append(memory)
    write_memories(memories, workspace)

    return memory


def get_memory(mem_id, workspace=None):
    """Get a single memory by ID."""
    memories = read_memories(workspace)
    for m in memories:
        if m["id"] == mem_id:
            return m
    return None


def list_memories(mem_type=None, entity=None, status="active", limit=50,
                  workspace=None, sort="time"):
    """
    List memories with optional filters.
    sort: 'time' (newest first), 'confidence' (highest first), 'access' (most accessed first)
    """
    memories = read_memories(workspace)
    filtered = memories

    if mem_type:
        filtered = [m for m in filtered if m.get("type") == mem_type]
    if entity:
        filtered = [m for m in filtered if m.get("entity", "").lower() == entity.lower()]
    if status:
        filtered = [m for m in filtered if m.get("status", "active") == status]

    # Sort
    if sort == "time":
        filtered.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
    elif sort == "confidence":
        filtered.sort(key=lambda m: m.get("confidence", 0), reverse=True)
    elif sort == "access":
        filtered.sort(key=lambda m: m.get("access_count", 0), reverse=True)

    return filtered[:limit]


def update_memory(mem_id, content=None, confidence=None, status=None,
                  attributes=None, workspace=None,
                  valid_from=None, valid_until=None):
    """
    Update an existing memory.
    v2.1.0: supports updating valid_from and valid_until temporal fields.
    Returns the updated memory or None.
    """
    memories = read_memories(workspace)
    updated = None
    for m in memories:
        if m["id"] == mem_id:
            if content is not None:
                m["content"] = content
                # Recalculate SimHash
                full_text = f"{m.get('entity', '')} {content}"
                m["simhash"] = simhash(full_text)
            if confidence is not None:
                m["confidence"] = confidence
            if status is not None:
                m["status"] = status
            if attributes is not None:
                if "attributes" not in m:
                    m["attributes"] = {}
                m["attributes"].update(attributes)
            # v2.1.0: temporal field updates
            if valid_from is not None:
                m["valid_from"] = valid_from
            if valid_until is not None:
                m["valid_until"] = valid_until
            updated = m
            break

    if updated:
        write_memories(memories, workspace)
    return updated


def delete_memory(mem_id, workspace=None):
    """Delete a memory by ID. Returns True if deleted."""
    memories = read_memories(workspace)
    original_len = len(memories)
    memories = [m for m in memories if m["id"] != mem_id]
    if len(memories) < original_len:
        write_memories(memories, workspace)
        # Also clean up graph references
        graph = read_graph(workspace)
        changed = False
        for node_id, node in graph.get("nodes", {}).items():
            if mem_id in node.get("related_memories", []):
                node["related_memories"] = [x for x in node.get("related_memories", []) if x != mem_id]
                changed = True
        for edge_id, edge in graph.get("edges", {}).items():
            if edge.get("source_memory") == mem_id:
                edge["source_memory"] = None
                changed = True
        if changed:
            write_graph(graph, workspace)
        return True
    return False


def merge_memories(id1, id2, workspace=None):
    """
    Merge two memories. The higher-confidence memory absorbs the lower one.
    Returns the merged memory or None if failed.
    """
    m1 = get_memory(id1, workspace)
    m2 = get_memory(id2, workspace)
    if not m1 or not m2:
        return None

    # Determine which absorbs which
    if m1["confidence"] >= m2["confidence"]:
        keeper, deprecated = m1, m2
    else:
        keeper, deprecated = m2, m1

    # Merge content (append if different)
    if deprecated["content"] not in keeper["content"]:
        keeper["content"] = keeper["content"] + " [merged: " + deprecated["content"] + "]"

    # Boost confidence slightly (corroboration)
    keeper["confidence"] = min(1.0, keeper["confidence"] + 0.05)

    # Merge attributes
    keeper_attrs = keeper.get("attributes", {})
    dep_attrs = deprecated.get("attributes", {})
    for k, v in dep_attrs.items():
        if k not in keeper_attrs:
            keeper_attrs[k] = v
        elif k == "tags" and isinstance(keeper_attrs[k], list):
            for tag in v if isinstance(v, list) else [v]:
                if tag not in keeper_attrs[k]:
                    keeper_attrs[k].append(tag)
    keeper["attributes"] = keeper_attrs

    # Merge related nodes
    keeper["related_nodes"] = list(set(
        keeper.get("related_nodes", []) + deprecated.get("related_nodes", [])
    ))

    # Update the keeper
    update_memory(keeper["id"], content=keeper["content"],
                  confidence=keeper["confidence"], attributes=keeper_attrs,
                  workspace=workspace)

    # Mark deprecated as archived
    update_memory(deprecated["id"], status="archived", workspace=workspace)

    return keeper


def search(query, limit=10, workspace=None):
    """
    Search memories using hybrid retrieval.
    v2.1.0: time-aware filtering — expired memories get slight score penalty.
    Returns list of results with scores.
    """
    from datetime import datetime, timezone as tz
    memories = read_memories(workspace)
    # Only search active memories
    active = [m for m in memories if m.get("status") == "active"]
    config = load_config()
    threshold = config.get("similarity_threshold", 0.15) * 0.3  # Lower threshold for search

    results = search_memories(query, active, limit=limit, similarity_threshold=threshold,
                              workspace=workspace)

    # v2.1.0: time-aware score penalty for expired facts
    now = datetime.now(tz.utc).strftime("%Y-%m-%d")
    scored_results = []
    for mem, score, match_type in results:
        valid_until = mem.get("valid_until")
        if valid_until and valid_until < now:
            # Expired — slight penalty, don't completely hide
            score = score * 0.85
        scored_results.append((mem, score, match_type))
    scored_results.sort(key=lambda x: x[1], reverse=True)

    # Update access counts for returned memories
    if scored_results:
        all_memories = read_memories(workspace)
        result_ids = {r[0]["id"] for r in scored_results}
        now_ts = get_timestamp()
        for m in all_memories:
            if m["id"] in result_ids:
                m["access_count"] = m.get("access_count", 0) + 1
                m["last_accessed"] = now_ts
        write_memories(all_memories, workspace)

    return scored_results[:limit]


def get_context(query, limit=5, workspace=None, min_score=None):
    """
    Get relevant context for a query.
    v2.1.0: supports min_score for dynamic threshold override;
    includes valid_from/valid_until in output for temporal awareness.
    Returns a compressed summary suitable for injection into conversation context.
    Uses Token optimization: structured format instead of full memory dumps.
    """
    results = search(query, limit=max(limit * 2, 20), workspace=workspace)  # Fetch more for filtering
    if not results:
        return {"memories": [], "summary": "No relevant memories found."}

    context_memories = []
    for mem, score, match_type in results:
        # v2.1.0: apply min_score filter if provided
        if min_score is not None and score < min_score:
            continue
        entry = {
            "id": mem["id"],
            "type": mem["type"],
            "entity": mem["entity"],
            "content": mem["content"],
            "confidence": mem["confidence"],
            "score": round(score, 3),
            "match": match_type,
            "timestamp": mem["timestamp"][:10]  # Date only for brevity
        }
        # v2.1.0: include temporal validity if present
        if mem.get("valid_from"):
            entry["valid_from"] = mem["valid_from"]
        if mem.get("valid_until"):
            entry["valid_until"] = mem["valid_until"]
        if mem.get("replaces"):
            entry["replaces"] = mem["replaces"]
        context_memories.append(entry)
        if len(context_memories) >= limit:
            break

    # Generate structured summary
    entities = list(set(m["entity"] for m in context_memories))
    types = list(set(m["type"] for m in context_memories))
    expired = [m for m in context_memories if m.get("valid_until") and m["valid_until"] < __import__("datetime").datetime.now().strftime("%Y-%m-%d")]

    summary_parts = [f"Found {len(context_memories)} relevant memories"]
    if expired:
        summary_parts.append(f"({len(expired)} may be expired)")
    summary_parts.append(f"(entities: {', '.join(entities[:5])}; types: {', '.join(types)})")

    return {
        "memories": context_memories,
        "summary": " ".join(summary_parts),
        "token_optimized": True,
        "temporal_aware": True
    }


def find_issues(workspace=None):
    """Find potential issues: duplicates and contradictions."""
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]

    dups = find_duplicates(active)
    # Contradictions are heuristic - just find high-similarity same-entity memories
    from sb_search import find_contradictions
    contradictions = []
    seen_pairs = set()
    for m in active:
        candidates = find_contradictions(m, active, threshold=0.6)
        for other_id, sim in candidates:
            pair = tuple(sorted([m["id"], other_id]))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                contradictions.append({
                    "memory1": m["id"],
                    "memory2": other_id,
                    "similarity": round(sim, 3),
                    "entity": m["entity"],
                    "content1": m["content"][:80],
                    "content2": next((x["content"][:80] for x in active if x["id"] == other_id), "")
                })

    return {
        "duplicates": [{"id1": d[0], "id2": d[1], "similarity": round(d[2], 3)} for d in dups],
        "potential_contradictions": contradictions
    }


def get_stats(workspace=None):
    """Get memory statistics. v2.1.0: includes temporal stats."""
    from datetime import datetime, timezone as tz
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    archived = [m for m in memories if m.get("status") == "archived"]
    superseded = [m for m in memories if m.get("status") == "superseded"]

    # Type distribution
    type_dist = {}
    for m in active:
        t = m.get("type", "unknown")
        type_dist[t] = type_dist.get(t, 0) + 1

    # Entity distribution
    entity_dist = {}
    for m in active:
        e = m.get("entity", "general")
        entity_dist[e] = entity_dist.get(e, 0) + 1

    # Average confidence
    avg_conf = sum(m.get("confidence", 0) for m in active) / len(active) if active else 0

    # Most accessed
    by_access = sorted(active, key=lambda m: m.get("access_count", 0), reverse=True)[:5]

    # v2.1.0: temporal stats
    now = datetime.now(tz.utc).strftime("%Y-%m-%d")
    with_temporal = [m for m in active if m.get("valid_from")]
    expired_active = [m for m in active if m.get("valid_until") and m["valid_until"] < now]
    chain_linked = [m for m in active if m.get("replaces")]

    return {
        "total": len(memories),
        "active": len(active),
        "archived": len(archived),
        "superseded": len(superseded),
        "type_distribution": type_dist,
        "top_entities": dict(sorted(entity_dist.items(), key=lambda x: x[1], reverse=True)[:10]),
        "avg_confidence": round(avg_conf, 3),
        "most_accessed": [{"id": m["id"], "content": m["content"][:60], "accesses": m.get("access_count", 0)} for m in by_access],
        "temporal": {
            "with_temporal_info": len(with_temporal),
            "expired_but_active": len(expired_active),
            "chain_linked": len(chain_linked)
        },
        "v3": {
            "with_ternary_hash": sum(1 for m in active if m.get("ternary_hash") is not None),
            "auto_stored": sum(1 for m in active if m.get("attributes", {}).get("auto_ingested")),
            "with_category": sum(1 for m in active if m.get("attributes", {}).get("content_category"))
        }
    }


# ===================================================================
# v3.0.0: Auto-Store (自动存储重要信息)
# ===================================================================

def auto_store(text, source_session=None, workspace=None):
    """
    Automatically detect and store important information from text.
    
    This is the "对话即入库" entry point for the memory engine.
    It uses the perception module to decide what to store, and the
    pipeline module to classify it for differential retention.
    
    Returns: dict with stored memories and metadata
    """
    from sb_perception import should_learn_or_query
    from sb_pipeline import classify_content
    from sb_reasoning import extract_key_points
    
    # Perception: should we learn or query?
    perception = should_learn_or_query(text, workspace)
    
    if perception["decision"] == "skip":
        return {"action": "skipped", "reason": perception["reasoning"], "stored": []}
    
    if perception["decision"] == "query":
        results = search(text, limit=3, workspace=workspace)
        return {
            "action": "queried", 
            "reason": perception["reasoning"],
            "found": len(results),
            "results": [{"id": m["id"], "content": m["content"][:80]} for m, _, _ in results]
        }
    
    # Extract key points
    key_points = extract_key_points(text, max_points=3)
    classification = classify_content(text)
    
    stored = []
    points_to_store = key_points if key_points else [{"sentence": text[:300], "type": "contextual"}]
    
    for point in points_to_store:
        # v3.1.0: Anti-pollution check before storing
        inferred_type = _infer_type(point.get("type", "contextual"), classification["category"])
        stored_confidence = min(0.95, perception["value"] + 0.1)
        
        pollution = anti_pollution_check(
            content=point["sentence"],
            mem_type=inferred_type,
            confidence=stored_confidence,
            workspace=workspace
        )
        
        if pollution["action"] == "skip":
            continue  # Don't store pollution
        
        if pollution["action"] == "increment":
            increment_memory_counter(pollution["increment_target"], workspace)
            stored.append({
                "id": pollution["increment_target"],
                "content": point["sentence"][:80],
                "type": inferred_type,
                "category": classification["category"],
                "action": "incremented",
                "similarity": pollution.get("similarity", 0)
            })
            continue
        
        # Clean: store normally
        memory = add_memory(
            content=point["sentence"],
            mem_type=inferred_type,
            entity=_guess_entity(point["sentence"]),
            confidence=stored_confidence,
            source=source_session or "auto_store",
            attributes={
                "content_category": classification["category"],
                "perception_decision": perception["decision"],
                "auto_ingested": True,
                "point_type": point.get("type", "contextual")
            },
            workspace=workspace
        )
        stored.append({
            "id": memory["id"],
            "content": point["sentence"][:80],
            "type": memory["type"],
            "category": classification["category"],
            "action": "stored"
        })
    
    return {
        "action": "stored",
        "reason": perception["reasoning"],
        "stored": stored,
        "stored_count": len(stored),
        "classification": classification["category"]
    }


def _infer_type(point_type, category):
    """Infer memory type from point type and content category."""
    type_map = {
        "causal": "decision",
        "factual": "fact",
        "definitional": "fact",
        "contextual": "context"
    }
    return type_map.get(point_type, "context")


# ===================================================================
# v3.1.0: Anti-Pollution Rules (反污染规则)
# ===================================================================

# Patterns that indicate unresolved errors (should NOT be stored)
UNRESOLVED_ERROR_PATTERNS = [
    r'(?:报错|出错|失败|异常|错误|bug|error|fail|crash)',
    r'(?:不知道怎么|搞不定|没解决|未解决|不行|不行了)',
    r'(?:试了.*不行|试过.*没用|怎么都.*不了)',
    r'(?:还在找|还在查|还没|尚未|仍未)',
]

# Patterns that indicate a RESOLVED error (can be stored)
RESOLVED_ERROR_PATTERNS = [
    r'(?:解决了|修好了|搞定|修复了|弄好了|成功了)',
    r'(?:原来是|root cause|根本原因)',
    r'(?:解决方法|解决方案|fix|resolve|workaround)',
]

# Patterns that indicate dead-end exploration (transient, should skip)
DEAD_END_PATTERNS = [
    r'(?:试一下|试试看|先看看|看看能不能)',
    r'(?:或许可以|可能可以|大概可以|不确定)',
    r'(?:临时|暂定|先这样|凑合)',
]


def anti_pollution_check(content, mem_type=None, confidence=0.0, workspace=None):
    """
    v3.1.0: Check if a memory should be stored or is pollution.
    
    Rules:
    1. Decision-type + confidence < 0.7 → SKIP (likely dead-end exploration)
    2. Unresolved error → SKIP (only store resolved errors)
    3. Near-duplicate (SimHash distance < threshold) → INCREMENT counter
    4. Dead-end pattern → SKIP
    
    Returns:
        dict with:
        - action: "store" | "skip" | "increment"
        - reason: str
        - increment_target: memory id (if action == "increment")
    """
    # Rule 1: Low-confidence decisions
    if mem_type == "decision" and confidence < 0.7:
        return {
            "action": "skip",
            "reason": f"Low-confidence decision (confidence={confidence:.2f} < 0.7), likely dead-end exploration"
        }
    
    # Rule 2: Unresolved errors
    content_lower = content.lower()
    has_error = any(re.search(p, content_lower) for p in UNRESOLVED_ERROR_PATTERNS)
    has_resolution = any(re.search(p, content_lower) for p in RESOLVED_ERROR_PATTERNS)
    if has_error and not has_resolution:
        return {
            "action": "skip",
            "reason": "Unresolved error detected, only resolved errors should be stored"
        }
    
    # Rule 3: Dead-end exploration patterns
    has_dead_end = any(re.search(p, content_lower) for p in DEAD_END_PATTERNS)
    if has_dead_end and confidence < 0.75:
        return {
            "action": "skip",
            "reason": "Dead-end exploration pattern detected with low confidence"
        }
    
    # Rule 4: Near-duplicate detection (SimHash-based)
    try:
        content_sh = simhash(content)
        memories = read_memories(workspace)
        active = [m for m in memories if m.get("status") == "active"]
        best_match = None
        best_sim = 0.0
        for m in active:
            if m.get("simhash"):
                similarity = simhash_similarity(content_sh, m["simhash"])
                if similarity > best_sim:
                    best_sim = similarity
                    best_match = m
        
        # Very high similarity → increment counter instead of creating new
        if best_sim >= 0.92 and best_match:
            return {
                "action": "increment",
                "reason": f"Near-duplicate detected (SimHash similarity={best_sim:.3f}), incrementing counter",
                "increment_target": best_match["id"],
                "similarity": round(best_sim, 3)
            }
    except Exception:
        pass  # If dedup fails, proceed with store
    
    return {"action": "store", "reason": "Passed all anti-pollution checks"}


def simhash_similarity(h1, h2):
    """Calculate SimHash similarity (0.0-1.0) via Hamming distance."""
    if h1 == 0 or h2 == 0:
        return 0.0
    xor = h1 ^ h2
    distance = bin(xor).count('1')
    return 1.0 - (distance / 64.0)


def increment_memory_counter(mem_id, workspace=None):
    """
    Increment access/repetition counter on an existing memory.
    Instead of creating a duplicate, update the existing memory's
    access_count and last_accessed timestamp.
    """
    memories = read_memories(workspace)
    for m in memories:
        if m["id"] == mem_id:
            m["access_count"] = m.get("access_count", 0) + 1
            m["last_accessed"] = get_timestamp()
            # v3.1.0: record observation sessions
            sessions = m.get("attributes", {}).get("sessions_observed", 1)
            if "attributes" not in m:
                m["attributes"] = {}
            m["attributes"]["sessions_observed"] = sessions + 1
            write_memories(memories, workspace)
            return {"incremented": True, "memory_id": mem_id, "new_count": m["access_count"]}
    return {"incremented": False, "reason": "Memory not found"}


def _guess_entity(text):
    """Guess the primary entity from text content."""
    # Chinese entity patterns
    cn_match = re.findall(r'[\u4e00-\u9fff]{2,}(?:项目|系统|模块|引擎|框架|平台|服务|技能|超脑)', text)
    if cn_match:
        return cn_match[0]
    
    # English entity patterns
    en_match = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)+', text)
    if en_match:
        return en_match[0]
    
    # Technical terms
    tech_match = re.findall(r'\b(?:API|HTTP|JSON|React|Vue|Python|Node|Docker|SimHash|TF-IDF)\b', text)
    if tech_match:
        return tech_match[0]
    
    return "general"


# ===================================================================
# v3.0.0: Fuzzy Query Correction (错别字/用词纠偏)
# ===================================================================

def fuzzy_correct_query(query, workspace=None):
    """
    Correct typos and wording issues in a query.
    
    Uses Levenshtein distance to find the closest matching tokens
    from the memory store, correcting user input before search.
    
    Also uses the expression profile to recognize user-specific
    phrasings and map them to standard forms.
    
    Returns: dict with corrected query and correction details
    """
    if not query:
        return {"corrected": query, "corrections": [], "original": query}
    
    query_tokens = tokenize(query)
    if not query_tokens:
        return {"corrected": query, "corrections": [], "original": query}
    
    # Build vocabulary from memories
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    vocab = set()
    for m in active:
        vocab.update(tokenize(m.get("content", "") + " " + m.get("entity", "")))
    
    # Also check expression profile
    profile = get_expression_profile(workspace)
    for std, variants in profile.get("expression_map", {}).items():
        vocab.add(std)
        vocab.update(variants)
    
    if not vocab:
        return {"corrected": query, "corrections": [], "original": query}
    
    corrections = []
    corrected_tokens = list(query_tokens)
    
    for i, token in enumerate(query_tokens):
        if token in vocab:
            continue  # Token exists in vocabulary, no correction needed
        
        # Find closest match in vocabulary
        best_match = None
        best_sim = 0.0
        max_dist = max(1, len(token) // 3)
        
        for vocab_token in vocab:
            if abs(len(vocab_token) - len(token)) > max_dist + 1:
                continue
            
            is_match, sim = fuzzy_match(token, vocab_token, max_distance=max_dist)
            if is_match and sim > best_sim:
                best_sim = sim
                best_match = vocab_token
        
        if best_match and best_sim > 0.7:
            corrected_tokens[i] = best_match
            corrections.append({
                "original": token,
                "corrected": best_match,
                "similarity": round(best_sim, 3)
            })
    
    # Also check expression profile for phrase-level corrections
    for std_form, variants in profile.get("expression_map", {}).items():
        for variant in variants:
            if variant in query.lower():
                # Replace variant with standard form
                corrected_query = re.sub(re.escape(variant), std_form, query, flags=re.IGNORECASE)
                if corrected_query != query:
                    corrections.append({
                        "original": variant,
                        "corrected": std_form,
                        "similarity": 1.0,
                        "type": "expression"
                    })
                    query = corrected_query
    
    # Rebuild corrected query from tokens if token-level corrections were made
    if any(c["type"] != "expression" for c in corrections):
        # Simple reconstruction: replace corrected tokens in original query
        corrected_query = query
        for correction in corrections:
            if correction["type"] != "expression":
                corrected_query = corrected_query.replace(correction["original"], correction["corrected"])
    else:
        corrected_query = query
    
    return {
        "corrected": corrected_query,
        "corrections": corrections,
        "original": query,
        "correction_count": len(corrections)
    }


# ===================================================================
# v3.0.0: Expression Learning (学习用户表达习惯)
# ===================================================================

def learn_expression(user_input, standard_form=None, workspace=None):
    """
    Learn a user's expression pattern.
    
    When a user consistently uses a specific phrase or wording,
    this function records the mapping so future queries using
    the same phrasing can be understood correctly.
    
    Args:
        user_input: The user's actual phrasing
        standard_form: The standard/canonical form (if known)
                       If None, the user_input itself becomes a known expression
        workspace: workspace name
    
    Returns: dict with learning result
    """
    ws_dir = ensure_workspace(workspace)
    profile_path = os.path.join(ws_dir, "expression_profile.json")
    profile = read_json(profile_path) or {
        "expression_map": {},      # standard_form -> [variants]
        "token_frequency": {},     # token -> count
        "phrase_patterns": {},     # pattern -> count
        "total_learned": 0,
        "last_updated": None
    }
    
    if standard_form:
        # Map user input to standard form
        if standard_form not in profile["expression_map"]:
            profile["expression_map"][standard_form] = []
        
        if user_input not in profile["expression_map"][standard_form]:
            profile["expression_map"][standard_form].append(user_input)
    else:
        # Just record the expression as known
        tokens = tokenize(user_input)
        for token in tokens:
            profile["token_frequency"][token] = profile["token_frequency"].get(token, 0) + 1
        
        # Detect phrase patterns (2-3 token sequences)
        for i in range(len(tokens) - 1):
            bigram = tokens[i] + " " + tokens[i + 1]
            profile["phrase_patterns"][bigram] = profile["phrase_patterns"].get(bigram, 0) + 1
    
    profile["total_learned"] += 1
    profile["last_updated"] = get_timestamp()
    
    write_json(profile_path, profile)
    
    return {
        "learned": True,
        "standard_form": standard_form,
        "user_input": user_input,
        "total_expressions": len(profile["expression_map"]),
        "total_tokens": len(profile["token_frequency"])
    }


def get_expression_profile(workspace=None):
    """
    Get the user's expression profile for a workspace.
    
    Returns: dict with expression_map, token_frequency, phrase_patterns
    """
    ws_dir = ensure_workspace(workspace)
    profile_path = os.path.join(ws_dir, "expression_profile.json")
    profile = read_json(profile_path)
    if not profile:
        return {
            "expression_map": {},
            "token_frequency": {},
            "phrase_patterns": {},
            "total_learned": 0,
            "last_updated": None
        }
    return profile


def search_with_correction(query, limit=10, workspace=None):
    """
    Search with automatic typo/wording correction.
    
    This wraps the standard search function with fuzzy correction:
    1. Correct the query using expression profile + vocabulary
    2. Search with corrected query
    3. Also search with original query (fallback)
    4. Merge and deduplicate results
    
    Returns: list of (memory, score, match_type) tuples
    """
    # Correct the query
    correction_result = fuzzy_correct_query(query, workspace)
    corrected_query = correction_result["corrected"]
    
    # Search with corrected query
    results = search(corrected_query, limit=limit, workspace=workspace)
    
    # If corrections were made, also search with original query
    if correction_result["corrections"]:
        original_results = search(query, limit=limit, workspace=workspace)
        
        # Merge: add original results that aren't already in corrected results
        existing_ids = {r[0]["id"] for r in results}
        for mem, score, match_type in original_results:
            if mem["id"] not in existing_ids:
                results.append((mem, score * 0.8, "fuzzy_corrected"))  # Slight penalty
                existing_ids.add(mem["id"])
        
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:limit]
    
    return results
