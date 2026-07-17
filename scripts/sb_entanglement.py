#!/usr/bin/env python3
"""
SuperBrain Entanglement Field v3.0.0
Mines implicit associations between words and concepts, strengthening
word-to-word connections through search reinforcement.

The entanglement field is inspired by quantum entanglement: two concepts
may be "entangled" even if they never appear together directly, because
they share contextual signatures in the ternary hash space.

Core capabilities:
- mine_entanglement: Discover hidden associations between concepts
- reinforce_links: Strengthen connections through search feedback
- build_entanglement_field: Construct the full association matrix
- query_entanglement: Find entangled concepts for a given input

The entanglement field uses three signals:
1. Ternary hash overlap (structural similarity)
2. Co-occurrence frequency (statistical correlation)
3. Graph proximity (topological distance in knowledge graph)

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, read_graph, write_json, read_json, ensure_workspace, \
    get_timestamp, read_meta, WARMUP_MEMORY_THRESHOLD, WARMUP_SESSION_THRESHOLD  # v3.9.5 P2-9
from sb_search import (
    tokenize, ternary_hash, ternary_similarity, 
    tf_idf_cosine_similarity, WordNetwork, get_word_network,
    build_word_network_from_memories
)


def _is_entanglement_warmup(workspace=None):
    """Check if entanglement should be gated due to cold start."""
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    memory_count = len(active)
    meta = read_meta(workspace)
    session_count = meta.get("session_count", 0)
    return memory_count < WARMUP_MEMORY_THRESHOLD or session_count < WARMUP_SESSION_THRESHOLD


def mine_entanglement(concept, workspace=None, depth=2, min_strength=0.1):
    """
    Discover hidden associations for a given concept.
    
    Uses three channels:
    1. Ternary hash channel: find words with similar hash signatures
    2. Co-occurrence channel: find words that appear in same memories
    3. Graph channel: find entities connected through the knowledge graph
    
    Returns: dict with entangled concepts ranked by combined strength
    """
    # v3.1.0: Cold start gating
    if _is_entanglement_warmup(workspace):
        return {
            "mode": "warmup",
            "concept": concept,
            "entangled": [],
            "warning": "Entanglement engine in warmup (need 15+ memories, 3+ sessions)"
        }
    
    results = {
        "concept": concept,
        "ternary_entanglements": [],
        "cooccurrence_entanglements": [],
        "graph_entanglements": [],
        "combined": []
    }
    
    # Channel 1: Ternary hash entanglement
    wn = get_word_network(workspace)
    if wn._total_docs == 0:
        # Build network if not yet built
        memories = read_memories(workspace)
        build_word_network_from_memories(memories, workspace)
    
    ternary_results = wn.get_entangled_words(concept, max_results=10)
    results["ternary_entanglements"] = [
        {"concept": c, "strength": round(s, 3), "channel": "ternary"} 
        for c, s in ternary_results
    ]
    
    # Channel 2: Co-occurrence entanglement
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    concept_tokens = set(tokenize(concept))
    cooc_counter = Counter()
    
    for mem in active:
        content = mem.get("content", "") + " " + mem.get("entity", "")
        mem_tokens = set(tokenize(content))
        # If any concept token appears in this memory
        if concept_tokens & mem_tokens:
            # Count other tokens in this memory as co-occurring
            other_tokens = mem_tokens - concept_tokens
            for t in other_tokens:
                cooc_counter[t] += 1
    
    # Normalize co-occurrence scores
    max_cooc = max(cooc_counter.values()) if cooc_counter else 1
    results["cooccurrence_entanglements"] = [
        {"concept": t, "strength": round(c / max_cooc, 3), "channel": "cooccurrence", "raw_count": c}
        for t, c in cooc_counter.most_common(10)
        if c / max_cooc >= min_strength
    ]
    
    # Channel 3: Graph entanglement
    try:
        from sb_graph import query_graph, find_node
        graph_result = query_graph(concept, depth=depth, workspace=workspace)
        if "connections" in graph_result:
            results["graph_entanglements"] = [
                {
                    "concept": conn["target"] if conn["source"] == concept else conn["source"],
                    "strength": round(min(1.0, conn.get("weight", 1.0)), 3),
                    "channel": "graph",
                    "edge_type": conn["type"]
                }
                for conn in graph_result["connections"]
            ]
    except Exception:
        pass  # Graph might not have this node
    
    # Combine all channels
    combined_scores = defaultdict(lambda: {"score": 0.0, "channels": []})
    
    for ent in results["ternary_entanglements"]:
        combined_scores[ent["concept"]]["score"] += ent["strength"] * 0.4
        combined_scores[ent["concept"]]["channels"].append("ternary")
    
    for ent in results["cooccurrence_entanglements"]:
        combined_scores[ent["concept"]]["score"] += ent["strength"] * 0.35
        combined_scores[ent["concept"]]["channels"].append("cooccurrence")
    
    for ent in results["graph_entanglements"]:
        combined_scores[ent["concept"]]["score"] += ent["strength"] * 0.25
        combined_scores[ent["concept"]]["channels"].append("graph")
    
    # Sort and filter
    results["combined"] = [
        {
            "concept": concept,
            "strength": round(data["score"], 3),
            "channels": list(set(data["channels"])),
            "channel_count": len(set(data["channels"]))
        }
        for concept, data in sorted(combined_scores.items(), key=lambda x: x[1]["score"], reverse=True)
        if data["score"] >= min_strength
    ]
    
    return results


def reinforce_links(token1, token2, strength=0.1, workspace=None):
    """
    Reinforce the connection between two tokens.
    
    Called after a successful search that connects two previously
    unrelated concepts. This strengthens their entanglement for
    future queries.
    
    The reinforcement is stored in the word network's co-occurrence
    matrix, making future queries more likely to find this connection.
    """
    wn = get_word_network(workspace)
    
    # Ensure both tokens are in the network
    for token in [token1, token2]:
        if token not in wn._token_hashes:
            wn._token_hashes[token] = ternary_hash(token)
    
    # Reinforce co-occurrence (round to nearest int, floor at 1 so non-zero input always produces non-zero increment)
    wn._cooccurrence[token1][token2] += max(1, int(round(strength * 10)))
    wn._cooccurrence[token2][token1] += max(1, int(round(strength * 10)))
    
    return {
        "token1": token1,
        "token2": token2,
        "new_strength": wn._cooccurrence[token1][token2],
        "reinforced": True
    }


def build_entanglement_field(workspace=None, min_strength=0.1):
    """
    Build the complete entanglement field for a workspace.
    
    This processes all memories and constructs the full association
    matrix, computing entanglement strengths for all token pairs.
    
    Returns: dict with field statistics and top entanglements
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    # Build/update word network (rebuild from scratch to ensure completeness)
    wn = get_word_network(workspace)
    # Clear and rebuild to ensure all tokens are present
    wn._token_hashes = {}
    wn._cooccurrence = defaultdict(lambda: defaultdict(int))
    wn._total_docs = 0
    for mem in active:
        content = mem.get("content", "") + " " + mem.get("entity", "")
        wn.add_document(content)
    
    # Compute entanglement matrix
    all_tokens = list(wn._token_hashes.keys())
    entanglement_pairs = []
    
    # Only compute for top N most frequent tokens to avoid O(n^2) explosion
    token_freq = Counter()
    for mem in active:
        content = mem.get("content", "") + " " + mem.get("entity", "")
        token_freq.update(tokenize(content))
    
    # Filter to only tokens that exist in the word network
    top_tokens = [t for t, _ in token_freq.most_common(50) if t in wn._token_hashes]
    
    for i in range(len(top_tokens)):
        for j in range(i + 1, len(top_tokens)):
            t1, t2 = top_tokens[i], top_tokens[j]
            
            # Ternary hash similarity
            th_sim = ternary_similarity(wn._token_hashes[t1], wn._token_hashes[t2])
            
            # Co-occurrence
            cooc = wn._cooccurrence.get(t1, {}).get(t2, 0)
            cooc_score = min(1.0, cooc * 0.1)
            
            # Combined
            combined = th_sim * 0.5 + cooc_score * 0.5
            
            if combined >= min_strength:
                entanglement_pairs.append({
                    "token1": t1,
                    "token2": t2,
                    "strength": round(combined, 3),
                    "ternary_sim": round(th_sim, 3),
                    "cooccurrence": cooc
                })
    
    entanglement_pairs.sort(key=lambda x: x["strength"], reverse=True)
    
    return {
        "total_tokens": len(all_tokens),
        "top_tokens_analyzed": len(top_tokens),
        "entanglement_pairs_found": len(entanglement_pairs),
        "top_entanglements": entanglement_pairs[:20],
        "field_density": round(len(entanglement_pairs) / max(len(top_tokens) * (len(top_tokens) - 1) / 2, 1), 3),
        "word_network_stats": wn.stats()
    }


def query_entanglement(query, workspace=None, max_results=10):
    """
    Find entangled concepts for a query, expanding the search space.
    
    This is the retrieval-facing function: given a user query, it
    finds concepts that are entangled with the query terms, enabling
    discovery of related information the user didn't explicitly ask for.
    
    Returns: list of {concept, strength, source} dicts
    """
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    
    entangled = defaultdict(lambda: {"strength": 0.0, "sources": []})
    
    for token in query_tokens:
        # Mine entanglement for each query token
        result = mine_entanglement(token, workspace, depth=1, min_strength=0.05)
        # v3.8.7: 冷启动返回无 combined 字段，跳过
        if "combined" not in result:
            continue
        for ent in result["combined"]:
            if ent["concept"] in query_tokens:
                continue  # Skip tokens already in query
            entangled[ent["concept"]]["strength"] = max(entangled[ent["concept"]]["strength"], ent["strength"])
            entangled[ent["concept"]]["sources"].append(token)
    
    # Sort by combined strength
    results = [
        {
            "concept": concept,
            "strength": round(data["strength"], 3),
            "sources": list(set(data["sources"])),
            "source_count": len(set(data["sources"]))
        }
        for concept, data in sorted(entangled.items(), key=lambda x: x[1]["strength"], reverse=True)
    ]
    
    return results[:max_results]


def get_entanglement_stats(workspace=None):
    """Get entanglement field statistics."""
    wn = get_word_network(workspace)
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    if wn._total_docs == 0 and active:
        build_word_network_from_memories(active, workspace)
    
    wn_stats = wn.stats()
    
    # Count strong entanglements
    strong_links = 0
    total_links = 0
    for token, neighbors in wn._cooccurrence.items():
        for neighbor, count in neighbors.items():
            total_links += 1
            if count >= 3:
                strong_links += 1
    
    return {
        "word_network": wn_stats,
        "total_cooccurrence_links": total_links // 2,
        "strong_entanglements": strong_links // 2,
        "entanglement_density": round(total_links / max(wn_stats["total_tokens"] * (wn_stats["total_tokens"] - 1) / 2, 1), 4) if wn_stats["total_tokens"] > 1 else 0,
        "field_active": True
    }
