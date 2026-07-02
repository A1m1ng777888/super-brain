#!/usr/bin/env python3
"""
SuperBrain Search Engine v3.0.0
Ternary Hash Word Network + SimHash + TF-IDF cosine similarity + keyword matching
+ Levenshtein fuzzy matching for typo correction.
Pure standard library, no external dependencies.

v3.0.0 additions:
- Ternary hash (三进制哈希): -1/0/+1 per position, 3^64 states vs 2^64 for binary
- Word network (字词网络): token-level entanglement graph for query expansion
- Levenshtein distance for typo-tolerant matching
- Enhanced tokenize with CJK trigram support
"""

import hashlib
import math
import re
from collections import Counter, defaultdict

# Chinese character range for CJK tokenization
CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
# Word pattern for Latin text
WORD_PATTERN = re.compile(r'[a-zA-Z0-9_]+')
# Chinese bigram pattern
CJK_BIGRAM_PATTERN = re.compile(r'[\u4e00-\u9fff]{2}')

# v3.0.0: Default hash bits for ternary system
DEFAULT_TERNARY_BITS = 64


def tokenize(text):
    """
    Tokenize text into a list of tokens.
    v3.0.0: Enhanced with CJK trigram support for better semantic capture.
    Handles both Latin (word-level) and Chinese (bigram + trigram-level) text.
    """
    if not text:
        return []
    tokens = []
    # Extract Latin words
    tokens.extend(WORD_PATTERN.findall(text.lower()))
    # Extract CJK characters
    cjk_chars = CJK_PATTERN.findall(text)
    # Chinese bigrams (character pairs)
    for i in range(len(cjk_chars) - 1):
        tokens.append(cjk_chars[i] + cjk_chars[i + 1])
    # v3.0.0: Chinese trigrams (three-character sequences) for richer semantics
    for i in range(len(cjk_chars) - 2):
        tokens.append(cjk_chars[i] + cjk_chars[i + 1] + cjk_chars[i + 2])
    # Also add single Chinese characters as tokens (lower weight in practice)
    tokens.extend(cjk_chars)
    return tokens


# ===================================================================
# v3.0.0: Ternary Hash (三进制哈希)
# ===================================================================

def ternary_hash(text, hash_bits=DEFAULT_TERNARY_BITS):
    """
    Generate a ternary hash fingerprint for text.
    
    Unlike binary SimHash (0/1 per bit), ternary hash uses three states:
    - +1: word strongly present at this position
    - -1: word strongly absent from this position  
    -  0: neutral (word doesn't influence this position)
    
    This gives 3^64 possible states (vs 2^64 for binary), dramatically
    increasing discriminative power with the same hash width.
    
    Storage: Two integers (pos_mask, neg_mask) where:
    - pos_mask has bit set where value is +1
    - neg_mask has bit set where value is -1
    - Positions in neither mask are 0 (neutral)
    
    Returns: (pos_mask, neg_mask) tuple of integers
    """
    tokens = tokenize(text)
    if not tokens:
        return (0, 0)
    
    token_counts = Counter(tokens)
    v = [0] * hash_bits
    
    for token, weight in token_counts.items():
        h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
        for i in range(hash_bits):
            bit = (h >> i) & 1
            if bit:
                v[i] += weight
            else:
                v[i] -= weight
    
    # Convert to ternary: +1 where v>0, -1 where v<0, 0 where v==0
    pos_mask = 0
    neg_mask = 0
    for i in range(hash_bits):
        if v[i] > 0:
            pos_mask |= (1 << i)
        elif v[i] < 0:
            neg_mask |= (1 << i)
    
    return (pos_mask, neg_mask)


def ternary_similarity(t1, t2, hash_bits=DEFAULT_TERNARY_BITS):
    """
    Calculate similarity between two ternary hashes.
    
    Only considers non-neutral positions (where at least one hash has a non-zero value).
    Agreement: both +1 or both -1 at the same position.
    Disagreement: one +1 and the other -1.
    
    similarity = agreement / (agreement + disagreement)
    
    Returns float 0.0 to 1.0
    """
    pos1, neg1 = t1
    pos2, neg2 = t2
    
    # Agreement: both positive or both negative
    both_pos = bin(pos1 & pos2).count('1')
    both_neg = bin(neg1 & neg2).count('1')
    agreement = both_pos + both_neg
    
    # Disagreement: one positive, other negative
    pos1_neg2 = bin(pos1 & neg2).count('1')
    neg1_pos2 = bin(neg1 & pos2).count('1')
    disagreement = pos1_neg2 + neg1_pos2
    
    total = agreement + disagreement
    if total == 0:
        return 0.0
    return agreement / total


def ternary_hamming(t1, t2, hash_bits=DEFAULT_TERNARY_BITS):
    """
    Calculate ternary Hamming distance (number of disagreeing positions).
    Only counts positions where both hashes have non-zero values.
    """
    pos1, neg1 = t1
    pos2, neg2 = t2
    
    pos1_neg2 = bin(pos1 & neg2).count('1')
    neg1_pos2 = bin(neg1 & pos2).count('1')
    return pos1_neg2 + neg1_pos2


# ===================================================================
# v3.0.0: Word Network (字词网络)
# ===================================================================

class WordNetwork:
    """
    Token-level entanglement network.
    
    Each unique token gets a ternary hash. Tokens that share many non-zero
    hash positions are "entangled" — they tend to appear in similar contexts.
    
    The network supports:
    - Query expansion: find related words for a given token
    - Contextual linking: strengthen connections through co-occurrence
    - Retrieval acceleration: pre-computed index for fast lookup
    """
    
    def __init__(self):
        self._token_hashes = {}   # token -> (pos_mask, neg_mask)
        self._cooccurrence = defaultdict(lambda: defaultdict(int))  # token -> {neighbor: count}
        self._total_docs = 0
    
    def add_document(self, text):
        """Process a document: compute token hashes and update co-occurrence."""
        tokens = tokenize(text)
        if not tokens:
            return
        
        self._total_docs += 1
        unique_tokens = set(tokens)
        
        # Compute/update ternary hashes for each token
        for token in unique_tokens:
            if token not in self._token_hashes:
                self._token_hashes[token] = ternary_hash(token)
        
        # Update co-occurrence counts
        token_list = list(unique_tokens)
        for i in range(len(token_list)):
            for j in range(i + 1, len(token_list)):
                self._cooccurrence[token_list[i]][token_list[j]] += 1
                self._cooccurrence[token_list[j]][token_list[i]] += 1
    
    def expand_query(self, query, max_expansions=5, min_similarity=0.15):
        """
        Expand a query with related tokens from the word network.
        
        Returns list of (token, similarity) tuples sorted by similarity.
        """
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        
        # Compute query ternary hash
        query_hash = ternary_hash(query)
        
        # Find related tokens through hash similarity
        candidates = []
        seen = set(query_tokens)
        
        for token, token_hash in self._token_hashes.items():
            if token in seen:
                continue
            sim = ternary_similarity(query_hash, token_hash)
            # Also check co-occurrence boost
            cooc_boost = 0
            for qt in query_tokens:
                cooc = self._cooccurrence.get(qt, {}).get(token, 0)
                if cooc > 0:
                    cooc_boost += min(0.2, cooc * 0.05)
            
            total_score = sim + cooc_boost
            if total_score >= min_similarity:
                candidates.append((token, total_score))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:max_expansions]
    
    def get_entangled_words(self, token, max_results=10):
        """Get words entangled with a specific token (via hash + co-occurrence)."""
        if token not in self._token_hashes:
            return []
        
        token_hash = self._token_hashes[token]
        results = []
        
        for other_token, other_hash in self._token_hashes.items():
            if other_token == token:
                continue
            sim = ternary_similarity(token_hash, other_hash)
            cooc = self._cooccurrence.get(token, {}).get(other_token, 0)
            if sim > 0 or cooc > 0:
                score = sim + min(0.3, cooc * 0.1)
                if score > 0.05:
                    results.append((other_token, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]
    
    def stats(self):
        """Get word network statistics."""
        total_cooc = sum(len(v) for v in self._cooccurrence.values())
        return {
            "total_tokens": len(self._token_hashes),
            "total_documents": self._total_docs,
            "total_cooccurrence_links": total_cooc // 2,
            "avg_links_per_token": round(total_cooc / max(len(self._token_hashes), 1) / 2, 2)
        }


# Global word network instance (persisted per workspace)
_word_networks = {}


def get_word_network(workspace=None):
    """Get or create the word network for a workspace."""
    if workspace not in _word_networks:
        _word_networks[workspace] = WordNetwork()
    return _word_networks[workspace]


def build_word_network_from_memories(memories, workspace=None):
    """
    Build/update the word network from all memories in a workspace.
    This creates the ternary hash index for fast retrieval.
    """
    wn = get_word_network(workspace)
    for mem in memories:
        content = mem.get("content", "")
        entity = mem.get("entity", "")
        wn.add_document(f"{entity} {content}")
    return wn


# ===================================================================
# v3.0.0: Levenshtein Distance (错别字纠偏)
# ===================================================================

def levenshtein_distance(s1, s2):
    """
    Calculate Levenshtein edit distance between two strings.
    Used for typo-tolerant matching.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    
    return prev_row[-1]


def fuzzy_match(query, target, max_distance=None):
    """
    Check if query fuzzy-matches target using Levenshtein distance.
    
    Args:
        query: The query string
        target: The target string to match against
        max_distance: Maximum edit distance (default: len(query) // 3 + 1)
    
    Returns: (is_match, similarity_score 0.0-1.0)
    """
    if not query or not target:
        return (False, 0.0)
    
    if max_distance is None:
        max_distance = max(1, len(query) // 3)
    
    # Quick check: exact match
    if query == target:
        return (True, 1.0)
    
    # Check substring
    if query in target or target in query:
        return (True, 0.9)
    
    dist = levenshtein_distance(query, target)
    if dist <= max_distance:
        max_len = max(len(query), len(target))
        similarity = 1.0 - (dist / max_len)
        return (True, similarity)
    
    return (False, 0.0)


def fuzzy_token_match(query_tokens, content_tokens, max_distance_ratio=0.33):
    """
    Check if query tokens fuzzy-match content tokens.
    Handles typos and minor wording differences.
    
    Returns a fuzzy match score 0.0-1.0.
    """
    if not query_tokens or not content_tokens:
        return 0.0
    
    content_set = set(content_tokens)
    matched = 0
    total_boost = 0.0
    
    for qt in query_tokens:
        if qt in content_set:
            matched += 1
            continue
        # Try fuzzy match for each unmatched query token
        best_sim = 0.0
        for ct in content_set:
            is_match, sim = fuzzy_match(qt, ct, max_distance=max(1, int(len(qt) * max_distance_ratio)))
            if is_match and sim > best_sim:
                best_sim = sim
                break
        if best_sim > 0:
            total_boost += best_sim * 0.7  # Fuzzy match worth 70% of exact
    
    exact_score = matched / len(query_tokens) if query_tokens else 0
    fuzzy_score = total_boost / len(query_tokens) if query_tokens else 0
    return min(1.0, exact_score + fuzzy_score)


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


def search_memories(query, memories, limit=10, similarity_threshold=0.15,
                    dynamic_threshold=True, workspace=None):
    """
    Search memories using a hybrid approach:
    1. SimHash for fast candidate filtering
    2. TF-IDF cosine similarity for precise ranking
    3. Keyword matching for exact hit boosting
    4. v3.0.0: Ternary hash for enhanced semantic discrimination
    5. v3.0.0: Fuzzy token matching for typo tolerance
    6. v3.0.0: Word network query expansion

    v2.1.0: Dynamic threshold mode — instead of a fixed similarity_threshold,
    the quality line adapts to the distribution of scores:
      dynamic_min = max(base, min(ceiling, top_score * ratio))
    This ensures high-quality queries get a commensurately high bar,
    while niche queries aren't starved of results.

    Args:
        query: Search query string
        memories: List of memory dicts
        limit: Max results to return
        similarity_threshold: Fallback fixed threshold (used when dynamic_threshold=False)
        dynamic_threshold: If True, compute threshold adaptively from score distribution
        workspace: v3.0.0 workspace name for word network access

    Returns:
        List of (memory, score, match_type) tuples, sorted by score descending
    """
    if not memories or not query:
        return []

    query_tokens = tokenize(query)
    query_simhash = simhash(query)
    query_ternary = ternary_hash(query)  # v3.0.0

    # v3.0.0: Word network query expansion
    expanded_tokens = set(query_tokens)
    wn = get_word_network(workspace)
    if wn._total_docs > 0:
        expansions = wn.expand_query(query, max_expansions=3, min_similarity=0.12)
        for exp_token, _ in expansions:
            expanded_tokens.add(exp_token)

    # Build corpus for TF-IDF
    all_docs = [tokenize(m.get("content", "")) for m in memories]

    candidates = []
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

        # 3. Keyword match (with v3.0.0 expanded tokens)
        kw_score = keyword_match_score(query_tokens, content_tokens)

        # v3.0.0: 4. Ternary hash similarity (enhanced discrimination)
        mem_ternary = memory.get("ternary_hash")
        if mem_ternary is None:
            mem_ternary = ternary_hash(full_text)
        th_score = ternary_similarity(query_ternary, mem_ternary)

        # v3.0.0: 5. Fuzzy token match (typo tolerance)
        fuzzy_score = fuzzy_token_match(query_tokens, content_tokens)

        # v3.0.0: 6. Expanded token match (word network)
        expanded_score = keyword_match_score(list(expanded_tokens), content_tokens) if len(expanded_tokens) > len(query_tokens) else 0

        # Combined score with weights
        # v3.0.0: rebalanced weights to incorporate ternary hash and fuzzy matching
        combined = (0.35 * tfidf_score +
                    0.20 * kw_score +
                    0.15 * sh_score +
                    0.12 * th_score +
                    0.10 * fuzzy_score +
                    0.08 * expanded_score)

        # v2.1.0: Coarse pre-filter — only skip absolute garbage
        if combined >= 0.02:
            # Determine match type
            if fuzzy_score > 0.3 and kw_score < 0.3:
                match_type = "fuzzy"  # v3.0.0: typo-tolerant match
            elif kw_score > 0.5:
                match_type = "keyword"
            elif tfidf_score > 0.3:
                match_type = "semantic"
            elif th_score > 0.3:
                match_type = "ternary"  # v3.0.0: ternary hash match
            elif expanded_score > 0.3:
                match_type = "expanded"  # v3.0.0: word network expansion
            else:
                match_type = "fuzzy"

            candidates.append((memory, combined, match_type))

    if not candidates:
        return []

    # v2.1.0: Dynamic threshold from score distribution
    if dynamic_threshold:
        top_score = max(c[1] for c in candidates)
        # adaptive quality line: proportional to top score, bounded
        dynamic_min = max(0.10, min(0.30, top_score * 0.5))
        effective_threshold = dynamic_min
    else:
        effective_threshold = similarity_threshold

    # Filter and sort
    results = [(m, s, t) for m, s, t in candidates if s >= effective_threshold]
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
