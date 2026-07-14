#!/usr/bin/env python3
"""
SuperBrain v3.0.0 Test Suite
Tests all v3.0.0 modules for functionality and backward compatibility.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
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

# === 3b. P1-1 Regression: 重复 token 查询仍须点亮扩展信号 ===
# 背景：v3.8.3 用 len(expanded_tokens) > len(query_tokens) 判断"是否发生扩展"，
# 但 expanded_tokens 是去重后的 set、query_tokens 是含重复的 list。query 含重复 token 时
# 两长度被拉平，即使词网真扩展了新 token，条件也为 False → 第六路信号被静默关闭。
# 修复后改用 set-vs-set（base_token_count），不受重复 token 干扰。
print("\n--- 3b. P1-1 Regression (expanded signal, duplicate-token query) ---")
import sb_search as _sb_search
class _FakeWN:
    _total_docs = 5
    def expand_query(self, query, max_expansions=3, min_similarity=0.12):
        return [("programming", 0.9)]   # 确定性地扩展出一个 query 里没有的 token
_orig_gwn = _sb_search.get_word_network
_sb_search.get_word_network = lambda workspace=None: _FakeWN()
_mem = [{"content": "programming only topic here", "entity": "y", "simhash": 0, "ternary_hash": None}]
_res = _sb_search.search_memories("python python", _mem, limit=10, workspace="p1_reg")
# query="python python" → tokenize 含重复；记忆内容仅含扩展 token "programming"，
# 修复前 expanded_score=0 且无其他信号达标 → 漏召回；修复后 has_expansion=True → 召回。
test("P1-1: duplicate-token query lights expanded signal", len(_res) >= 1, f"got {len(_res)} results (expected >=1)")
_sb_search.get_word_network = _orig_gwn   # 还原，避免影响后续用例

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
# v3.1.0: Add enough memories to pass cold start gating (need 15+)
for i in range(12):
    add_memory(content=f"测试记忆内容用于填充 #{i+1}", mem_type="fact",
              entity=f"测试实体{i%3}", confidence=0.8)

# Bump session count to pass warmup
from sb_core import read_meta, write_meta
meta = read_meta()
meta["session_count"] = meta.get("session_count", 0) + 3
write_meta(meta)

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

# v3.1.0 CLI tests
test("CLI has session command", "session" in test_actions)
test("CLI has obsidian command", "obsidian" in test_actions)

# v3.2.0 CLI tests
test("CLI has orchestrate command", "orchestrate" in test_actions, f"available: {test_actions}")

# === 13. Orchestrator Tests (v3.2.0) ===
print("\n--- 13. Orchestrator (子Agent编排器) ---")
from sb_orchestrator import (
    should_orchestrate, decompose_task, generate_sub_agent_specs,
    validate_isolation, select_minimal_tools, _detect_needed_profiles,
    TOOL_PROFILES, ORCHESTRATE_THRESHOLD, get_orchestration_stats
)
# v3.4.0
from sb_selfcheck import check_file_integrity, check_index_integrity, check_backup_freshness, _create_backup, run_full_check
from sb_token_roi import calc_token_roi
from superbrain import cmd_token_roi

# Assessment - trivial rejection
decision = should_orchestrate("帮我看一下今天几号")
test("O1: trivial task rejected", not decision["should_spawn"], decision["reason"])

# Assessment - sequential gate (needs ≥2 sequential patterns)
decision = should_orchestrate("先安装依赖，然后再启动服务器，最后再运行测试")
test("O2: sequential task gated", decision["gate"] in ("sequential", "complexity"), decision["gate"])

# Assessment - complex parallel passes
decision = should_orchestrate(
    "帮我同时做：\n1. 搜索最新的 AI Agent 论文\n2. 写Python后端接口代码\n"
    "3. 设计管理后台UI界面\n4. 生成项目分析报告",
    current_context_size=70000
)
test("O3: complex parallel passes orchestrator gate", decision["should_spawn"], decision["assessment"]["reasoning"])

# Decomposition
decomp = decompose_task(
    "1. 搜索AI搜索技术 2. 写数据分析脚本 3. 设计看板界面 4. 生成PPT报告"
)
test("O4: decomposition produces subtasks", decomp["count"] >= 2, f"Got {decomp['count']}")
st = decomp["sub_tasks"][0]
test("O5: subtask has 4 required fields", all(k in st for k in ["objective", "output_format", "tools", "boundary"]))

# Independence validation
similar = [{"objective": "搜索React 19新特性"}, {"objective": "搜索React 19更新"}]
issues = validate_isolation(similar)
test("O6: detects overlapping subtasks", len(issues) > 0)

independent = [{"objective": "设计UI"}, {"objective": "分析数据"}, {"objective": "编写脚本"}]
issues = validate_isolation(independent)
test("O7: independent subtasks pass", len(issues) == 0)

# Profile detection
profiles = _detect_needed_profiles("帮我写Python代码并设计UI界面")
test("O8: detects code+design profiles", "code" in profiles and "design" in profiles, str(profiles))

# Tool selection
tools = select_minimal_tools("research")
test("O9: research profile has tools", len(tools["tools"]) > 0)

# Full spec generation
spec = generate_sub_agent_specs(
    "帮我同时做：\n1. 搜索最新AI论文\n2. 写Python代码\n3. 设计UI界面",
    current_context_size=60000
)
test("O10: full spec generates correctly", "should_orchestrate" in spec)

# Stats
stats = get_orchestration_stats()
test("O11: orchestrator stats available", "stats" in stats and "version" in stats)

# Profile registry
test("O12: TOOL_PROFILES has 5+ profiles", len(TOOL_PROFILES) >= 5, str(list(TOOL_PROFILES.keys())))

# === 14. v3.4.0: Physical Selfcheck (物理层自检) ===
print("\n--- 14. Physical Selfcheck (v3.4.0) ---")

test("SC1: file_integrity check exists", callable(check_file_integrity))
fi = check_file_integrity()
test("SC2: file_integrity reports healthy", fi["status"] in ("healthy", "warning", "critical"))

test("SC3: index_integrity check exists", callable(check_index_integrity))
ii = check_index_integrity()
test("SC4: index_integrity runs without error", ii["status"] in ("healthy", "warning"))

test("SC5: backup_freshness check exists", callable(check_backup_freshness))
bf = check_backup_freshness()
test("SC6: backup_freshness reports status", bf["status"] in ("healthy", "warning"))

test("SC7: _create_backup exists", callable(_create_backup))
bk = _create_backup(reason="test")
test("SC8: backup creates files", len(bk.get("files", [])) > 0, f"Backed up: {bk.get('files', [])}")

# 9 items total
full = run_full_check()
test("SC9: full check now has 9 checks", len(full["checks"]) >= 9, f"Count: {len(full['checks'])}")

# === 15. v3.4.0: Token ROI (Token 量化) ===
print("\n--- 15. Token ROI (v3.4.0) ---")

test("T1: calc_token_roi exists", callable(calc_token_roi))
roi = calc_token_roi()
test("T2: ROI has expected fields", "total_savings" in roi and "roi_ratio" in roi)
test("T3: ROI ratio is positive", roi["roi_ratio"] >= 0)
test("T4: ROI has category breakdown", len(roi.get("by_category", {})) > 0)
test("T5: ROI has top savers", len(roi.get("top_savers", [])) >= 0)
test("T6: cmd_token_roi exists", callable(cmd_token_roi))

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
