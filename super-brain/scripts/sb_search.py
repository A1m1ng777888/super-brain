#!/usr/bin/env python3
"""
SuperBrain Search Engine
SimHash fingerprinting + TF-IDF cosine similarity + keyword matching.
Pure standard library, no external dependencies.
"""

import hashlib
import math
import re
from collections import Counter

# Chinese character range for CJK tokenization
CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
# Word pattern for Latin text
WORD_PATTERN = re.compile(r'[a-zA-Z0-9_]+')
# Chinese bigram pattern
CJK_BIGRAM_PATTERN = re.compile(r'[\u4e00-\u9fff]{2}')


def tokenize(text):
    """
    Tokenize text into a list of tokens.
    Handles both Latin (word-level) and Chinese (bigram-level) text.
    """
    if not text:
        return []
    tokens = []
    # Extract Latin words
    tokens.extend(WORD_PATTERN.findall(text.lower()))
    # Extract Chinese bigrams (character pairs for better semantic matching)
    cjk_chars = CJK_PATTERN.findall(text)
    for i in range(len(cjk_chars) - 1):
        tokens.append(cjk_chars[i] + cjk_chars[i + 1])
    # Also add single Chinese characters as tokens (lower weight in practice)
    tokens.extend(cjk_chars)
    return tokens


def simhash(text, hash_bits=64):
    """
    Generate SimHash fingerprint for text.
    Returns an integer representing the fingerprint.
    """
    tokens = tokenize(text)
    if not tokens:
        return 0

    token_counts = Counter(tokens)
    v = [0] * hash_bits

    for token, weight in token_counts.items():
        # MD5 hash of token, take first hash_bits bits
        h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
        for i in range(hash_bits):
            bit = (h >> i) & 1
            if bit:
                v[i] += weight
            else:
                v[i] -= weight

    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def hamming_distance(h1, h2):
    """Calculate Hamming distance between two integer hashes."""
    return bin(h1 ^ h2).count('1')


def simhash_similarity(h1, h2, hash_bits=64):
    """Calculate similarity between two SimHash fingerprints (0.0 to 1.0)."""
    if h1 == 0 and h2 == 0:
        return 0.0
    return 1.0 - (hamming_distance(h1, h2) / hash_bits)


def jaccard_similarity(set1, set2):
    """Calculate Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    return len(intersection) / len(union) if union else 0.0


def tf_idf_cosine_similarity(text1, text2, all_docs=None):
    """
    Calculate TF-IDF cosine similarity between two texts.
    If all_docs is provided, uses it for IDF calculation.
    Otherwise, falls back to TF-only cosine similarity.
    """
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)
    if not tokens1 or not tokens2:
        return 0.0

    tf1 = Counter(tokens1)
    tf2 = Counter(tokens2)

    # Calculate IDF if we have a document collection
    idf = {}
    if all_docs:
        N = len(all_docs)
        all_terms = set(tf1.keys()) | set(tf2.keys())
        for term in all_terms:
            doc_freq = sum(1 for doc in all_docs if term in doc)
            idf[term] = math.log((N + 1) / (doc_freq + 1)) + 1
    else:
        # Without corpus, IDF = 1 for all terms
        idf = {term: 1.0 for term in set(tf1.keys()) | set(tf2.keys())}

    # Calculate TF-IDF vectors
    vec1 = {term: tf1[term] * idf.get(term, 1.0) for term in tf1}
    vec2 = {term: tf2[term] * idf.get(term, 1.0) for term in tf2}

    # Cosine similarity
    all_terms = set(vec1.keys()) | set(vec2.keys())
    dot_product = sum(vec1.get(term, 0) * vec2.get(term, 0) for term in all_terms)
    mag1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)


def keyword_match_score(query_tokens, content_tokens):
    """
    Calculate keyword match score (overlap ratio).
    Returns a score from 0.0 to 1.0.
    """
    if not query_tokens or not content_tokens:
        return 0.0
    query_set = set(query_tokens)
    content_set = set(content_tokens)
    overlap = query_set & content_set
    return len(overlap) / len(query_set) if query_set else 0.0


def search_memories(query, memories, limit=10, similarity_threshold=0.15):
    """
    Search memories using a hybrid approach:
    1. SimHash for fast candidate filtering
    2. TF-IDF cosine similarity for precise ranking
    3. Keyword matching for exact hit boosting

    Args:
        query: Search query string
        memories: List of memory dicts
        limit: Max results to return
        similarity_threshold: Minimum combined score to include

    Returns:
        List of (memory, score, match_type) tuples, sorted by score descending
    """
    if not memories or not query:
        return []

    query_tokens = tokenize(query)
    query_simhash = simhash(query)

    # Build corpus for TF-IDF
    all_docs = [tokenize(m.get("content", "")) for m in memories]

    results = []
    for i, memory in enumerate(memories):
        content = memory.get("content", "")
        entity = memory.get("entity", "")
        full_text = f"{entity} {content}"
        content_tokens = all_docs[i]

        # 1. SimHash similarity (fast, coarse)
        mem_simhash = memory.get("simhash", 0)
        if mem_simhash == 0:
            mem_simhash = simhash(full_text)
        sh_score = simhash_similarity(query_simhash, mem_simhash)

        # 2. TF-IDF cosine similarity (precise)
        tfidf_score = tf_idf_cosine_similarity(query, full_text, all_docs)

        # 3. Keyword match
        kw_score = keyword_match_score(query_tokens, content_tokens)

        # Combined score with weights
        # TF-IDF is the primary signal, keyword match boosts exact hits,
        # SimHash provides a baseline for semantic similarity
        combined = (0.5 * tfidf_score + 0.3 * kw_score + 0.2 * sh_score)

        if combined >= similarity_threshold:
            # Determine match type
            if kw_score > 0.5:
                match_type = "keyword"
            elif tfidf_score > 0.3:
                match_type = "semantic"
            else:
                match_type = "fuzzy"

            results.append((memory, combined, match_type))

    # Sort by score descending, take top N
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


def find_duplicates(memories, similarity_threshold=0.75):
    """
    Find likely duplicate memories using a two-stage approach:
    1. SimHash coarse filter (simhash_threshold=0.65) for fast candidate selection
    2. TF-IDF cosine similarity for precise duplicate confirmation (similarity_threshold)

    Returns list of (memory1_id, memory2_id, similarity) tuples.
    """
    duplicates = []
    n = len(memories)
    # Build corpus for TF-IDF
    all_docs = [tokenize(m.get("content", "")) for m in memories]

    for i in range(n):
        h1 = memories[i].get("simhash", 0)
        if h1 == 0:
            h1 = simhash(memories[i].get("content", ""))
        content1 = memories[i].get("content", "")
        for j in range(i + 1, n):
            h2 = memories[j].get("simhash", 0)
            if h2 == 0:
                h2 = simhash(memories[j].get("content", ""))
            # Stage 1: SimHash coarse filter
            sh_sim = simhash_similarity(h1, h2)
            if sh_sim < 0.65:
                continue
            # Stage 2: TF-IDF precise check
            content2 = memories[j].get("content", "")
            tfidf_sim = tf_idf_cosine_similarity(content1, content2, all_docs)
            # Use the higher of the two as the final similarity
            final_sim = max(sh_sim, tfidf_sim)
            if final_sim >= similarity_threshold:
                duplicates.append((memories[i]["id"], memories[j]["id"], final_sim))
    return duplicates


def find_contradictions(memory, all_memories, threshold=0.5):
    """
    Find memories that are semantically similar but potentially contradictory.
    Uses TF-IDF similarity to find related memories, then flags them for review.
    This is a heuristic - actual contradiction detection requires LLM reasoning.

    Returns list of (other_memory_id, similarity) tuples for review.
    """
    candidates = []
    mem_content = memory.get("content", "")
    mem_entity = memory.get("entity", "")

    for other in all_memories:
        if other["id"] == memory["id"]:
            continue
        # Only check memories with same entity
        if other.get("entity", "") != mem_entity:
            continue
        # Skip if different type (a fact and a preference aren't contradictory)
        if other.get("type", "") != memory.get("type", ""):
            continue

        sim = tf_idf_cosine_similarity(mem_content, other.get("content", ""))
        if sim >= threshold:
            candidates.append((other["id"], sim))

    return candidates
