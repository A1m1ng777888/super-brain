#!/usr/bin/env python3
"""
SuperBrain Reasoning Engine v3.0.0
Auto-extracts key data points, organizes logical relationships, and derives conclusions.

The reasoning engine provides structured analysis capabilities:
- extract_key_points: Identify the most important information in text
- analyze_logic: Map cause-effect relationships and logical structure
- derive_conclusion: Synthesize multiple memories into conclusions
- assist_decision: Provide structured decision support

All reasoning is rule-based and deterministic (no LLM calls), making it
fast, predictable, and zero-cost in terms of tokens.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, read_graph, read_meta, update_meta
from sb_search import tokenize, tf_idf_cosine_similarity, keyword_match_score
from sb_graph import find_node, query_graph


# v3.1.0: Cold start gating thresholds
WARMUP_MEMORY_THRESHOLD = 15      # Min active memories needed
WARMUP_SESSION_THRESHOLD = 3      # Min sessions needed


def check_warmup_mode(workspace=None):
    """
    v3.1.0: Check if the system is still in cold start (warmup) mode.
    
    In warmup mode, only perception + storage are active.
    Reasoning, entanglement, and pattern extraction are disabled
    until enough data has accumulated.
    
    Returns:
        dict with:
        - mode: "warmup" | "active"
        - memory_count: int
        - session_count: int
        - ready: bool
        - missing: list of what's still needed
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    memory_count = len(active)
    
    meta = read_meta(workspace)
    session_count = meta.get("session_count", 0)
    
    missing = []
    if memory_count < WARMUP_MEMORY_THRESHOLD:
        missing.append(f"need {WARMUP_MEMORY_THRESHOLD - memory_count} more memories")
    if session_count < WARMUP_SESSION_THRESHOLD:
        missing.append(f"need {WARMUP_SESSION_THRESHOLD - session_count} more sessions")
    
    ready = not bool(missing)
    
    if ready and meta.get("mode") != "active":
        update_meta("mode", "active", workspace)
    elif not ready and meta.get("mode") != "warmup":
        update_meta("mode", "warmup", workspace)
    
    return {
        "mode": "active" if ready else "warmup",
        "memory_count": memory_count,
        "session_count": session_count,
        "thresholds": {
            "memory": WARMUP_MEMORY_THRESHOLD,
            "session": WARMUP_SESSION_THRESHOLD
        },
        "ready": ready,
        "missing": missing if missing else None
    }


def _is_warmup(workspace=None):
    """Quick warmup check for internal gating."""
    result = check_warmup_mode(workspace)
    return result["mode"] == "warmup"


# Causal patterns (cause → effect)
CAUSE_PATTERNS = [
    (r'(.+?)因为(.+)', 'cause', 'reversed'),      # A因为B → B causes A
    (r'(.+?)所以(.+)', 'effect', 'forward'),       # A所以B → A causes B
    (r'(.+?)由于(.+)', 'cause', 'reversed'),       # A由于B → B causes A
    (r'(.+?)导致(.+)', 'effect', 'forward'),       # A导致B → A causes B
    (r'(.+?)引起(.+)', 'effect', 'forward'),       # A引起B → A causes B
    (r'(.+?)使得(.+)', 'effect', 'forward'),       # A使得B → A causes B
    (r'(.+?)因此(.+)', 'effect', 'forward'),       # A因此B → A causes B
    (r'(.+?)从而(.+)', 'effect', 'forward'),       # A从而B → A causes B
    (r'because\s+(.+?),\s*(.+)', 'cause', 'reversed'),
    (r'(.+?)\s+therefore\s+(.+)', 'effect', 'forward'),
    (r'(.+?)\s+causes?\s+(.+)', 'effect', 'forward'),
    (r'(.+?)\s+leads to\s+(.+)', 'effect', 'forward'),
]

# Condition patterns
CONDITION_PATTERNS = [
    r'(?:如果|假如|假设|若|当)(.+?)(?:则|那么|就|，)',
    r'(?:if|when|whenever)\s+(.+?)(?:then|,)',
]

# Contrast patterns
CONTRAST_PATTERNS = [
    r'(?:但是|但|然而|不过|虽然)(.+)',
    r'(?:but|however|although|though)\s+(.+)',
]


def extract_key_points(text, max_points=5):
    """
    Extract the most important information from text.
    
    Uses a multi-signal approach:
    1. Sentence segmentation (split by punctuation)
    2. Information density scoring per sentence
    3. Position weighting (first/last sentences get boost)
    4. Keyword density (terms with high TF-IDF weight)
    5. Entity detection (named entities, numbers, technical terms)
    
    Returns: list of {sentence, score, type} dicts, sorted by importance
    """
    if not text or len(text.strip()) < 5:
        return []
    
    # Sentence segmentation
    sentences = re.split(r'[。！？.!?；;\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 2]
    
    if not sentences:
        return []
    
    # Tokenize full text for TF-IDF baseline
    all_tokens = tokenize(text)
    token_freq = Counter(all_tokens)
    total_tokens = max(len(all_tokens), 1)
    
    key_points = []
    for i, sent in enumerate(sentences):
        sent_tokens = tokenize(sent)
        if not sent_tokens:
            continue
        
        # Signal 1: Information density (unique tokens / total tokens)
        unique_ratio = len(set(sent_tokens)) / max(len(sent_tokens), 1)
        
        # Signal 2: Keyword density (high-frequency tokens from full text)
        keyword_density = sum(token_freq[t] for t in set(sent_tokens)) / total_tokens
        
        # Signal 3: Position weighting
        position_score = 1.0
        if i == 0:
            position_score = 1.2  # First sentence boost
        elif i == len(sentences) - 1:
            position_score = 1.1  # Last sentence boost
        elif i > 3:
            position_score = 0.8  # Later sentences penalty
        
        # Signal 4: Entity detection
        has_numbers = bool(re.search(r'\d+', sent))
        has_technical = bool(re.search(r'[A-Z]{2,}|[a-z]+_[a-z]+|API|HTTP|JSON', sent))
        has_named = bool(re.search(r'[\u4e00-\u9fff]{2,}[A-Z]|[A-Z][\u4e00-\u9fff]+', sent))
        entity_score = sum([0.15 if has_numbers else 0,
                           0.15 if has_technical else 0,
                           0.1 if has_named else 0])
        
        # Signal 5: Length factor (longer sentences tend to carry more info)
        length_factor = min(1.0, len(sent) / 80)
        
        # Signal 6: Causal/conditional structure bonus
        structure_bonus = 0.0
        for pattern, _, _ in CAUSE_PATTERNS:
            if re.search(pattern, sent):
                structure_bonus += 0.2
                break
        for pattern in CONDITION_PATTERNS:
            if re.search(pattern, sent):
                structure_bonus += 0.15
                break
        
        # Combined score
        score = (unique_ratio * 0.25 +
                 keyword_density * 0.25 +
                 position_score * 0.15 +
                 entity_score * 0.15 +
                 length_factor * 0.1 +
                 structure_bonus * 0.1)
        
        # Determine point type
        if structure_bonus > 0:
            point_type = "causal"
        elif entity_score > 0.2:
            point_type = "factual"
        elif unique_ratio > 0.7:
            point_type = "definitional"
        else:
            point_type = "contextual"
        
        key_points.append({
            "sentence": sent,
            "score": round(score, 3),
            "type": point_type,
            "position": i
        })
    
    key_points.sort(key=lambda x: x["score"], reverse=True)
    return key_points[:max_points]


def analyze_logic(text):
    """
    Analyze the logical structure of text.
    
    Identifies:
    - Cause-effect relationships (A → B)
    - Conditions (if X then Y)
    - Contrasts (but, however)
    - Temporal sequences (first, then, finally)
    
    Returns: dict with logical_structure, relationships, and summary
    """
    if not text:
        return {"relationships": [], "structure": "empty", "summary": "No content to analyze"}
    
    relationships = []
    
    # Extract cause-effect relationships
    for pattern, rel_type, direction in CAUSE_PATTERNS:
        matches = re.finditer(pattern, text)
        for m in matches:
            if direction == 'forward':
                cause = m.group(1).strip()
                effect = m.group(2).strip()
            else:  # reversed
                cause = m.group(2).strip()
                effect = m.group(1).strip()
            
            if cause and effect and len(cause) > 1 and len(effect) > 1:
                relationships.append({
                    "type": "cause_effect",
                    "cause": cause[:100],
                    "effect": effect[:100],
                    "direction": direction
                })
    
    # Extract conditions
    for pattern in CONDITION_PATTERNS:
        matches = re.finditer(pattern, text)
        for m in matches:
            condition = m.group(1).strip()
            if condition and len(condition) > 1:
                relationships.append({
                    "type": "condition",
                    "condition": condition[:100],
                    "text": text[text.find(m.group(0)):text.find(m.group(0)) + 100]
                })
    
    # Extract contrasts
    for pattern in CONTRAST_PATTERNS:
        matches = re.finditer(pattern, text)
        for m in matches:
            contrast = m.group(1).strip()
            if contrast and len(contrast) > 1:
                relationships.append({
                    "type": "contrast",
                    "contrast": contrast[:100]
                })
    
    # Determine overall structure
    if not relationships:
        structure = "flat"
    elif len(relationships) <= 2:
        structure = "simple"
    elif any(r["type"] == "cause_effect" for r in relationships):
        structure = "causal_chain"
    elif any(r["type"] == "condition" for r in relationships):
        structure = "conditional"
    else:
        structure = "complex"
    
    # Generate summary
    ce_count = sum(1 for r in relationships if r["type"] == "cause_effect")
    cond_count = sum(1 for r in relationships if r["type"] == "condition")
    contrast_count = sum(1 for r in relationships if r["type"] == "contrast")
    
    summary_parts = [f"{len(relationships)} logical relationships"]
    if ce_count:
        summary_parts.append(f"{ce_count} cause-effect")
    if cond_count:
        summary_parts.append(f"{cond_count} conditional")
    if contrast_count:
        summary_parts.append(f"{contrast_count} contrast")
    summary = ", ".join(summary_parts)
    
    return {
        "relationships": relationships,
        "structure": structure,
        "summary": summary,
        "relationship_count": len(relationships)
    }


def derive_conclusion(query, workspace=None, max_premises=5):
    """
    Synthesize multiple memories into a conclusion.
    
    1. Search for memories related to the query
    2. Extract key points from each memory
    3. Analyze logical relationships across memories
    4. Identify convergent (agreement) and divergent (conflict) points
    5. Generate a synthesized conclusion
    
    Returns: dict with premises, convergent_points, divergent_points, conclusion
    """
    # v3.1.0: Cold start gating
    if _is_warmup(workspace):
        return {
            "mode": "warmup",
            "conclusion": None,
            "warning": f"Reasoning engine in warmup mode. Need {WARMUP_MEMORY_THRESHOLD} memories and {WARMUP_SESSION_THRESHOLD} sessions.",
            "premises": [],
            "convergent_points": [],
            "divergent_points": []
        }
    from sb_memory import search
    results = search(query, limit=max_premises * 2, workspace=workspace)
    
    if not results:
        return {
            "premises": [],
            "convergent_points": [],
            "divergent_points": [],
            "conclusion": "No relevant memories found to derive a conclusion."
        }
    
    # Extract key points from each memory
    premises = []
    all_points = []
    
    for mem, score, match_type in results[:max_premises]:
        points = extract_key_points(mem.get("content", ""), max_points=3)
        premises.append({
            "memory_id": mem["id"],
            "entity": mem.get("entity", ""),
            "content": mem["content"][:200],
            "score": round(score, 3),
            "key_points": [p["sentence"] for p in points],
            "type": mem.get("type", "fact")
        })
        for p in points:
            all_points.append({
                "sentence": p["sentence"],
                "type": p["type"],
                "source_id": mem["id"],
                "source_entity": mem.get("entity", "")
            })
    
    # Find convergent points (similar sentences from different memories)
    convergent = []
    divergent = []
    
    for i in range(len(all_points)):
        for j in range(i + 1, len(all_points)):
            if all_points[i]["source_id"] == all_points[j]["source_id"]:
                continue
            sim = tf_idf_cosine_similarity(all_points[i]["sentence"], all_points[j]["sentence"])
            if sim > 0.5:
                convergent.append({
                    "point1": all_points[i]["sentence"][:100],
                    "point2": all_points[j]["sentence"][:100],
                    "similarity": round(sim, 3),
                    "entities": [all_points[i]["source_entity"], all_points[j]["source_entity"]]
                })
            elif 0.2 < sim < 0.4 and all_points[i]["source_entity"] == all_points[j]["source_entity"]:
                # Same entity, different content — potential divergence
                divergent.append({
                    "point1": all_points[i]["sentence"][:100],
                    "point2": all_points[j]["sentence"][:100],
                    "similarity": round(sim, 3),
                    "entity": all_points[i]["source_entity"]
                })
    
    # Generate conclusion
    if convergent:
        conclusion = f"Based on {len(premises)} memories, found {len(convergent)} convergent points. "
        conclusion += "Multiple sources agree on: " + "; ".join(c["point1"][:60] for c in convergent[:3])
    elif divergent:
        conclusion = f"Based on {len(premises)} memories, found {len(divergent)} potential divergent points. "
        conclusion += "Sources disagree on aspects of: " + divergent[0]["entity"]
    else:
        conclusion = f"Based on {len(premises)} memories, key points extracted but no strong convergence or divergence detected."
    
    return {
        "premises": premises,
        "convergent_points": convergent[:10],
        "divergent_points": divergent[:10],
        "conclusion": conclusion,
        "premise_count": len(premises)
    }


def assist_decision(options, criteria=None, workspace=None):
    """
    Provide structured decision support.
    
    Args:
        options: list of option strings to evaluate
        criteria: list of evaluation criteria (default: novelty, feasibility, impact)
        workspace: workspace for memory lookups
    
    Returns: dict with scored options and recommendation
    """
    # v3.1.0: Cold start gating
    if _is_warmup(workspace):
        return {
            "mode": "warmup",
            "recommendation": None,
            "warning": f"Reasoning engine in warmup mode. Need {WARMUP_MEMORY_THRESHOLD} memories and {WARMUP_SESSION_THRESHOLD} sessions.",
            "scores": []
        }
    if not options:
        return {"error": "No options provided"}
    
    if criteria is None:
        criteria = ["novelty", "feasibility", "impact", "alignment"]
    
    scored_options = []
    
    for option in options:
        scores = {}
        
        # Check memory for related info
        from sb_memory import search
        results = search(option, limit=3, workspace=workspace)
        
        # Novelty: fewer matches = more novel
        scores["novelty"] = max(0.3, 1.0 - len(results) * 0.2)
        
        # Feasibility: check if there are known constraints
        feasibility = 0.7  # Default
        for mem, score, _ in results:
            if any(w in mem.get("content", "").lower() for w in ["困难", "复杂", "问题", "风险", "difficult", "risk"]):
                feasibility -= 0.1
            if any(w in mem.get("content", "").lower() for w in ["简单", "容易", "可行", "simple", "easy", "feasible"]):
                feasibility += 0.1
        scores["feasibility"] = max(0.1, min(1.0, feasibility))
        
        # Impact: based on information value
        from sb_perception import information_value_assessment
        scores["impact"] = information_value_assessment(option)
        
        # Alignment: how well it matches existing knowledge
        if results:
            scores["alignment"] = results[0][1]  # Best match score
        else:
            scores["alignment"] = 0.5  # Neutral if no existing knowledge
        
        # Weighted total
        total = sum(scores.values()) / len(criteria)
        
        scored_options.append({
            "option": option,
            "scores": {k: round(v, 3) for k, v in scores.items()},
            "total_score": round(total, 3)
        })
    
    scored_options.sort(key=lambda x: x["total_score"], reverse=True)
    
    return {
        "options": scored_options,
        "criteria": criteria,
        "recommendation": scored_options[0]["option"] if scored_options else None,
        "reasoning": f"Top option scores highest on {', '.join(criteria)}"
    }


def get_reasoning_stats(workspace=None):
    """Get reasoning engine statistics."""
    from sb_memory import read_memories
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    # Analyze logical structure of all memories
    total_relationships = 0
    causal_memories = 0
    
    for m in active:
        logic = analyze_logic(m.get("content", ""))
        total_relationships += logic["relationship_count"]
        if logic["structure"] == "causal_chain":
            causal_memories += 1
    
    return {
        "total_memories_analyzed": len(active),
        "total_relationships_found": total_relationships,
        "causal_memories": causal_memories,
        "avg_relationships_per_memory": round(total_relationships / max(len(active), 1), 2)
    }
