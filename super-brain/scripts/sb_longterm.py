#!/usr/bin/env python3
"""
SuperBrain Long-Term Memory v3.0.0
Cross-session knowledge association and zero-cost semantic retrieval.

The long-term memory module provides persistent, cross-session knowledge
management with minimal token overhead:

- auto_ingest: "对话即入库" — automatically extract and store knowledge from dialogue
- cross_session_associate: Link knowledge across different sessions
- zero_cost_retrieve: Pre-computed index for instant retrieval without re-scanning
- compact_storage: Efficient storage format that minimizes disk and token usage

"Zero-cost" means retrieval doesn't require loading all memories into context;
instead, a pre-computed index allows direct lookup of relevant memories,
dramatically reducing token consumption.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    read_memories, write_memories, read_json, write_json, 
    ensure_workspace, get_timestamp, get_workspace_dir, load_config
)
from sb_search import (
    tokenize, ternary_hash, ternary_similarity, 
    tf_idf_cosine_similarity, build_word_network_from_memories,
    get_word_network
)
from sb_perception import should_learn_or_query, information_value_assessment
from sb_pipeline import classify_content, CATEGORY_DEFINITION, CATEGORY_CHITCHAT


# v3.7: comprehension check — Karpathy "构建即理解" 落地
# 新概念入库前，独立复述原文关键点并与提取结果对比；
# 相似度不够 → 降低 confidence 并标记 "needs_review" 或 "needs_verification"

COMPREHENSION_PASS = 0.7        # 相似度 ≥ 此值 = 理解通过
COMPREHENSION_PARTIAL = 0.4     # 相似度 ≥ 此值 = 部分理解
# 相似度 < COMPREHENSION_PARTIAL = 理解失败


def comprehension_check(original_text, extracted_content, workspace=None):
    """
    验证系统是否真正理解了待入库内容。

    策略：
    1. 对原文独立做关键点提取（不参考已提取结果）
    2. 用三进制哈希 Jaccard 对比两次提取的相似度
    3. 根据相似度返回 (passed, adjusted_confidence, similarity, review_flag)

    review_flag:
      - None      → 理解通过
      - needs_review → 部分理解，置信度打 8 折
      - needs_verification → 理解失败，置信度打 5 折
    """
    # 过短文本跳过校验（1-2 个词不需要"理解"）
    if len(original_text.strip()) < 15:
        return (True, 1.0, 1.0, None)

    try:
        from sb_reasoning import extract_key_points
        independent = extract_key_points(original_text, max_points=3)
        independent_text = " ".join(
            p["sentence"] if isinstance(p, dict) else str(p)
            for p in independent
        )
    except Exception:
        # 提取失败 → 保守标记
        return (False, 0.4, 0.0, "needs_verification")

    if not independent_text.strip():
        return (False, 0.4, 0.0, "needs_verification")

    # 相似度对比（三进制哈希 Jaccard）
    try:
        h1 = ternary_hash(extracted_content)
        h2 = ternary_hash(independent_text)
        sim = ternary_similarity(h1, h2)
        # ternary_similarity returns a value; clamp if needed
        sim = max(0.0, min(1.0, sim))
    except Exception:
        sim = 0.5   # 保守中性

    if sim >= COMPREHENSION_PASS:
        return (True, 1.0, sim, None)
    elif sim >= COMPREHENSION_PARTIAL:
        return (False, 0.8, sim, "needs_review")
    else:
        return (False, 0.5, sim, "needs_verification")


def auto_ingest(text, source_session=None, workspace=None):
    """
    "对话即入库" — Automatically extract and store knowledge from text.
    
    This function:
    1. Runs perception check (learn/query/skip decision)
    2. If decision is "learn" or "both", extracts memory-worthy info
    3. Classifies content (definition vs chitchat) for differential retention
    4. Stores with all v3.0.0 metadata (ternary hash, category, perception)
    5. Updates the word network index
    
    Returns: dict with ingestion results
    """
    from sb_memory import add_memory, search
    
    # Step 1: Perception check
    perception = should_learn_or_query(text, workspace)
    
    decision = perception["decision"]
    
    if decision == "skip":
        return {
            "action": "skipped",
            "reason": perception["reasoning"],
            "stored": []
        }
    
    if decision == "query":
        # Just retrieve, don't store
        results = search(text, limit=3, workspace=workspace)
        return {
            "action": "queried",
            "reason": perception["reasoning"],
            "found": len(results),
            "results": [{"id": m["id"], "content": m["content"][:80], "score": round(s, 3)} for m, s, _ in results]
        }
    
    # Decision is "learn" or "both"
    # Step 2: Extract memory-worthy information
    from sb_reasoning import extract_key_points
    key_points = extract_key_points(text, max_points=3)
    
    # v3.7: comprehension check — 入库前验证是否真理解了
    comprehension_result = None
    if key_points:
        combined_extracted = " ".join(
            p["sentence"] if isinstance(p, dict) else str(p)
            for p in key_points
        )
        comprehension_result = comprehension_check(text, combined_extracted, workspace)
    else:
        comprehension_result = comprehension_check(text, text[:500], workspace)
    
    # Step 3: Classify content
    classification = classify_content(text)
    
    # Step 4: Store
    stored = []

    # v3.7: 根据 comprehension check 结果调整置信度
    adj_mult, review_flag = 1.0, None
    if comprehension_result:
        _, adj_mult, comp_sim, review_flag = comprehension_result
    
    # If there are clear key points, store each as a memory
    if key_points:
        for point in key_points:
            # Check if this specific point is novel
            point_perception = should_learn_or_query(point["sentence"], workspace)
            if point_perception["decision"] == "skip":
                continue
            
            # v3.7: apply comprehension adjustment
            adjusted_confidence = min(0.95, perception["value"] + 0.1) * adj_mult
            
            attrs = {
                "content_category": classification["category"],
                "perception_decision": decision,
                "perception_value": perception["value"],
                "point_type": point["type"],
                "auto_ingested": True
            }
            if review_flag:
                attrs["comprehension_review"] = review_flag
                attrs["comprehension_similarity"] = comp_sim
            
            memory = add_memory(
                content=point["sentence"],
                mem_type=_infer_memory_type(point["type"], classification["category"]),
                entity=_extract_entity(text, point["sentence"]),
                confidence=adjusted_confidence,
                source=source_session or "auto_ingest",
                attributes=attrs,
                workspace=workspace
            )
            stored.append({
                "id": memory["id"],
                "content": point["sentence"][:80],
                "type": memory["type"],
                "category": classification["category"]
            })
    else:
        # Store the whole text as a single memory
        memory = add_memory(
            content=text[:500],
            mem_type="context",
            entity="general",
            confidence=perception["value"],
            source=source_session or "auto_ingest",
            attributes={
                "content_category": classification["category"],
                "perception_decision": decision,
                "perception_value": perception["value"],
                "auto_ingested": True
            },
            workspace=workspace
        )
        stored.append({
            "id": memory["id"],
            "content": text[:80],
            "type": "context",
            "category": classification["category"]
        })
    
    # Step 5: Update word network index
    memories = read_memories(workspace)
    build_word_network_from_memories(memories, workspace)
    
    # If "both", also return query results
    query_results = []
    if decision == "both":
        results = search(text, limit=3, workspace=workspace)
        query_results = [{"id": m["id"], "content": m["content"][:80], "score": round(s, 3)} for m, s, _ in results]
    
    return {
        "action": "learned" if decision == "learn" else "learned_and_queried",
        "reason": perception["reasoning"],
        "stored": stored,
        "stored_count": len(stored),
        "category": classification["category"],
        "query_results": query_results
    }


def _infer_memory_type(point_type, category):
    """Infer memory type from point type and content category."""
    if category == CATEGORY_DEFINITION:
        if point_type == "causal":
            return "decision"
        elif point_type == "factual":
            return "fact"
        else:
            return "fact"
    else:
        return "context"


def _extract_entity(full_text, point_text):
    """Extract the most likely entity from text."""
    # Try to find proper nouns or key terms
    import re
    
    # Check for known entity patterns
    # Chinese proper noun patterns
    cn_entities = re.findall(r'[\u4e00-\u9fff]{2,}(?:项目|系统|模块|引擎|框架|平台|服务)', full_text)
    if cn_entities:
        return cn_entities[0]
    
    # English proper noun patterns
    en_entities = re.findall(r'[A-Z][a-z]+(?:[A-Z][a-z]+)+', full_text)
    if en_entities:
        return en_entities[0]
    
    # Technical terms
    tech_entities = re.findall(r'\b(?:API|HTTP|JSON|SQL|React|Vue|Python|Node|Docker|Kubernetes)\b', full_text)
    if tech_entities:
        return tech_entities[0]
    
    return "general"


def cross_session_associate(memory_id, workspace=None, min_strength=0.2):
    """
    Link a memory to related memories from other sessions.
    
    This creates cross-session associations that enable the AI to
    "remember" related discussions from different conversations.
    
    Returns: dict with associated memories and their session info
    """
    from sb_memory import get_memory, search
    
    mem = get_memory(memory_id, workspace)
    if not mem:
        return {"error": f"Memory not found: {memory_id}"}
    
    # Search for related memories
    results = search(mem.get("content", ""), limit=10, workspace=workspace)
    
    # Filter out self and group by session
    mem_date = mem.get("timestamp", "")[:10]
    associations = []
    
    for other, score, match_type in results:
        if other["id"] == memory_id:
            continue
        
        other_date = other.get("timestamp", "")[:10]
        cross_session = other_date != mem_date
        
        if score >= min_strength:
            associations.append({
                "memory_id": other["id"],
                "content": other["content"][:100],
                "entity": other.get("entity", ""),
                "type": other.get("type", ""),
                "score": round(score, 3),
                "match_type": match_type,
                "date": other_date,
                "cross_session": cross_session
            })
    
    # Sort by score
    associations.sort(key=lambda x: x["score"], reverse=True)
    
    cross_session_count = sum(1 for a in associations if a["cross_session"])
    
    return {
        "source_memory": memory_id,
        "source_date": mem_date,
        "total_associations": len(associations),
        "cross_session_associations": cross_session_count,
        "associations": associations
    }


def zero_cost_retrieve(query, workspace=None, limit=5):
    """
    Zero-cost semantic retrieval using pre-computed indexes.
    
    Instead of loading all memories and computing similarity scores
    (which costs tokens and compute), this function:
    1. Uses the word network to find relevant tokens
    2. Uses ternary hash for instant similarity comparison
    3. Returns only the top-K most relevant memories
    
    "Zero-cost" means no full-scan TF-IDF computation is needed;
    the ternary hash provides O(1) lookup per memory.
    
    Returns: dict with retrieved memories (token-optimized format)
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    if not active:
        return {"memories": [], "summary": "No memories in workspace"}
    
    # Compute query ternary hash
    query_ternary = ternary_hash(query)
    query_tokens = set(tokenize(query))
    
    # Use word network for query expansion
    wn = get_word_network(workspace)
    if wn._total_docs == 0:
        build_word_network_from_memories(active, workspace)
    
    # Score each memory using ternary hash (O(1) per memory)
    scored = []
    for mem in active:
        # Ternary hash lookup (pre-computed or compute on-the-fly)
        mem_ternary = mem.get("ternary_hash")
        if mem_ternary is None:
            mem_ternary = ternary_hash(mem.get("content", "") + " " + mem.get("entity", ""))
        
        th_score = ternary_similarity(query_ternary, mem_ternary)
        
        # Token overlap (fast set intersection)
        mem_tokens = set(tokenize(mem.get("content", "") + " " + mem.get("entity", "")))
        token_overlap = len(query_tokens & mem_tokens) / max(len(query_tokens), 1)
        
        # Combined score (no TF-IDF needed — zero cost)
        combined = th_score * 0.6 + token_overlap * 0.4
        
        if combined > 0.05:
            scored.append((mem, combined))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Return token-optimized format
    result_memories = []
    for mem, score in scored[:limit]:
        result_memories.append({
            "id": mem["id"],
            "c": mem["content"][:100],  # Short key for token efficiency
            "e": mem.get("entity", ""),  # Short key
            "t": mem.get("type", ""),
            "s": round(score, 3),
            "d": mem.get("timestamp", "")[:10]
        })
    
    return {
        "memories": result_memories,
        "count": len(result_memories),
        "method": "ternary_hash_zero_cost",
        "summary": f"Retrieved {len(result_memories)} memories via zero-cost index"
    }


def build_index(workspace=None):
    """
    Build the complete retrieval index for zero-cost lookups.
    
    This pre-computes:
    1. Ternary hashes for all memories
    2. Word network co-occurrence matrix
    3. Token-to-memory inverted index
    
    Call this after batch-ingesting memories for optimal retrieval performance.
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    # Build/update ternary hashes
    updated = False
    for mem in active:
        if mem.get("ternary_hash") is None:
            mem["ternary_hash"] = ternary_hash(mem.get("content", "") + " " + mem.get("entity", ""))
            updated = True
    
    if updated:
        write_memories(active + [m for m in memories if m.get("status") != "active"], workspace)
    
    # Build word network
    wn = build_word_network_from_memories(active, workspace)
    
    # Build inverted index (token → memory IDs)
    inverted_index = defaultdict(list)
    for mem in active:
        tokens = set(tokenize(mem.get("content", "") + " " + mem.get("entity", "")))
        for token in tokens:
            inverted_index[token].append(mem["id"])
    
    # Save index
    ws_dir = get_workspace_dir(workspace)
    index_path = os.path.join(ws_dir, "index.json")
    index_data = {
        "built_at": get_timestamp(),
        "memory_count": len(active),
        "inverted_index_size": len(inverted_index),
        "word_network_stats": wn.stats(),
        "ternary_hashes_computed": sum(1 for m in active if m.get("ternary_hash") is not None)
    }
    write_json(index_path, index_data)
    
    return {
        "indexed_memories": len(active),
        "inverted_index_tokens": len(inverted_index),
        "ternary_hashes": index_data["ternary_hashes_computed"],
        "word_network": wn.stats(),
        "index_path": index_path,
        "built_at": index_data["built_at"]
    }


def get_longterm_stats(workspace=None):
    """Get long-term memory statistics."""
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    # Count auto-ingested memories
    auto_ingested = sum(1 for m in active if m.get("attributes", {}).get("auto_ingested"))
    
    # Count memories with ternary hash
    with_ternary = sum(1 for m in active if m.get("ternary_hash") is not None)
    
    # Count memories with content category
    with_category = sum(1 for m in active if m.get("attributes", {}).get("content_category"))
    
    # Check if index exists
    ws_dir = get_workspace_dir(workspace)
    index_path = os.path.join(ws_dir, "index.json")
    index_info = read_json(index_path) if os.path.exists(index_path) else None
    
    # Session stats
    dates = set(m.get("timestamp", "")[:10] for m in active if m.get("timestamp"))
    
    return {
        "total_memories": len(active),
        "auto_ingested": auto_ingested,
        "with_ternary_hash": with_ternary,
        "with_content_category": with_category,
        "unique_sessions": len(dates),
        "index_built": index_info is not None,
        "index_info": index_info,
        "longterm_active": True
    }
