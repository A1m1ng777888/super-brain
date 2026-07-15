#!/usr/bin/env python3
"""
SuperBrain Perception Enhancement Module v3.0.0
Auto-determines whether information should be "learned" (stored) or "queried" (searched).

The perception module acts as a gatekeeper:
- Novel information (not in memory) → LEARN (store it)
- Known information (already in memory) → QUERY (retrieve and verify)
- Ambiguous information → BOTH (search first, then store if new)
- Transient information → SKIP (not worth storing)

This optimizes knowledge acquisition efficiency by avoiding redundant storage
and ensuring important new information is always captured.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, load_config
from sb_search import tokenize, search_memories, fuzzy_token_match, tf_idf_cosine_similarity
from sb_pipeline import classify_content, CATEGORY_CHITCHAT


# Perception decision types
DECISION_LEARN = "learn"       # Store this information
DECISION_QUERY = "query"       # Search for existing information
DECISION_BOTH = "both"         # Search first, then store if new
DECISION_SKIP = "skip"         # Not worth processing


def novelty_check(text, workspace=None, threshold=0.6):
    """
    Check if the given text contains novel information not already in memory.
    
    Uses semantic search to find similar existing memories.
    If best match score < threshold, the information is considered novel.
    
    Returns:
        dict with:
        - is_novel: bool
        - best_match_score: float (0.0-1.0)
        - best_match_id: str or None
        - similar_count: int (number of similar memories found)
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    if not active:
        return {
            "is_novel": True,
            "best_match_score": 0.0,
            "best_match_id": None,
            "similar_count": 0
        }
    
    results = search_memories(text, active, limit=5, dynamic_threshold=False,
                              similarity_threshold=0.1, workspace=workspace)
    
    if not results:
        return {
            "is_novel": True,
            "best_match_score": 0.0,
            "best_match_id": None,
            "similar_count": 0
        }
    
    best_mem, best_score, _ = results[0]
    similar_count = sum(1 for _, s, _ in results if s >= 0.3)
    
    return {
        "is_novel": best_score < threshold,
        "best_match_score": round(best_score, 3),
        "best_match_id": best_mem["id"] if best_score >= threshold else None,
        "similar_count": similar_count
    }


def information_value_assessment(text, context=None):
    """
    Assess the informational value of a piece of text.
    
    Factors:
    - Content category (definition > hybrid > chitchat)
    - Information density (unique tokens ratio)
    - Specificity (named entities, numbers, technical terms)
    - Actionability (contains actionable directives)
    
    Returns: float 0.0-1.0 (higher = more valuable)
    """
    if not text or len(text.strip()) < 3:
        return 0.1
    
    # Very short texts get heavy penalty (likely chitchat)
    text_len = len(text.strip())
    if text_len < 10:
        length_penalty = 0.3  # Heavy penalty for very short text
    elif text_len < 20:
        length_penalty = 0.6
    else:
        length_penalty = 1.0
    
    # Content classification
    classification = classify_content(text)
    category = classification["category"]
    
    # Category value mapping
    category_value = {
        "definition": 0.8,
        "hybrid": 0.5,
        "chitchat": 0.2
    }
    base_value = category_value.get(category, 0.5)
    
    # Information density
    tokens = tokenize(text)
    unique_ratio = len(set(tokens)) / max(len(tokens), 1)
    # Cap density score more aggressively for short texts
    density_score = min(1.0, unique_ratio * 1.2)
    
    # Specificity: check for numbers, technical terms, proper nouns
    import re
    has_numbers = bool(re.search(r'\d+', text))
    has_technical = bool(re.search(r'[A-Z][a-z]+[A-Z]|[a-z]+_[a-z]+|API|HTTP|JSON|SQL|CPU|GPU', text))
    has_chinese_terms = len([t for t in tokens if len(t) >= 2]) > 2
    specificity = sum([0.2 if has_numbers else 0, 
                       0.2 if has_technical else 0,
                       0.15 if has_chinese_terms else 0])
    
    # Actionability: check for action verbs
    # v3.9.2: 负向后行断言 + \b 词边界防否定极性误判（与 sb_reasoning pack-11 同型修复）
    action_patterns = ['需要', '应该', '必须', '创建', '配置', '安装', '部署', '修复',
                       'need', 'should', 'must', 'create', 'configure', 'install', 'fix']
    _t = text.lower()
    def _action_hit(p):
        if p.isascii():
            return bool(re.search(r'\b' + re.escape(p) + r'\b', _t))
        return bool(re.search(r'(?<![不没无])' + re.escape(p), _t))
    has_action = any(_action_hit(p) for p in action_patterns)
    action_score = 0.15 if has_action else 0.0
    
    # Combine with length penalty
    value = (base_value * 0.4 + density_score * 0.25 + specificity * 0.2 + action_score) * length_penalty
    
    # Length bonus (up to a point)
    length_bonus = min(0.1, len(text) / 500)
    
    return min(1.0, value + length_bonus)


def should_learn_or_query(text, workspace=None, context=None):
    """
    Main perception function: determine whether to learn or query.
    
    Decision logic:
    1. If text has low information value (< 0.2) → SKIP
    2. If text is pure chitchat → SKIP
    3. If text is novel (not in memory) → LEARN
    4. If text matches existing memory closely → QUERY
    5. If text is partially novel → BOTH
    
    Returns:
        dict with:
        - decision: "learn" | "query" | "both" | "skip"
        - confidence: 0.0-1.0
        - novelty: novelty_check result
        - value: information_value_assessment result
        - reasoning: str
    """
    # Step 1: Assess information value
    value = information_value_assessment(text, context)
    
    # Step 2: Classify content
    classification = classify_content(text)
    
    # Step 3: Skip low-value chitchat
    if value < 0.2 and classification["category"] == CATEGORY_CHITCHAT:
        return {
            "decision": DECISION_SKIP,
            "confidence": 0.85,
            "novelty": {"is_novel": True, "best_match_score": 0.0, "best_match_id": None, "similar_count": 0},
            "value": round(value, 3),
            "reasoning": f"Low value ({value:.2f}) chitchat content, skip storage"
        }
    
    # Step 4: Check novelty
    novelty = novelty_check(text, workspace, threshold=0.55)
    
    # Step 5: Make decision
    if novelty["is_novel"]:
        if value >= 0.5:
            decision = DECISION_LEARN
            confidence = min(0.95, value + 0.1)
            reasoning = f"Novel content (match={novelty['best_match_score']:.2f}) with high value ({value:.2f}), should learn"
        else:
            decision = DECISION_BOTH  # Search first, then store if confirmed
            confidence = 0.65
            reasoning = f"Novel content (match={novelty['best_match_score']:.2f}) with moderate value ({value:.2f}), search then learn"
    else:
        # Content exists in memory
        if novelty["best_match_score"] >= 0.8:
            decision = DECISION_QUERY
            confidence = 0.9
            reasoning = f"Content already known (match={novelty['best_match_score']:.2f}), query existing memory"
        else:
            # Partial match — might be an update or related info
            decision = DECISION_BOTH
            confidence = 0.7
            reasoning = f"Partial match (score={novelty['best_match_score']:.2f}), query and potentially update"
    
    return {
        "decision": decision,
        "confidence": round(confidence, 3),
        "novelty": novelty,
        "value": round(value, 3),
        "reasoning": reasoning
    }


def batch_perceive(messages, workspace=None):
    """
    Process a batch of messages (e.g., a conversation) and determine
    the optimal learn/query strategy for each.
    
    Returns: list of perception results, plus a summary
    """
    results = []
    learn_count = 0
    query_count = 0
    skip_count = 0
    both_count = 0
    
    for msg in messages:
        text = msg if isinstance(msg, str) else msg.get("content", "")
        result = should_learn_or_query(text, workspace)
        results.append({"text": text[:80], **result})
        
        if result["decision"] == DECISION_LEARN:
            learn_count += 1
        elif result["decision"] == DECISION_QUERY:
            query_count += 1
        elif result["decision"] == DECISION_SKIP:
            skip_count += 1
        else:
            both_count += 1
    
    return {
        "results": results,
        "summary": {
            "total": len(results),
            "learn": learn_count,
            "query": query_count,
            "both": both_count,
            "skip": skip_count,
            "efficiency": round((query_count + skip_count) / max(len(results), 1), 3)
        }
    }


def get_perception_stats(workspace=None):
    """Get perception module statistics."""
    from sb_memory import read_memories, get_stats
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    # Compute average information value
    total_value = 0
    for m in active:
        val = information_value_assessment(m.get("content", ""))
        total_value += val
    
    avg_value = total_value / max(len(active), 1)
    
    # Count by perception metadata
    learned = sum(1 for m in active if m.get("attributes", {}).get("perception_decision") == DECISION_LEARN)
    queried = sum(1 for m in active if m.get("attributes", {}).get("perception_decision") == DECISION_QUERY)
    
    return {
        "total_memories": len(active),
        "avg_information_value": round(avg_value, 3),
        "learned_via_perception": learned,
        "queried_via_perception": queried,
        "perception_active": True
    }
