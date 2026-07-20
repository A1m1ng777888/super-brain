#!/usr/bin/env python3
"""SuperBrain end-to-end test suite.
Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""
import sys
import os
import json
import tempfile

# B2 修复 (2026-07-10): 测试隔离
# 1. SCRIPT_DIR 用 __file__ 相对路径（不再硬编码 ~/.workbuddy/...，可在 CI/干净环境跑）
# 2. 数据目录重定向到 temp（避免触碰 production 的 ~/.workbuddy/super-brain/）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# B2: 重定向数据目录到 temp，sb_core.DEFAULT_DATA_DIR 会读这个环境变量
os.environ.setdefault("SUPERBRAIN_DATA_DIR",
                      os.path.join(tempfile.gettempdir(), "superbrain_test_data"))

from sb_core import (ensure_workspace, write_memories, write_graph, load_config, save_config,
                     switch_workspace, list_workspaces)
from sb_memory import add_memory, list_memories, search, get_context, merge_memories, get_stats, find_issues
from sb_graph import add_node, add_edge, query_graph, find_node, list_nodes, get_stats as get_graph_stats, delete_node
from sb_search import simhash, simhash_similarity, hamming_distance, tf_idf_cosine_similarity, tokenize, find_duplicates
from sb_selfcheck import run_full_check, get_health_score, get_health_report

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

def section(title):
    print(f"\n=== {title} ===")

# === SETUP: Clean test workspace and switch into it ===
section("Setup")
_original_workspace = load_config().get("current_workspace", "default")
# B2: 隔离到 temp 后，确保 default workspace 存在（首次跑 temp 目录没有）
ensure_workspace("default")
for ws in ["test"]:
    ensure_workspace(ws)
    write_memories([], ws)
    write_graph({"nodes": {}, "edges": {}}, ws)
switch_workspace("test")
print(f"  Test workspace cleaned and activated. (original workspace: {_original_workspace})")

# === TEST: Search Engine ===
section("Search Engine (sb_search)")

# SimHash
h1 = simhash("hello world")
h2 = simhash("hello world")
h3 = simhash("completely different text")
test("SimHash determinism", h1 == h2, "Same text should produce same hash")
test("SimHash differentiation", h1 != h3, "Different text should produce different hash")

# Hamming distance
hd = hamming_distance(h1, h3)
test("Hamming distance > 0 for different texts", hd > 0, f"Got {hd}")

# SimHash similarity
sim_same = simhash_similarity(h1, h2)
sim_diff = simhash_similarity(h1, h3)
test("SimHash similarity = 1.0 for identical", sim_same == 1.0, f"Got {sim_same}")
test("SimHash similarity < 1.0 for different", sim_diff < 1.0, f"Got {sim_diff}")

# TF-IDF cosine similarity
tf_sim = tf_idf_cosine_similarity("dark mode preference", "user prefers dark mode")
tf_zero = tf_idf_cosine_similarity("hello world", "量子物理")
test("TF-IDF similarity > 0 for related texts", tf_sim > 0, f"Got {tf_sim}")
test("TF-IDF similarity = 0 for unrelated texts", tf_zero == 0.0 or tf_zero < 0.01, f"Got {tf_zero}")

# Tokenize (Chinese + English)
tokens_en = tokenize("hello world python")
tokens_zh = tokenize("你好世界")
tokens_mix = tokenize("hello 你好 world 世界")
test("English tokenization", len(tokens_en) == 3, f"Got {tokens_en}")
test("Chinese tokenization (bigrams)", len(tokens_zh) >= 2, f"Got {tokens_zh}")
test("Mixed tokenization", len(tokens_mix) >= 4, f"Got {tokens_mix}")

# === TEST: Memory Engine ===
section("Memory Engine (sb_memory)")

# Add memories
m1 = add_memory("User prefers Python over JavaScript", "preference", "user", 0.95, "test")
m2 = add_memory("User prefers dark mode IDE theme", "preference", "user", 0.9, "test")
m3 = add_memory("Project Alpha uses React 18 with TypeScript", "fact", "project-alpha", 0.88, "test")
m4 = add_memory("Decided to use SimHash for semantic search", "decision", "super-brain", 0.85, "test")
m5 = add_memory("Need to write unit tests for auth module", "task", "auth-module", 0.7, "test")
test("Memory add returns valid ID", m1["id"].startswith("mem_"), f"Got {m1['id']}")
test("Memory has SimHash", "simhash" in m1 and m1["simhash"] > 0, "Missing simhash field")
test("Memory type is set", m1["type"] == "preference", f"Got {m1['type']}")

# List memories
all_mems = list_memories(limit=100)
test("List returns all memories", len(all_mems) == 5, f"Got {len(all_mems)}")
prefs = list_memories(mem_type="preference")
test("Filter by type", len(prefs) == 2, f"Got {len(prefs)}")
user_mems = list_memories(entity="user")
test("Filter by entity", len(user_mems) == 2, f"Got {len(user_mems)}")

# Search
results = search("Python preference", limit=5)
test("Search returns results", len(results) > 0, "No results")
test("Search finds Python memory", any("Python" in r[0]["content"] for r in results), "Python not in results")

# Context
ctx = get_context("user preferences", limit=3)
test("Context returns memories", len(ctx.get("memories", [])) > 0, "No memories in context")
test("Context is token-optimized", ctx.get("token_optimized") == True, "Not optimized")
test("Context has summary", "summary" in ctx, "Missing summary")

# Stats
stats = get_stats()
test("Stats show 5 total memories", stats["total"] == 5, f"Got {stats['total']}")
test("Stats show 5 active", stats["active"] == 5, f"Got {stats['active']}")
test("Stats show preference type", "preference" in stats["type_distribution"], f"Got {stats['type_distribution']}")

# === TEST: Knowledge Graph ===
section("Knowledge Graph (sb_graph)")

# Add nodes
n1 = add_node("Super Brain", "tool", ["超脑", "super-brain"])
n2 = add_node("Python", "tool", ["python3"])
n3 = add_node("Alice", "person", ["alice"])
n4 = add_node("Project Alpha", "project", ["proj-a"])
test("Node add returns valid ID", n1["id"].startswith("node_"), f"Got {n1['id']}")
test("Node has aliases", len(n1.get("aliases", [])) == 2, f"Got {n1.get('aliases')}")

# Find node (by name, alias, ID)
found_by_name = find_node("Super Brain")
found_by_alias = find_node("超脑")
found_by_id = find_node(n1["id"])
test("Find node by name", found_by_name is not None, "Not found")
test("Find node by alias (Chinese)", found_by_alias is not None, "Not found")
test("Find node by ID", found_by_id is not None, "Not found")
test("Found correct node", found_by_name["id"] == n1["id"], "Wrong node")

# Entity alignment (adding existing node updates it)
n1_updated = add_node("Super Brain", "tool", ["sb", "brain"])
test("Entity alignment updates existing", n1_updated["id"] == n1["id"], "Created new node instead of updating")
test("Alias merged", "sb" in n1_updated.get("aliases", []), "Alias not merged")

# Add edges
e1 = add_edge("Super Brain", "Python", "uses")
e2 = add_edge("Alice", "Project Alpha", "participates_in")
e3 = add_edge("Super Brain", "Project Alpha", "related_to")
test("Edge add returns valid ID", e1["id"].startswith("edge_"), f"Got {e1['id']}")

# Query graph
q_result = query_graph("Super Brain", depth=2)
test("Graph query returns nodes", q_result.get("nodes_found", 0) > 0, f"Got {q_result}")
test("Graph query returns edges", q_result.get("edges_found", 0) > 0, f"Got {q_result}")
test("Graph query finds connections", len(q_result.get("connections", [])) > 0, "No connections")

# Graph stats
g_stats = get_graph_stats()
test("Graph stats show 4 nodes", g_stats["total_nodes"] == 4, f"Got {g_stats['total_nodes']}")
test("Graph stats show 3 edges", g_stats["total_edges"] == 3, f"Got {g_stats['total_edges']}")
test("No orphan nodes", g_stats["orphan_nodes"] == 0, f"Got {g_stats['orphan_nodes']} orphans")

# === TEST: Self-Check ===
section("Self-Check (sb_selfcheck)")

# Run full check
report = run_full_check(auto_fix=False)
test("Self-check returns report", "checks" in report, "No checks in report")
test("Self-check has 12 checks (v3.7: +3 tail reliability)", len(report.get("checks", {})) == 12, f"Got {len(report.get('checks', {}))} checks")
test("Self-check has timestamp", "timestamp" in report, "Missing timestamp")
test("Self-check has overall status", "overall_status" in report, "Missing overall status")

# Health score
score = get_health_score()
test("Health score is 0-100", 0 <= score <= 100, f"Got {score}")

# Health report
latest = get_health_report()
test("Health report is latest", latest.get("timestamp") == report.get("timestamp"), "Report mismatch")

# === TEST: Duplicate Detection ===
section("Duplicate Detection")

# Add a near-duplicate
m_dup = add_memory("User prefers Python over JavaScript", "preference", "user", 0.9, "test")
issues = find_issues()
test("Issues found duplicates", len(issues.get("duplicates", [])) > 0, "No duplicates found")

# Test merge
if issues.get("duplicates"):
    dup = issues["duplicates"][0]
    merged = merge_memories(dup["id1"], dup["id2"])
    test("Merge returns keeper", merged is not None, "Merge failed")

# === TEST: Workspace ===
section("Workspace Management")

ensure_workspace("test-project")
ws_list = list_workspaces()
test("Workspace list includes default", "default" in ws_list, f"Got {ws_list}")
test("Workspace list includes test-project", "test-project" in ws_list, f"Got {ws_list}")

# === RESULTS ===
section("Results")
print(f"\n  Total: {passed + failed}")
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")
if errors:
    print("\n  Failures:")
    for e in errors:
        print(f"    - {e}")

# Cleanup
for ws in ["test"]:
    write_memories([], ws)
    write_graph({"nodes": {}, "edges": {}}, ws)
switch_workspace(_original_workspace)
print(f"\n  Test data cleaned. Workspace restored to {_original_workspace}.")

sys.exit(0 if failed == 0 else 1)
