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

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
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

# v3.11: entity 精确命中 boost —— 常量的现行定义见下方「BM25 主分」区。
# v3.11.2 P0-B 起检索改走 BM25，量纲从 RRF 的 0~0.098 变为归一化后的 0~1，
# boost 相应由加性 +0.04 改为乘性 ×1.4（换算说明见 ENTITY_HIT_MULTIPLIER）。


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

    # v3.9.4: 长度差预筛——编辑距离 ≥ |len(query)-len(target)|，
    # 长度差超过 max_distance 必然不匹配，安全剪枝（放在 substring 检查之后，
    # 不误杀子串命中）。n=500 时可将 Levenshtein 调用量削减 90%+。
    if abs(len(query) - len(target)) > max_distance:
        return (False, 0.0)

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
    
    # v3.11.2 P0-C: 有序去重，替代 set()。
    # 实测缺陷：set 的迭代顺序取决于 Python 字符串哈希（PYTHONHASHSEED 每次
    # 启动随机），配合下方 break，导致「哪个模糊匹配先命中」每次运行都不同
    # → 检索结果不可复现。这与超脑「每个数字可自己复现」的定位直接冲突。
    # dict.fromkeys 保持文档顺序去重，既确定性又不损失去重效果。
    content_set = dict.fromkeys(content_tokens)
    membership = content_set
    matched = 0
    total_boost = 0.0
    
    for qt in query_tokens:
        if qt in membership:
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


def _tfidf_cosine_precomputed(tf1, tf2, doc_freq, n_docs):
    """
    v3.9.4: TF-IDF cosine 的预建表版本——与 tf_idf_cosine_similarity 同公式，
    但 IDF 从预建的 doc_freq 查表，消除 search_memories 热路径中
    「每候选 × 每 term 全库扫 doc_freq」的 O(n²·terms) 退化。

    等价性：doc_freq 预建语义（每文档对 term 至多计 1）与原实现
    `sum(1 for doc in all_docs if term in doc)` 完全一致；term 缺失时
    两者都得 0，浮点运算序列相同，结果 bit 级一致。

    Args:
        tf1/tf2: Counter 词频（调用方已 tokenize）
        doc_freq: 预建文档频率表（term -> 包含该 term 的文档数）
        n_docs: 语料文档总数 N
    """
    all_terms = set(tf1.keys()) | set(tf2.keys())
    idf = {t: math.log((n_docs + 1) / (doc_freq.get(t, 0) + 1)) + 1 for t in all_terms}

    vec1 = {term: tf1[term] * idf.get(term, 1.0) for term in tf1}
    vec2 = {term: tf2[term] * idf.get(term, 1.0) for term in tf2}

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


# ============================================================ BM25 主分

# BM25 参数。与 superbrain-bench/eval_recall.py 的 BM25Baseline 保持逐项一致，
# 便于评测器与线上代码互相复现（改这里必须同步改那里，否则对照失效）。
BM25_K1 = 1.5

# v3.11.2 P0-G（**已撤回，保留结论备查**）：曾试 0.75 → 0.90，最终撤回。
#
# 起因诊断（真实中文库，查询「腾讯那个岗位投出去后现在什么状态」）：
#   top1 是我刚写入的 400 字过程记录，60.98 分，但**没有任何一个 token 贡献
#   超过 7%**——「那个」7.0% +「什么」5.3% +「腾讯那」5.3% +「讯那个」5.3%…
#   纯靠命中词多堆出来的；而真正相关的「腾讯AI产品经理岗已正式投递」只有
#   15.43 分，构成却是「投出」33.2% +「腾讯」23.5%——高信息量的精准匹配。
#   即：长文档靠**堆低信息量 token** 取胜，短而准的记忆被淹没。
#
# 中文 30 题扫描（同进程，recall@5 / mrr@5）：
#     0.75  0.900 / 0.758   （保留值）
#     0.85  0.867 / 0.756
#     0.90  0.900 / 0.764
#     0.95  0.867 / 0.756
#     1.00  0.867 / 0.733
#   0.90 在 k=1/3/5/10 上从不更差，k=10 多召回 1 题（0.900→0.933、
#   mrr 0.740→0.771），看着该改。
#
# ❌ 但 LOCOMO（298 题，**10 倍样本**）给出一致反证：
#     recall@5  0.570 → 0.557    recall@20  0.698 → 0.691    mrr 0.442 → 0.432
#   三项指标全部为负。
#
# 撤回理由：中文侧的「收益」实为 **1 道题**（1/30 = 0.033），而反证是 298 题
# 上约 4 道题的一致损失。1 道题不是证据，是抛硬币——**不在噪声上做决定**。
#
# 结论：B 只能按文档长度统一缩放，**无法区分「命中词多但都弱」与「命中词少
# 但很强」**。堆量问题的根因在这里无解，需要别的手段（见报告 §18.4）。
BM25_B = 0.75

# v3.11: entity 精确命中 boost —— 查询 token 与记忆 entity 完全一致（大小写不敏感）
# 时提升该记忆排名，修复「entity 强相关但 content 词面不重叠」的记忆
# 排名过低被 limit 截断（实验 1 RAG 反例）。
# v3.11.2 P0-B: 由「RRF 量纲下加性 +0.04」改为「原始分乘性 ×1.4」。
# 换算依据：RRF 满分 6/(K+1)≈0.098，+0.04 ≈ 满分的 41%；乘性 ×1.4 保持
# 相同的相对提升强度，且不会像加性那样在归一化后溢出 0~1 区间。
ENTITY_HIT_MULTIPLIER = 1.4

# v3.11.2: 动态阈值比例——保留「分数 ≥ 最佳匹配 × 该比例」的结果。
# 不能沿用 v3.8.x 的等效值：RRF 分数分布平缓（每路最多贡献 1/61），而 BM25
# 呈长尾（实测相关/最佳不相关分数比中位 3.09），同样的相对比例在 BM25 下
# 会误滤掉大量中等相关记忆（test_v3.py 3c 实测：RAG 记忆被整体滤除）。
# 该值由 superbrain-bench 实测标定（conv-26，199 题），扫描结果：
#     thr   recall@5  recall@10  recall@20  ndcg@10  平均返回
#     0.0      0.447      0.553      0.633    0.341     20.0
#     0.2      0.447      0.553      0.633    0.341     19.8  ← 拐点
#     0.3      0.447      0.548      0.613    0.341     18.3
#     0.5      0.432      0.513      0.553    0.336     11.5
# 0.2 及以下与「完全不过滤」指标逐位相同，0.3 起开始有可测量损失，
# 0.5 会砍掉 42% 的候选并损失 8 个点的 recall@20。取 0.2：既保住全部
# 召回质量，又保留对「查询与库完全无关」这一真实场景的兜底过滤。
DYNAMIC_THRESHOLD_RATIO = 0.2

# v3.11.2 P0-F: 单字 CJK token（unigram）的权重系数。
# 1.0 = 与 bigram/trigram 同等计权（虚词噪声大）；0.0 = 完全不给分
# （单字内容词如「茶」彻底失配）。0.35 由 30 条真实中文问句三选一同进程
# 对照标定，详见 _bm25_tokenize 的 docstring。
CJK_UNIGRAM_WEIGHT = 0.35


def _bm25_tokenize(text):
    """BM25 专用分词：CJK 出 unigram + bigram + trigram，其中 unigram 降权。

    ⚠️ 为什么要有第二个分词函数，而不是直接改全局 tokenize()——因为
    **全局 tokenize() 不能动**：sb_memory.add_memory 在写入时算
    `simhash(full_text)` 并落盘，find_duplicates 再拿新算的值去比已存储的
    旧值。改了分词，新旧 simhash 就不可比，去重会**静默失效**（不报错、
    只是再也查不出重复）。要改全局分词必须先做全量 simhash 重算迁移。

    ------------------------------------------------------------------
    为什么 CJK unigram 要「降权保留」而不是「全留」或「全删」
    ------------------------------------------------------------------
    同一份证据会以 unigram / bigram / trigram 三种 token 重复计入，
    但 unigram 也是**单字内容词唯一的匹配通道**，不能一删了之。

    实测（真实中文库，查询「我们数据库用的什么」top-1 得分 40.29，
    内容词「数据库」贡献 0，100% 来自停用词）：
        我们 18.5% | 们 17.6% | 什么 17.2% | 什 17.2% | 么 15.1% | 我 12.3%
    更反直觉的是这些填充词 IDF **极高**（我们 = 4.150，538 篇里仅 8 篇含）。
    BM25 隐含假设「停用词必然高频低 IDF」，但个人知识库是密集笔记，
    口语填充词反而罕见 → 被当成强信号。

    但全部删掉 unigram 也有代价：查询「上次说的那个茶是什么来着」的
    bigram 是 `个茶`/`茶是`，文档「砚：记住了，乌龙茶」的 bigram 是
    `乌龙`/`龙茶`——**只有单字「茶」能匹配**，删了就彻底失配。

    三选一同进程对照（30 条真实中文问句，recall@1/@3/@5、mrr@5）：
        unigram 全留(×1.0)  0.667 / 0.833 / 0.833 / 0.728   ← mrr 最低
        unigram 全删(×0.0)  0.600 / 0.867 / 0.867 / 0.756   ← recall@1 最低
        unigram ×0.35       0.633 / 0.867 / **0.900** / **0.758**  ← 采用
        unigram ×0.2        0.633 / 0.867 / 0.867 / 0.756
    ×0.35 在四项指标上均为最佳或并列最佳，且从不是最差。

    降权实现：在 _build_bm25_index 里把单字 CJK token 的 idf 乘以
    CJK_UNIGRAM_WEIGHT。因为 BM25 单项贡献 = idf × tf 饱和项，缩放 idf
    即等价于缩放该项贡献，且查询侧与文档侧共用同一张 idf 表，自动一致。
    """
    if not text:
        return []
    tokens = list(WORD_PATTERN.findall(text.lower()))
    cjk_chars = CJK_PATTERN.findall(text)
    # bigram
    for i in range(len(cjk_chars) - 1):
        tokens.append(cjk_chars[i] + cjk_chars[i + 1])
    # trigram
    for i in range(len(cjk_chars) - 2):
        tokens.append(cjk_chars[i] + cjk_chars[i + 1] + cjk_chars[i + 2])
    # unigram：保留（单字内容词的唯一匹配通道），权重在 idf 层降权
    tokens.extend(cjk_chars)
    return tokens


def _is_cjk_unigram(tok):
    """是否为单字 CJK token（用于 idf 降权）。"""
    return len(tok) == 1 and bool(CJK_PATTERN.fullmatch(tok))


def _build_bm25_index(memories):
    """预建 BM25 索引：idf 表 + 倒排表 + 文档长度。

    倒排（term -> [(doc_idx, tf)]）的意义：查询时只遍历真正命中该 term 的
    文档，避免「每个 query token 全库扫一遍」的 O(queries × n) 开销。

    v3.11.2 P0-B: 检索主分由 TF-IDF cosine 换成 BM25。
    实测依据（LOCOMO conv-26/30/41，448 题，见 superbrain-bench/results）：
        朴素 BM25 单路   recall@5 0.447 / 0.533 / 0.513
        六通道 RRF（旧） recall@5 0.293 / 0.314 / 0.269
        simhash 单路             0.027 / 0.048 / 0.031
        ternary 单路             0.040 / 0.067 / 0.026
    RRF 的病灶在于融合「名次」而非「分数」：simhash / ternary 单路表现与
    随机基线（约 1.2%）无异，却各自对全库贡献一整遍 1/(60+rank) 的扰动，
    量级与有效信号的名次级差相当 → 三路噪声压过了两路信号。
    """
    # v3.11.2 P0-F: BM25 走专用分词（去 CJK unigram），其余模块仍用全局
    # tokenize()——原因见 _bm25_tokenize 的 docstring（simhash 兼容性约束）。
    docs = [_bm25_tokenize(f"{m.get('entity', '')} {m.get('content', '')}")
            for m in memories]
    n = len(docs)
    avgdl = (sum(len(d) for d in docs) / n) if n else 0.0
    tf_list = [Counter(d) for d in docs]

    df = Counter()
    for tf in tf_list:
        for t in tf:                     # Counter 的键已去重
            df[t] += 1
    idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    # v3.11.2 P0-F: 单字 CJK token 降权。BM25 单项贡献 = idf × tf 饱和项，
    # 缩放 idf 即等价于缩放该 token 的贡献；查询侧与文档侧共用同一张 idf
    # 表，因此自动一致。依据见 CJK_UNIGRAM_WEIGHT 与 _bm25_tokenize。
    if CJK_UNIGRAM_WEIGHT != 1.0:
        for t in idf:
            if _is_cjk_unigram(t):
                idf[t] *= CJK_UNIGRAM_WEIGHT

    postings = defaultdict(list)
    for i, tf in enumerate(tf_list):
        for t, f in tf.items():
            postings[t].append((i, f))

    return {
        "n": n,
        "avgdl": avgdl,
        "idf": idf,
        "postings": postings,
        "lens": [len(d) for d in docs],
    }


def _bm25_scores(query_tokens, index):
    """返回与 memories 顺序一致的 BM25 分数列表（无过滤、无截断、无归一化）。"""
    n = index["n"]
    out = [0.0] * n
    avgdl = index["avgdl"]
    if not avgdl:
        return out
    idf = index["idf"]
    postings = index["postings"]
    lens = index["lens"]
    k1 = BM25_K1
    for t in query_tokens:
        plist = postings.get(t)
        if not plist:
            continue
        w = idf[t]
        for i, f in plist:
            dl = lens[i]
            out[i] += w * (f * (k1 + 1)) / (
                f + k1 * (1 - BM25_B + BM25_B * dl / avgdl))
    return out


def _signal_relevant(tfidf, kw, sh, th, fuzzy, expanded):
    """粗筛：任一路信号达到最低相关阈值即视为候选。

    替代原 search_memories 中 `combined >= 0.02` 的加权求和门槛，
    使 RRF 融合前只保留"至少一路信号有反应"的记忆，跳过纯噪声。
    """
    return (tfidf > 0.08 or kw > 0.15 or sh > 0.5 or
            th > 0.15 or fuzzy > 0.15 or expanded > 0.15)


def search_memories(query, memories, limit=10, similarity_threshold=0.15,
                    dynamic_threshold=True, workspace=None):
    """
    Search memories. v3.11.2 (P0-B) 起主分是 **BM25 单路**，不再做多通道融合。

    算法沿革（保留以备对照，勿删）：
    - v3.0.0 – v3.7：六路信号手调权重加权求和
    - v3.8.x – v3.11.1：六路信号 RRF（Reciprocal Rank Fusion）按名次融合
    - v3.11.2：BM25 单路。原因见 _build_bm25_index 的实测数据——RRF 融合
      的是名次而非分数，三路无效信号（simhash / ternary / fuzzy）各自对全库
      贡献一整遍 1/(60+rank) 扰动，把两路有效信号淹没了。
      六通道 RRF recall@5 = 0.29，朴素 BM25 = 0.52。

    分数语义（重要）：返回的是**归一化到 0~1 的相对分**——占本次检索最高分
    的比例，只保证同一查询内可比。它是排序分，不是相似度：
    - 需要「绝对相似度」的调用方（例如判断新内容是否与已有记忆雷同）
      请用 tf_idf_cosine_similarity，不要用这里的 score。
    - 现存的反例教训：v3.8.x 把打分换成 RRF（上限 0.098）后没有同步下游的
      硬编码阈值，导致 sb_perception.novelty_check 里 `score < 0.6` 恒成立、
      新颍性检测彻底失效。量纲变了，阈值必须跟着变。

    Args:
        query: Search query string
        memories: List of memory dicts
        limit: Max results to return
        similarity_threshold: 固定阈值，0~1 相对量纲（dynamic_threshold=False 时用）
        dynamic_threshold: True 时保留分数达到最佳匹配 50% 以上的结果
        workspace: workspace 名（v3.11.2 起检索路径不再使用词网络，仅为兼容保留）

    Returns:
        List of (memory, score, match_type) tuples, sorted by score descending
    """
    if not memories or not query:
        return []

    query_tokens = tokenize(query)
    # v3.11: 预计算查询 token 的小写集合，供 entity 精确命中判断（大小写不敏感）
    query_lower_tokens = {t.lower() for t in query_tokens}
    # v3.0.0: Word network query expansion（已于 v3.11.2 P0-B 退出检索路径）
    # v3.11.2 P0-B: 检索主分改 BM25 后，词网络不再参与排序。
    # 依据：按题型拆解 448 题后，BM25+wordnet 两路相对 BM25 单路在
    # adversarial(-0.046)、multi-hop(-0.024) 上是净亏，其余题型差异都在
    # 噪声底(±0.01)内——没有任何一类题型上词网络有显著正向贡献。
    # 注：P0-A 修复的「CLI 路径词网络恒为空」是真实缺陷，对仍走词网络的
    # 纠缠场挖掘（sb_entangle_mine）等路径依旧有效，这里只是不再在检索
    # 热路径上付构建开销。

    # Build corpus（keyword 标注仍需要 content 分词）
    all_docs = [tokenize(m.get("content", "")) for m in memories]

    # v3.11.2 P0-B: BM25 主分 + 单路排序（替代六通道 RRF）。
    # v3.11.2 P0-F: 查询侧同样走 _bm25_tokenize，与索引侧分词保持一致——
    # 两侧分词口径不同会让倒排表查不到（索引里没有 unigram 键）。
    bm_index = _build_bm25_index(memories)
    bm_raw = _bm25_scores(_bm25_tokenize(query), bm_index)

    candidates_raw = []
    for i, memory in enumerate(memories):
        bm = bm_raw[i]
        if bm <= 0:
            continue
        # keyword 只用于 match_type 标注，不参与排序：消融显示它单路
        # recall@5 仅 0.30，作为融合信号有害，作为标注仍有解释价值。
        kw_score = keyword_match_score(query_tokens, all_docs[i])
        match_type = "keyword" if kw_score > 0.5 else "semantic"
        candidates_raw.append((memory, match_type, bm))

    if not candidates_raw:
        return []

    # v3.11: entity 精确命中 boost —— 修复 entity 强相关但 content 词面不重叠时
    # 排名过低被 limit 截断（实验 1 RAG 反例）。检测标准：记忆 entity（非空、小写后）
    # 与查询任一 token 完全一致。命中者在最终排序前加固定 boost。
    # 注意：boost 只在「过滤后排序」阶段生效，不参与 dynamic_threshold 计算——
    # 否则会抬高 top_score → 抬高 dynamic_min → 误滤掉其他中等相关记忆。
    entity_hit_flags = []
    for mem, _mt, _bm in candidates_raw:
        ent = (mem.get("entity") or "").strip().lower()
        entity_hit_flags.append(bool(ent) and ent in query_lower_tokens)

    # v3.11.2 P0-B: 归一化到 0~1。
    # 为什么必须归一化：BM25 是随查询长度累加的**无界量**（本库实测中位约 67、
    # p90 约 101），而下游 sb_memory 的过期惩罚(×0.85)、遗忘降权，以及 persona
    # 合并的 min(1.0, score * 1.1) 全部假设 0~1 量纲——直接放出原始分会让所有
    # persona 结果被 clamp 成 1.0 集体插队。
    #
    # 归一方式：占本次检索最高分的比例，语义为「相对最佳匹配有多好」。
    # 与旧 RRF 时代的相对强度对齐：旧阈值 0.02~0.07 / 满分 0.098 ≈ 最高分的
    # 20%~71%；新动态阈值取最高分的 50%，落在同一区间内。
    #
    # ⚠️ 这是**相对**量纲：同一查询内可比，跨查询绝对值不可比。需要绝对
    #   相似度的调用方（如感知层新颍性判定）请用 tf_idf_cosine_similarity，
    #   见 sb_perception.novelty_check 的 v3.11.2 修复。
    top_base = max(c[2] for c in candidates_raw)
    if top_base <= 0:
        return []
    boosted_raw = [
        c[2] * (ENTITY_HIT_MULTIPLIER if entity_hit_flags[i] else 1.0)
        for i, c in enumerate(candidates_raw)
    ]
    top_boosted = max(boosted_raw)

    # 过滤用 base_norm（不含 boost）：boost 若参与阈值计算会抬高最高分 →
    # 抬高阈值线 → 误滤掉其他中等相关记忆（v3.11 原有约束，保持不变）。
    base_norm = [c[2] / top_base for c in candidates_raw]
    norm = [r / top_boosted for r in boosted_raw]

    if dynamic_threshold:
        # 归一化后最高分恒为 1.0，动态阈值即「保留达到最佳匹配
        # DYNAMIC_THRESHOLD_RATIO 以上者」。比例值见常量处的标定说明。
        effective_threshold = DYNAMIC_THRESHOLD_RATIO
    else:
        # 非动态模式：similarity_threshold 现与归一化量纲一致，无需再夹取。
        effective_threshold = max(0.0, min(1.0, similarity_threshold))

    results = [
        (candidates_raw[i][0], norm[i], candidates_raw[i][1])
        for i in range(len(candidates_raw))
        if base_norm[i] >= effective_threshold
    ]
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


def find_duplicates(memories, similarity_threshold=0.85):
    """
    Find likely duplicate memories using a two-stage approach:
    1. SimHash coarse filter (simhash_threshold=0.65) for fast candidate selection
    2. TF-IDF cosine similarity for precise duplicate confirmation (similarity_threshold)

    Returns list of (memory1_id, memory2_id, similarity) tuples.
    """
    duplicates = []
    n = len(memories)
    if n < 2:
        return duplicates

    # Build corpus for TF-IDF
    all_docs = [tokenize(m.get("content", "")) for m in memories]

    # v3.11.x 性能修复：预建 IDF doc_freq 表 + 预计算每篇 doc 的 tf Counter，
    # 消除 find_duplicates 热路径「每候选 × 每 term 全库扫 doc_freq」的
    # O(n²·terms·doc_len) 退化（n=382 实测 ~235s → 秒级）。
    # 语义与原 tf_idf_cosine_similarity(content1, content2, all_docs) 逐项等价：
    # doc_freq 按「每文档对 term 至多计 1」构建，公式 idf=log((N+1)/(df+1))+1 相同，
    # 浮点运算序列一致，结果 bit 级一致（与 v3.9.4 _tfidf_cosine_precomputed 同源）。
    doc_freq = Counter()
    for toks in all_docs:
        for term in set(toks):
            doc_freq[term] += 1
    tf_list = [Counter(toks) for toks in all_docs]

    for i in range(n):
        h1 = memories[i].get("simhash", 0)
        if h1 == 0:
            h1 = simhash(memories[i].get("content", ""))
        for j in range(i + 1, n):
            h2 = memories[j].get("simhash", 0)
            if h2 == 0:
                h2 = simhash(memories[j].get("content", ""))
            # Stage 1: SimHash coarse filter
            sh_sim = simhash_similarity(h1, h2)
            if sh_sim < 0.65:
                continue
            # Stage 2: TF-IDF precise check（doc_freq 查表，等价于原全库扫描）
            tfidf_sim = _tfidf_cosine_precomputed(
                tf_list[i], tf_list[j], doc_freq, n)
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
