#!/usr/bin/env python3
"""
SuperBrain Context Memory v3.0.0
Auto-groups same-topic content and supports cross-window, cross-date tracing.

The context memory module solves the "context fragmentation" problem:
when a user discusses the same topic across different sessions or days,
the AI loses track of the conversation thread.

Core capabilities:
- topic_cluster: Automatically group memories by topic similarity
- trace_thread: Trace a conversation thread across sessions/dates
- cross_session_recall: Retrieve related context from other sessions
- get_topic_context: Get all memories related to a specific topic

This module creates "topic threads" — chains of memories that belong
to the same conversation topic, regardless of when they were stored.
"""

import sys
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, write_json, read_json, ensure_workspace, get_timestamp, get_workspace_dir
from sb_search import tokenize, tf_idf_cosine_similarity, ternary_hash, ternary_similarity


def topic_cluster(workspace=None, num_clusters=None, min_similarity=0.3):
    """
    Automatically group memories into topic clusters.
    
    Uses agglomerative clustering based on TF-IDF + ternary hash similarity.
    Memories in the same cluster share a common topic.
    
    Args:
        workspace: workspace name
        num_clusters: target number of clusters (if None, auto-determined)
        min_similarity: minimum similarity to merge clusters
    
    Returns: dict with clusters list and statistics
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    if not active:
        return {"clusters": [], "total_memories": 0}
    
    # Compute pairwise similarity matrix
    n = len(active)
    all_docs = [tokenize(m.get("content", "") + " " + m.get("entity", "")) for m in active]
    
    # Initialize: each memory is its own cluster
    clusters = [[i] for i in range(n)]
    
    # Compute similarity for all pairs
    sim_cache = {}
    for i in range(n):
        for j in range(i + 1, n):
            tfidf_sim = tf_idf_cosine_similarity(
                active[i].get("content", ""),
                active[j].get("content", ""),
                all_docs
            )
            h1 = active[i].get("ternary_hash") or ternary_hash(active[i].get("content", ""))
            h2 = active[j].get("ternary_hash") or ternary_hash(active[j].get("content", ""))
            th_sim = ternary_similarity(h1, h2)
            combined = tfidf_sim * 0.6 + th_sim * 0.4
            sim_cache[(i, j)] = combined
    
    # Agglomerative clustering
    while len(clusters) > 1:
        # Find most similar pair of clusters (single-linkage)
        best_sim = -1
        best_pair = None
        
        for ci in range(len(clusters)):
            for cj in range(ci + 1, len(clusters)):
                # Find max similarity between any members
                max_sim = 0
                for mi in clusters[ci]:
                    for mj in clusters[cj]:
                        key = (min(mi, mj), max(mi, mj))
                        sim = sim_cache.get(key, 0)
                        max_sim = max(max_sim, sim)
                
                if max_sim > best_sim:
                    best_sim = max_sim
                    best_pair = (ci, cj)
        
        # Stop if best similarity is too low
        if best_sim < min_similarity:
            break
        
        # Merge clusters
        ci, cj = best_pair
        clusters[ci].extend(clusters[cj])
        clusters.pop(cj)
        
        # Stop if we've reached target number of clusters
        if num_clusters and len(clusters) <= num_clusters:
            break
    
    # Build cluster results
    cluster_results = []
    for idx, member_indices in enumerate(clusters):
        if len(member_indices) == 0:
            continue
        
        members = [active[i] for i in member_indices]
        
        # Extract cluster topic (most common entity + most frequent tokens)
        entities = [m.get("entity", "") for m in members if m.get("entity")]
        entity_counts = defaultdict(int)
        for e in entities:
            entity_counts[e] += 1
        primary_entity = max(entity_counts, key=entity_counts.get) if entity_counts else "general"
        
        # Topic keywords (most frequent tokens across cluster)
        all_tokens = []
        for m in members:
            all_tokens.extend(tokenize(m.get("content", "")))
        token_freq = Counter(all_tokens)
        topic_keywords = [t for t, _ in token_freq.most_common(5) if len(t) > 1]
        
        # Date range
        dates = [m.get("timestamp", "")[:10] for m in members if m.get("timestamp")]
        date_range = f"{min(dates)} ~ {max(dates)}" if dates else "unknown"
        
        cluster_results.append({
            "cluster_id": f"topic_{idx}",
            "size": len(members),
            "primary_entity": primary_entity,
            "topic_keywords": topic_keywords,
            "date_range": date_range,
            "member_ids": [m["id"] for m in members],
            "member_summaries": [
                {"id": m["id"], "content": m["content"][:80], "timestamp": m.get("timestamp", "")[:10]}
                for m in members
            ]
        })
    
    # Sort by cluster size
    cluster_results.sort(key=lambda x: x["size"], reverse=True)
    
    # Re-number clusters
    for i, c in enumerate(cluster_results):
        c["cluster_id"] = f"topic_{i}"
    
    return {
        "clusters": cluster_results,
        "total_clusters": len(cluster_results),
        "total_memories": n,
        "silhouette_estimate": round(best_sim if 'best_sim' in dir() else 0, 3)
    }


from collections import Counter


def trace_thread(topic_or_memory_id, workspace=None, max_depth=10):
    """
    Trace a conversation thread across sessions and dates.
    
    Given a topic or memory ID, finds all related memories that form
    a conversation thread, ordered chronologically.
    
    Returns: dict with thread memories and metadata
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    # Determine starting point
    if topic_or_memory_id.startswith("mem_"):
        # Start from a specific memory
        start_mem = next((m for m in active if m["id"] == topic_or_memory_id), None)
        if not start_mem:
            return {"error": f"Memory not found: {topic_or_memory_id}"}
        seed_content = start_mem.get("content", "")
        seed_entity = start_mem.get("entity", "")
    else:
        # Start from a topic query
        seed_content = topic_or_memory_id
        seed_entity = ""
    
    # Find all memories related to the seed
    seed_tokens = set(tokenize(seed_content + " " + seed_entity))
    
    thread_members = []
    for mem in active:
        mem_tokens = set(tokenize(mem.get("content", "") + " " + mem.get("entity", "")))
        
        # Check token overlap
        overlap = seed_tokens & mem_tokens
        overlap_ratio = len(overlap) / max(len(seed_tokens), 1)
        
        # Check TF-IDF similarity
        tfidf_sim = tf_idf_cosine_similarity(seed_content, mem.get("content", ""))
        
        # Check ternary hash similarity
        h1 = ternary_hash(seed_content)
        h2 = mem.get("ternary_hash") or ternary_hash(mem.get("content", ""))
        th_sim = ternary_similarity(h1, h2)
        
        # Combined relevance
        relevance = overlap_ratio * 0.4 + tfidf_sim * 0.35 + th_sim * 0.25
        
        if relevance >= 0.15:
            thread_members.append({
                "memory": mem,
                "relevance": round(relevance, 3),
                "overlap_tokens": list(overlap)[:5]
            })
    
    # Sort chronologically
    thread_members.sort(key=lambda x: x["memory"].get("timestamp", ""))
    
    # Build thread narrative
    thread_narrative = []
    prev_date = None
    for member in thread_members:
        mem = member["memory"]
        curr_date = mem.get("timestamp", "")[:10]
        
        # Mark session breaks (different dates)
        session_break = prev_date is not None and curr_date != prev_date
        
        thread_narrative.append({
            "memory_id": mem["id"],
            "content": mem["content"][:150],
            "entity": mem.get("entity", ""),
            "type": mem.get("type", ""),
            "timestamp": mem.get("timestamp", ""),
            "date": curr_date,
            "relevance": member["relevance"],
            "session_break": session_break,
            "shared_tokens": member["overlap_tokens"]
        })
        prev_date = curr_date
    
    # Count unique sessions
    dates = set(m["date"] for m in thread_narrative if m["date"])
    
    return {
        "thread_id": f"thread_{hash(topic_or_memory_id) % 10000}",
        "seed": topic_or_memory_id[:80],
        "thread_length": len(thread_narrative),
        "session_count": len(dates),
        "date_range": f"{min(dates)} ~ {max(dates)}" if dates else "unknown",
        "narrative": thread_narrative,
        "cross_session": len(dates) > 1
    }


def cross_session_recall(query, workspace=None, days_back=None):
    """
    Retrieve related context from previous sessions.
    
    Finds memories from different dates that are relevant to the current query,
    enabling the AI to "remember" discussions from previous sessions.
    
    Args:
        query: current query/topic
        workspace: workspace name
        days_back: how many days to look back (None = all history)
    
    Returns: dict with recalled memories grouped by session
    """
    from sb_memory import search
    results = search(query, limit=20, workspace=workspace)
    
    if not results:
        return {"recalled": [], "session_count": 0}
    
    # Filter by date if specified
    if days_back:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        results = [(m, s, t) for m, s, t in results 
                   if m.get("timestamp", "")[:10] >= cutoff]
    
    # Group by date (session proxy)
    by_date = defaultdict(list)
    for mem, score, match_type in results:
        date = mem.get("timestamp", "")[:10]
        by_date[date].append({
            "memory_id": mem["id"],
            "content": mem["content"][:120],
            "entity": mem.get("entity", ""),
            "type": mem.get("type", ""),
            "score": round(score, 3),
            "match_type": match_type,
            "timestamp": mem.get("timestamp", "")
        })
    
    # Build session summary
    sessions = []
    for date in sorted(by_date.keys(), reverse=True):
        sessions.append({
            "date": date,
            "memory_count": len(by_date[date]),
            "top_memory": by_date[date][0],
            "all_memories": by_date[date]
        })
    
    return {
        "query": query[:80],
        "total_recalled": sum(len(s["all_memories"]) for s in sessions),
        "session_count": len(sessions),
        "sessions": sessions,
        "cross_session": len(sessions) > 1
    }


def get_topic_context(topic, workspace=None, limit=10):
    """
    Get all memories related to a specific topic.
    
    This is a convenience function that combines search + thread tracing
    to provide complete context for a topic.
    
    Returns: dict with topic memories, thread, and summary
    """
    # Search for topic memories
    from sb_memory import search
    results = search(topic, limit=limit, workspace=workspace)
    
    # Trace the thread
    thread = trace_thread(topic, workspace)
    
    # Build summary
    if results:
        entities = set(m.get("entity", "") for m, _, _ in results)
        types = set(m.get("type", "") for m, _, _ in results)
        summary = f"Found {len(results)} memories about '{topic}' across {len(entities)} entities"
    else:
        summary = f"No memories found about '{topic}'"
    
    return {
        "topic": topic,
        "memories": [
            {
                "id": m["id"],
                "content": m["content"][:120],
                "entity": m.get("entity", ""),
                "type": m.get("type", ""),
                "score": round(s, 3),
                "timestamp": m.get("timestamp", "")[:10]
            }
            for m, s, _ in results
        ],
        "thread": {
            "length": thread.get("thread_length", 0),
            "session_count": thread.get("session_count", 0),
            "cross_session": thread.get("cross_session", False)
        },
        "summary": summary
    }


def get_context_stats(workspace=None):
    """Get context memory statistics."""
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    # Count unique dates (sessions)
    dates = set(m.get("timestamp", "")[:10] for m in active if m.get("timestamp"))
    
    # Run topic clustering
    clustering = topic_cluster(workspace, min_similarity=0.25)
    
    return {
        "total_memories": len(active),
        "unique_sessions": len(dates),
        "topic_clusters": clustering["total_clusters"],
        "largest_cluster_size": max((c["size"] for c in clustering["clusters"]), default=0),
        "cross_session_topics": sum(1 for c in clustering["clusters"] if " ~ " in c.get("date_range", "")),
        "context_active": True
    }
