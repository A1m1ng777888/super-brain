#!/usr/bin/env python3
"""
SuperBrain v3.0.0 Test Suite
Tests all v3.0.0 modules for functionality and backward compatibility.
"""

import sys
import os
import json
import tempfile
import shutil

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set temporary data directory for testing
test_data_dir = os.path.join(tempfile.gettempdir(), "superbrain_test_v3")
os.environ["SUPERBRAIN_DATA_DIR"] = test_data_dir

# Clean up any previous test data
if os.path.exists(test_data_dir):
    shutil.rmtree(test_data_dir)

from sb_core import ensure_workspace, load_config, save_config
from sb_search import (
    tokenize, simhash, ternary_hash, ternary_similarity,
    levenshtein_distance, fuzzy_match, fuzzy_token_match,
    WordNetwork, get_word_network, build_word_network_from_memories
)
from sb_pipeline import classify_content, compute_decay_factor, should_archive, DECAY_CONFIG
from sb_perception import should_learn_or_query, information_value_assessment, batch_perceive
from sb_reasoning import extract_key_points, analyze_logic, derive_conclusion
from sb_entanglement import mine_entanglement, build_entanglement_field, query_entanglement
from sb_context import topic_cluster, trace_thread, cross_session_recall
from sb_longterm import auto_ingest, build_index, zero_cost_retrieve
from sb_memory import (
    add_memory, search, auto_store, fuzzy_correct_query, 
    learn_expression, get_expression_profile, search_with_correction
)

passed = 0
failed = 0
errors = []

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} - {detail}")


print("=" * 60)
print("SuperBrain v3.0.0 Test Suite")
print("=" * 60)

# Initialize
ensure_workspace("default")
config = load_config()
save_config(config)

# === 1. Ternary Hash Tests ===
print("\n--- 1. Ternary Hash (三进制哈希) ---")

th1 = ternary_hash("hello world")
th2 = ternary_hash("hello world")
th3 = ternary_hash("completely different text")
test("ternary_hash returns tuple", isinstance(th1, tuple) and len(th1) == 2, f"got {type(th1)}")
test("same text same hash", th1 == th2, "identical texts should produce identical hashes")
test("different text different hash", th1 != th3, "different texts should produce different hashes")
sim_same = ternary_similarity(th1, th2)
sim_diff = ternary_similarity(th1, th3)
test("ternary similarity same=1.0", sim_same == 1.0, f"got {sim_same}")
test("ternary similarity diff<1.0", sim_diff < 1.0, f"got {sim_diff}")
test("ternary similarity diff>=0", sim_diff >= 0.0, f"got {sim_diff}")

# Chinese text
th_cn1 = ternary_hash("超脑记忆引擎")
th_cn2 = ternary_hash("超脑记忆系统")
sim_cn = ternary_similarity(th_cn1, th_cn2)
test("chinese ternary hash works", th_cn1 != (0, 0), "should produce non-zero hash")
test("chinese ternary similarity reasonable", 0.0 <= sim_cn <= 1.0, f"got {sim_cn}")

# === 2. Levenshtein / Fuzzy Match Tests ===
print("\n--- 2. Levenshtein / Fuzzy Match (错别字纠偏) ---")

test("levenshtein same=0", levenshtein_distance("hello", "hello") == 0)
test("levenshtein one edit", levenshtein_distance("hello", "hallo") == 1)
test("levenshtein insert", levenshtein_distance("cat", "cats") == 1)

is_match, sim = fuzzy_match("hellow", "hello")
test("fuzzy match typo", is_match and sim > 0.8, f"got match={is_match}, sim={sim}")

is_match, sim = fuzzy_match("completely", "different")
test("fuzzy match no match", not is_match, f"should not match, got match={is_match}")

fuzzy_score = fuzzy_token_match(["hello", "world"], ["helo", "word", "test"])
test("fuzzy token match partial", fuzzy_score > 0.3, f"got {fuzzy_score}")

# === 3. Word Network Tests ===
print("\n--- 3. Word Network (字词网络) ---")

wn = WordNetwork()
wn.add_document("Python is a programming language")
wn.add_document("Python is used for AI development")
wn.add_document("AI requires large datasets")

test("word network tracks docs", wn._total_docs == 3)
test("word network has tokens", len(wn._token_hashes) > 5)
test("word network has co-occurrence", len(wn._cooccurrence) > 0)

expansions = wn.expand_query("Python AI", max_expansions=3)
test("word network expand query", isinstance(expansions, list), f"got {type(expansions)}")

entangled = wn.get_entangled_words("python", max_results=5)
test("word network entangled words", isinstance(entangled, list), f"got {type(entangled)}")

stats = wn.stats()
test("word network stats", "total_tokens" in stats and "total_documents" in stats)

# === 4. Pipeline (Classification) Tests ===
print("\n--- 4. Classification Pipeline (分类管线) ---")

result = classify_content("React是一个用于构建用户界面的JavaScript库，由Facebook开发。")
test("classify definition", result["category"] == "definition", f"got {result['category']}")

result = classify_content("哈哈好的谢谢啦")
test("classify chitchat", result["category"] == "chitchat", f"got {result['category']}")

result = classify_content("项目使用React 18，但是需要注意兼容性问题。")
test("classify hybrid or definition", result["category"] in ("hybrid", "definition"), f"got {result['category']}")

# Decay test
import time
from datetime import datetime, timezone
old_mem = {
    "timestamp": "2025-01-01T00:00:00",
    "access_count": 0,
    "confidence": 0.5,
    "attributes": {"content_category": "chitchat"}
}
decay = compute_decay_factor(old_mem, "chitchat")
test("chitchat fast decay", decay < 0.5, f"chitchat should decay fast, got {decay}")

old_mem_def = {
    "timestamp": "2025-01-01T00:00:00",
    "access_count": 0,
    "confidence": 0.9,
    "attributes": {"content_category": "definition"}
}
decay_def = compute_decay_factor(old_mem_def, "definition")
test("definition slow decay", decay_def > decay, f"definition should decay slower, got {decay_def} vs {decay}")

# === 5. Perception Tests ===
print("\n--- 5. Perception (感知增强) ---")

value = information_value_assessment("API网关配置需要设置超时时间为30秒，并启用重试机制。")
test("info value assessment high", value > 0.4, f"got {value}")

value_low = information_value_assessment("好的嗯嗯")
test("info value assessment low", value_low < 0.3, f"got {value_low}")

perception = should_learn_or_query("用户偏好使用TypeScript进行开发，配置strict模式。")
test("perception decision valid", perception["decision"] in ("learn", "query", "both", "skip"))
test("perception has reasoning", "reasoning" in perception)

perception_skip = should_learn_or_query("哈哈好的谢谢")
test("perception skips chitchat", perception_skip["decision"] == "skip", f"got {perception_skip['decision']}")

# === 6. Reasoning Tests ===
print("\n--- 6. Reasoning (推理引擎) ---")

points = extract_key_points(
    "React 18引入了并发渲染特性。因为并发渲染可以提高性能，所以大型应用受益最大。"
    "但是需要注意兼容性问题。如果使用Suspense，则需要确保组件支持异步加载。"
)
test("extract key points", len(points) > 0, "should extract at least one point")
test("key points sorted", all(points[i]["score"] >= points[i+1]["score"] for i in range(len(points)-1)), "should be sorted by score")

logic = analyze_logic("因为并发渲染可以提高性能，所以大型应用受益最大。")
test("analyze logic finds relationships", logic["relationship_count"] > 0, "should find cause-effect")
test("analyze logic structure", logic["structure"] in ("simple", "causal_chain", "conditional", "complex", "flat"))

# === 7. Memory Engine v3.0.0 Tests ===
print("\n--- 7. Memory Engine v3.0.0 (记忆引擎升级) ---")

# Add test memories
mem1 = add_memory(
    content="用户偏好使用TypeScript进行开发",
    mem_type="preference",
    entity="用户",
    confidence=0.95
)
test("memory has ternary hash", mem1.get("ternary_hash") is not None, "v3.0.0 memories should have ternary_hash")

mem2 = add_memory(
    content="项目使用React 18和TypeScript",
    mem_type="fact",
    entity="项目",
    confidence=0.9
)

# Search
results = search("TypeScript", limit=5)
test("search returns results", len(results) > 0, "should find TypeScript memories")
test("search returns tuples", all(len(r) == 3 for r in results), "should return (mem, score, type)")

# Auto store
auto_result = auto_store("配置API网关需要设置超时时间30秒，启用重试机制，这是生产环境的必须配置。")
test("auto_store returns action", "action" in auto_result, f"got {auto_result}")

# Fuzzy correct
learn_expression("TS", standard_form="TypeScript")
learn_expression("React18", standard_form="React 18")
correction = fuzzy_correct_query("TScript开发")
test("fuzzy_correct returns dict", "corrected" in correction and "corrections" in correction)

# Search with correction
corrected_results = search_with_correction("TypeScript", limit=5)
test("search_with_correction returns results", isinstance(corrected_results, list))

# Expression profile
profile = get_expression_profile()
test("expression profile has entries", len(profile.get("expression_map", {})) > 0, "should have learned expressions")

# === 8. Entanglement Tests ===
print("\n--- 8. Entanglement (纠缠场) ---")

# Add more memories for entanglement
add_memory(content="超脑使用三进制哈希进行语义搜索", mem_type="fact", entity="超脑", confidence=0.9)
add_memory(content="三进制哈希比二进制SimHash有更强的区分能力", mem_type="fact", entity="超脑", confidence=0.85)
add_memory(content="语义搜索通过TF-IDF和关键词匹配实现", mem_type="fact", entity="超脑", confidence=0.8)

ent_result = mine_entanglement("超脑", min_strength=0.05)
test("mine_entanglement returns dict", "combined" in ent_result, "should have combined results")

field = build_entanglement_field(min_strength=0.05)
test("build_entanglement_field returns stats", "total_tokens" in field, "should have field stats")

query_ent = query_entanglement("哈希搜索", max_results=5)
test("query_entanglement returns list", isinstance(query_ent, list))

# === 9. Context Memory Tests ===
print("\n--- 9. Context Memory (上下文记忆) ---")

clusters = topic_cluster(min_similarity=0.15)
test("topic_cluster returns clusters", "clusters" in clusters, "should have clusters")
test("topic_cluster has results", clusters["total_clusters"] > 0, "should find at least one cluster")

thread = trace_thread("超脑")
test("trace_thread returns narrative", "narrative" in thread, "should have narrative")

recall = cross_session_recall("TypeScript")
test("cross_session_recall returns sessions", "sessions" in recall, "should have sessions")

# === 10. Long-Term Memory Tests ===
print("\n--- 10. Long-Term Memory (本地长期记忆) ---")

ingest_result = auto_ingest("配置Docker部署需要设置环境变量DATABASE_URL，端口映射5432，这是生产环境的标准配置。")
test("auto_ingest returns action", "action" in ingest_result, f"got {ingest_result}")

index_result = build_index()
test("build_index returns stats", "indexed_memories" in index_result, "should have index stats")
test("build_index computed hashes", index_result["ternary_hashes"] > 0, "should compute ternary hashes")

retrieval = zero_cost_retrieve("Docker", limit=3)
test("zero_cost_retrieve returns memories", "memories" in retrieval, "should have memories")
test("zero_cost_retrieve method", retrieval.get("method") == "ternary_hash_zero_cost")

# === 11. Backward Compatibility Tests ===
print("\n--- 11. Backward Compatibility (向后兼容) ---")

# SimHash still works
sh = simhash("test text")
test("simhash still works", isinstance(sh, int) and sh >= 0)

# Old-style memory without ternary hash should still be searchable
from sb_core import read_memories, write_memories
memories = read_memories()
old_style_mem = {
    "id": "mem_legacy_001",
    "timestamp": "2026-06-29T00:00:00",
    "type": "fact",
    "entity": "legacy",
    "content": "This is a legacy memory without ternary hash",
    "attributes": {},
    "confidence": 0.8,
    "access_count": 0,
    "status": "active",
    "simhash": simhash("legacy memory"),
    "related_nodes": []
    # Note: no ternary_hash field
}
memories.append(old_style_mem)
write_memories(memories)
legacy_results = search("legacy", limit=5)
test("legacy memory searchable", any(r[0]["id"] == "mem_legacy_001" for r in legacy_results), "legacy memories should still be searchable")

# === 12. CLI Integration Tests ===
print("\n--- 12. CLI Integration (CLI集成) ---")

import superbrain as cli
parser = cli.build_parser()

# Test that new subcommands are registered
test_actions = []
for action in parser._subparsers._actions:
    if hasattr(action, 'choices') and action.choices:
        test_actions.extend(action.choices.keys())

test("CLI has perceive command", "perceive" in test_actions, f"available: {test_actions}")
test("CLI has pipeline command", "pipeline" in test_actions)
test("CLI has reason command", "reason" in test_actions)
test("CLI has entangle command", "entangle" in test_actions)
test("CLI has context-mem command", "context-mem" in test_actions)
test("CLI has longterm command", "longterm" in test_actions)

# === Summary ===
print("\n" + "=" * 60)
print(f"Test Results: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 60)

if errors:
    print("\nFailures:")
    for e in errors:
        print(f"  - {e}")

# Cleanup
shutil.rmtree(test_data_dir, ignore_errors=True)

sys.exit(0 if failed == 0 else 1)
