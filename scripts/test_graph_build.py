#!/usr/bin/env python3
"""
v3.11.2 (P0-I) 自动建图测试
============================
覆盖 sb_graph.build_from_memories：
  T1 基本建图：实体→节点、top-K 建边、related_nodes 回填
  T2 general/空实体不建节点、不回填
  T3 幂等性：重复执行不新增节点/边、related_nodes 不重复
  T4 推理链记忆 ID 保护：回填合并不覆盖既有 related_nodes
  T5 dry_run 不落盘

隔离方式与 test_v36 相同：独立 workspace 逻辑名，原地清空，不碰真实库。

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, write_memories, ensure_workspace, read_graph, write_graph
from sb_graph import build_from_memories, find_node

WS = "sb_test_graph_build"

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def reset_workspace():
    """清空隔离 workspace（沙箱禁止 rmtree，用空写替代删除目录）。"""
    ensure_workspace(WS)
    write_memories([], WS)
    write_graph({"nodes": {}, "edges": {}}, WS)


def seed():
    """三个有词面重叠的实体 + 一个 general + 一个链式 related_nodes 保护样本。"""
    write_memories([
        {"id": "mem_t1_a1", "type": "fact", "entity": "苹果", "content": "苹果公司发布了新款 MacBook 电脑",
         "confidence": 0.9, "status": "active", "timestamp": "2026-08-01T10:00:00",
         "related_nodes": [], "access_count": 0},
        {"id": "mem_t1_a2", "type": "fact", "entity": "苹果", "content": "苹果的 macOS 系统更新了深色模式",
         "confidence": 0.9, "status": "active", "timestamp": "2026-08-02T10:00:00",
         "related_nodes": [], "access_count": 0},
        {"id": "mem_t1_b1", "type": "fact", "entity": "微软", "content": "微软 Windows 系统发布了新版本电脑体验",
         "confidence": 0.9, "status": "active", "timestamp": "2026-08-03T10:00:00",
         "related_nodes": [], "access_count": 0},
        {"id": "mem_t1_b2", "type": "fact", "entity": "微软", "content": "微软的 Surface 电脑用 Windows 系统",
         "confidence": 0.9, "status": "active", "timestamp": "2026-08-04T10:00:00",
         "related_nodes": [], "access_count": 0},
        {"id": "mem_t1_c1", "type": "event", "entity": "做饭", "content": "今天中午做了一碗西红柿鸡蛋面",
         "confidence": 0.8, "status": "active", "timestamp": "2026-08-05T10:00:00",
         "related_nodes": [], "access_count": 0},
        {"id": "mem_t1_g1", "type": "fact", "entity": "general", "content": "苹果 微软 系统电脑相关但未分类的记忆",
         "confidence": 0.9, "status": "active", "timestamp": "2026-08-06T10:00:00",
         "related_nodes": [], "access_count": 0},
        # 链式保护样本：related_nodes 已有记忆 ID（capture_reasoning_chain 的产物）
        {"id": "mem_t1_chain", "type": "reasoning_intermediate", "entity": "苹果",
         "content": "苹果macbook电脑系统推理中间步骤记录",
         "confidence": 0.7, "status": "active", "timestamp": "2026-08-07T10:00:00",
         "related_nodes": ["mem_t1_a1"], "access_count": 0},
    ], WS)


# --- T1: 基本建图 ---------------------------------------------------------
def test_basic_build():
    print("\n[T1] 基本建图：实体→节点、建边、related_nodes 回填")
    reset_workspace()
    seed()
    r = build_from_memories(workspace=WS)

    check("返回统计无 error", "error" not in r, str(r))
    graph = read_graph(WS)
    nodes = graph["nodes"]
    by_name = {n["name"]: n for n in nodes.values()}

    check("连通实体建了节点", {"苹果", "微软"} <= set(by_name), f"nodes={sorted(by_name)}")
    check("general 未建节点", "general" not in by_name, f"nodes={sorted(by_name)}")
    check("孤立实体不建节点（无边节点会被 selfcheck orphans 告警）",
          "做饭" not in by_name, f"nodes={sorted(by_name)}")

    apple = by_name.get("苹果")
    check("节点挂载成员记忆", apple and "mem_t1_a1" in apple["related_memories"]
          and "mem_t1_chain" in apple["related_memories"], str(apple))

    # 苹果↔微软 应有边（共享 电脑/系统 等词），做饭 应是孤立实体
    pairs = {(e["source"], e["target"]) for e in graph["edges"].values()}
    ids = {n["name"]: n["id"] for n in nodes.values()}
    check("苹果↔微软 建边", (ids["苹果"], ids["微软"]) in pairs or (ids["微软"], ids["苹果"]) in pairs,
          f"pairs={pairs}")

    mems = {m["id"]: m for m in read_memories(WS)}
    check("孤立实体的记忆不回填（related_nodes 为空）",
          mems["mem_t1_c1"]["related_nodes"] == [], str(mems["mem_t1_c1"]["related_nodes"]))
    apple_related = mems["mem_t1_a1"]["related_nodes"]
    check("成员记忆回填 related_nodes 含自身节点", ids["苹果"] in apple_related, str(apple_related))
    check("ent_score 刻度：回填数 ≤5", len(apple_related) <= 5, str(apple_related))
    return r


# --- T2: general 与空实体跳过 ---------------------------------------------
def test_general_skipped():
    print("\n[T2] general/空实体不建节点不回填")
    mems = {m["id"]: m for m in read_memories(WS)}
    check("general 记忆 related_nodes 仍为空", mems["mem_t1_g1"]["related_nodes"] == [],
          str(mems["mem_t1_g1"]["related_nodes"]))


# --- T3: 幂等性 -------------------------------------------------------------
def test_idempotent():
    print("\n[T3] 重复执行不新增节点/边，related_nodes 不重复")
    before_nodes = len(read_graph(WS)["nodes"])
    before_edges = len(read_graph(WS)["edges"])
    r = build_from_memories(workspace=WS)
    graph = read_graph(WS)
    check("节点数不变", len(graph["nodes"]) == before_nodes,
          f"{before_nodes} → {len(graph['nodes'])}")
    check("边数不变", len(graph["edges"]) == before_edges,
          f"{before_edges} → {len(graph['edges'])}")
    mems = {m["id"]: m for m in read_memories(WS)}
    rel = mems["mem_t1_a1"]["related_nodes"]
    check("related_nodes 无重复", len(rel) == len(set(rel)), str(rel))


# --- T4: 链式记忆 ID 保护 ----------------------------------------------------
def test_chain_links_protected():
    print("\n[T4] 推理链记忆 ID 不被回填覆盖")
    mems = {m["id"]: m for m in read_memories(WS)}
    rel = mems["mem_t1_chain"]["related_nodes"]
    check("链式记忆 ID 保留在首位", rel and rel[0] == "mem_t1_a1", str(rel))
    check("链式记忆同时获得图节点链接", any(i.startswith("node_") for i in rel), str(rel))


# --- T5: dry_run 不落盘 ------------------------------------------------------
def test_dry_run():
    print("\n[T5] dry_run 不落盘")
    reset_workspace()
    seed()
    before = (read_graph(WS), read_memories(WS))
    r = build_from_memories(workspace=WS, dry_run=True)
    after = (read_graph(WS), read_memories(WS))
    check("dry_run 标记返回", r.get("dry_run") is True, str(r.get("dry_run")))
    check("graph 未写入", before[0] == after[0])
    check("memories 未写入", before[1] == after[1])


if __name__ == "__main__":
    print("=" * 60)
    print("P0-I 自动建图测试")
    print("=" * 60)
    test_basic_build()
    test_general_skipped()
    test_idempotent()
    test_chain_links_protected()
    test_dry_run()
    print("\n" + "=" * 60)
    print(f"测试结果: {PASS} 通过 / {FAIL} 失败")
    print("=" * 60)
    sys.exit(1 if FAIL else 0)
