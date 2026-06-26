#!/usr/bin/env python3
"""
SuperBrain Memory Engine
Memory CRUD, confidence management, merging, time-decay retrieval.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    generate_id, get_timestamp, read_memories, write_memories,
    read_graph, write_graph, update_meta, print_json, print_table,
    ensure_workspace, load_config
)
from sb_search import simhash, search_memories, find_duplicates


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
               source=None, attributes=None, tags=None, workspace=None):
    """
    Add a new memory to the store.
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

    # Generate SimHash for the content
    full_text = f"{entity or ''} {content}"
    sh = simhash(full_text, config.get("simhash_bits", 64))

    memory = {
        "id": generate_id("mem"),
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
        "related_nodes": []
    }

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
                  attributes=None, workspace=None):
    """Update an existing memory. Returns the updated memory or None."""
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
    Returns list of results with scores.
    """
    memories = read_memories(workspace)
    # Only search active memories
    active = [m for m in memories if m.get("status") == "active"]
    config = load_config()
    threshold = config.get("similarity_threshold", 0.15) * 0.3  # Lower threshold for search

    results = search_memories(query, active, limit=limit, similarity_threshold=threshold)

    # Update access counts for returned memories
    if results:
        all_memories = read_memories(workspace)
        result_ids = {r[0]["id"] for r in results}
        now = get_timestamp()
        for m in all_memories:
            if m["id"] in result_ids:
                m["access_count"] = m.get("access_count", 0) + 1
                m["last_accessed"] = now
        write_memories(all_memories, workspace)

    return results


def get_context(query, limit=5, workspace=None):
    """
    Get relevant context for a query.
    Returns a compressed summary suitable for injection into conversation context.
    Uses Token optimization: structured format instead of full memory dumps.
    """
    results = search(query, limit=limit, workspace=workspace)
    if not results:
        return {"memories": [], "summary": "No relevant memories found."}

    context_memories = []
    for mem, score, match_type in results:
        context_memories.append({
            "id": mem["id"],
            "type": mem["type"],
            "entity": mem["entity"],
            "content": mem["content"],
            "confidence": mem["confidence"],
            "score": round(score, 3),
            "match": match_type,
            "timestamp": mem["timestamp"][:10]  # Date only for brevity
        })

    # Generate structured summary
    entities = list(set(m["entity"] for m in context_memories))
    types = list(set(m["type"] for m in context_memories))

    return {
        "memories": context_memories,
        "summary": f"Found {len(context_memories)} relevant memories "
                   f"(entities: {', '.join(entities[:5])}; "
                   f"types: {', '.join(types)})",
        "token_optimized": True
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
    """Get memory statistics."""
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    archived = [m for m in memories if m.get("status") == "archived"]

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

    return {
        "total": len(memories),
        "active": len(active),
        "archived": len(archived),
        "type_distribution": type_dist,
        "top_entities": dict(sorted(entity_dist.items(), key=lambda x: x[1], reverse=True)[:10]),
        "avg_confidence": round(avg_conf, 3),
        "most_accessed": [{"id": m["id"], "content": m["content"][:60], "accesses": m.get("access_count", 0)} for m in by_access]
    }
