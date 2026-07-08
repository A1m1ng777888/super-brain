#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperBrain v3.6.0 测试套件 — 全局工作空间门控层 + 中间推理捕获
Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
=============================================================
覆盖：
  T1 salience 单调性（confidence / recency / access / entanglement）
  T2 chain_ignite 链式点燃
  T3 reasoning_intermediate 落库（capture_reasoning_chain）
  T4 get_active_workspace 子集 / 容量上限
  T5 memory context --workspace-only 选择性过滤
  T6 门控 CLI 处理函数可调用性
  T7 v3.6.1 自动晋升（add_memory / longterm ingest 入库即晋升）+ demote 修复
全程使用隔离的 "test" workspace，不触碰生产数据。
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import ensure_workspace, read_memories, write_memories
from sb_memory import add_memory, get_context, MEMORY_TYPES
from sb_reasoning import capture_reasoning_chain
from sb_longterm import auto_ingest
from sb_gating import (
    compute_salience, chain_ignite, get_active_workspace,
    set_threshold, get_threshold, promote, demote, calibrate,
    DEFAULT_THRESHOLD, DEFAULT_CAP
)

WS = "test"
DATA_ROOT = os.path.join(
    os.path.dirname(os.path.expanduser("~")),
    ".workbuddy", "super-brain", "workspaces"
)
WS_DIR = os.path.join(DATA_ROOT, WS)

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
    """清空隔离 workspace，确保测试幂等。
    注意：沙箱禁止 rmtree，故用 write_memories([]) 原地清空记忆替代删除目录。"""
    ensure_workspace(WS)
    write_memories([], WS)
    # 固定阈值，消除默认阈值波动
    set_threshold(0.5, workspace=WS)


# --- T1: salience 单调性 --------------------------------------------------
def test_salience_monotonicity():
    print("\n[T1] salience 单调性")
    base = {
        "type": "fact", "confidence": 0.5, "access_count": 0,
        "related_nodes": [], "last_accessed": None, "timestamp": None,
        "status": "active",
    }
    # confidence 越高 salience 越高
    low = dict(base, confidence=0.2)
    high = dict(base, confidence=0.9)
    check("confidence 越高 salience 越高",
          compute_salience(low, WS) < compute_salience(high, WS),
          f"{compute_salience(low, WS)} !< {compute_salience(high, WS)}")
    # access_count 越高 salience 越高
    cold = dict(base, access_count=0)
    hot = dict(base, access_count=10)
    check("access_count 越高 salience 越高",
          compute_salience(cold, WS) < compute_salience(hot, WS),
          f"{compute_salience(cold, WS)} !< {compute_salience(hot, WS)}")
    # entanglement 越高 salience 越高
    lone = dict(base, related_nodes=[])
    linked = dict(base, related_nodes=["a", "b", "c"])
    check("entanglement 越高 salience 越高",
          compute_salience(lone, WS) < compute_salience(linked, WS),
          f"{compute_salience(lone, WS)} !< {compute_salience(linked, WS)}")
    # reasoning_intermediate 基线更冷（同等信号下低于 fact）
    fact_mem = dict(base, type="fact", confidence=0.7)
    reason_mem = dict(base, type="reasoning_intermediate", confidence=0.7)
    check("reasoning_intermediate 基线低于 fact",
          compute_salience(reason_mem, WS) < compute_salience(fact_mem, WS),
          f"{compute_salience(reason_mem, WS)} !< {compute_salience(fact_mem, WS)}")
    # salience 落在 [0,1]
    s = compute_salience(dict(base, confidence=1.0, access_count=99,
                              related_nodes=["x"] * 9), WS)
    check("salience 落在 [0,1]", 0.0 <= s <= 1.0, f"salience={s}")


# --- T2: chain_ignite 链式点燃 --------------------------------------------
def test_chain_ignite():
    print("\n[T2] chain_ignite 链式点燃")
    reset_workspace()
    cid = "chain_test_001"
    # 三个低显著度节点，默认阈值下都进不了工作空间
    for i in range(3):
        add_memory(
            content=f"中间推理节点 {i}",
            mem_type="reasoning_intermediate",
            entity="gwt",
            confidence=0.3,  # 低 -> 默认不会晋升
            workspace=WS,
            attributes={"chain_id": cid, "reasoning_role": f"step_{i}"}
        )
    # 手动标注 chain_id（add_memory 不直接支持，这里补写）
    mems = read_memories(WS)
    for m in mems:
        m["chain_id"] = cid
    write_memories(mems, WS)

    before = get_active_workspace(WS, cap=DEFAULT_CAP)
    check("点燃前无晋升节点", len(before) == 0, f"active={len(before)}")

    # 手动点燃其中一个
    target = read_memories(WS)[0]
    promote(target["id"], workspace=WS)

    res = chain_ignite(WS)
    check("chain_ignite 报告整链点燃", res["chain_promoted"] >= 1, str(res))
    check("chain_ignite 改变了 >=2 个节点", res["changed"] >= 2, str(res))

    after = get_active_workspace(WS, cap=DEFAULT_CAP)
    check("点燃后整链都晋升", len(after) == 3, f"active={len(after)}")


# --- T3: reasoning_intermediate 落库 --------------------------------------
def test_reasoning_capture():
    print("\n[T3] reasoning_intermediate 落库")
    reset_workspace()
    text = ("要决定采用门控层，需要先评估选择性原则。"
            "论文指出中间推理概念会因果驱动答案。"
            "因此我们捕获推理链而非只保留结论。")
    res = capture_reasoning_chain(text, workspace=WS)
    check("返回 chain_id", bool(res.get("chain_id")), str(res))
    check("至少捕获 1 个中间节点", res.get("stored", 0) >= 1, str(res))

    mems = read_memories(WS)
    reasons = [m for m in mems if m.get("type") == "reasoning_intermediate"]
    check("落库类型为 reasoning_intermediate", len(reasons) >= 1, f"count={len(reasons)}")
    check("节点共享顶层 chain_id", len(set(m["chain_id"] for m in reasons)) == 1,
          f"chains={set(m['chain_id'] for m in reasons)}")
    check("reasoning_intermediate 是合法类型",
          "reasoning_intermediate" in MEMORY_TYPES)


# --- T4: get_active_workspace 子集 / 容量 ---------------------------------
def test_active_workspace():
    print("\n[T4] get_active_workspace 子集 / 容量")
    reset_workspace()
    set_threshold(0.5, workspace=WS)  # 0.5 高于新鲜记忆的显著度下限(0.30)，可区分高低置信
    # 10 个高置信 fact（显著度 ~0.585 -> 晋升）
    for i in range(10):
        add_memory(content=f"事实 {i}", mem_type="fact", entity="x",
                   confidence=0.95, workspace=WS)
    # 5 个低置信 fact（显著度 ~0.33 -> 不晋升）
    for i in range(5):
        add_memory(content=f"弱事实 {i}", mem_type="fact", entity="y",
                   confidence=0.1, workspace=WS)

    full = get_active_workspace(WS, cap=DEFAULT_CAP)
    check("高置信晋升且低置信不晋升（共10）", len(full) == 10, f"active={len(full)}")

    capped = get_active_workspace(WS, cap=3)
    check("容量上限生效", len(capped) == 3, f"capped={len(capped)}")

    # 子集性质：活跃工作空间 ⊆ 活跃记忆
    active_all = [m for m in read_memories(WS) if m.get("status") == "active"]
    check("活跃工作空间是活跃记忆的子集",
          all(any(a["id"] == m["id"] for m in active_all) for a in capped))


# --- T5: context --workspace-only 选择性 ----------------------------------
def test_context_workspace_only():
    print("\n[T5] memory context --workspace-only 选择性")
    reset_workspace()
    set_threshold(0.5, workspace=WS)
    add_memory(content="高亮事实 关于 gwt", mem_type="fact", entity="gwt",
               confidence=0.95, workspace=WS)
    add_memory(content="冷事实 关于 gwt", mem_type="fact", entity="gwt",
               confidence=0.1, workspace=WS)

    get_active_workspace(WS, cap=DEFAULT_CAP)  # 先打 workspace_promoted 标记

    ctx_all = get_context("gwt", limit=10, workspace=WS)
    ctx_gw = get_context("gwt", limit=10, workspace=WS, workspace_only=True)
    check("全量 context 包含冷记忆", len(ctx_all["memories"]) >= 2,
          f"all={len(ctx_all['memories'])}")
    check("workspace_only 仅保留晋升记忆",
          all(m.get("workspace_promoted") for m in ctx_gw["memories"]),
          f"gw_flags={[m.get('workspace_promoted') for m in ctx_gw['memories']]}")
    check("workspace_only 结果 <= 全量结果",
          len(ctx_gw["memories"]) <= len(ctx_all["memories"]))


# --- T6: 门控 CLI 处理函数可调用性 ----------------------------------------
def test_gating_cli_functions():
    print("\n[T6] 门控 CLI 处理函数可调用性")
    reset_workspace()
    add_memory(content="cli 测试记忆", mem_type="fact", entity="cli",
               confidence=0.9, workspace=WS)
    mid = read_memories(WS)[-1]["id"]

    t = get_threshold(WS)
    check("get_threshold 返回浮点", isinstance(t, float), str(t))

    set_threshold(0.42, workspace=WS)
    check("set_threshold 持久化", abs(get_threshold(WS) - 0.42) < 1e-9)

    cal = calibrate(workspace=WS)
    check("calibrate 返回 ratio", "promotion_ratio" in cal, str(cal))

    res = demote(mid, workspace=WS)
    check("demote 可调用", res.get("demoted") in (True, False), str(res))

    res = promote(mid, workspace=WS)
    check("promote 可调用", res.get("promoted") in (True, False), str(res))


# --- T7: v3.6.1 自动晋升 + demote 修复 -----------------------------------
def test_auto_promotion_and_demote():
    print("\n[T7] v3.6.1 自动晋升（入库即晋升）+ demote 修复")
    reset_workspace()
    set_threshold(0.5, workspace=WS)  # 高于新鲜记忆显著度下限，可区分高低置信

    # --- T2: 入库即晋升（单点接 add_memory，覆盖 memory add / auto_store / longterm ingest）---
    m_hi = add_memory(content="重要事实 关于 gwt 门控层", mem_type="fact",
                      entity="gwt", confidence=0.95, workspace=WS)
    m_lo = add_memory(content="弱事实 关于 gwt 冷存储", mem_type="fact",
                      entity="gwt", confidence=0.1, workspace=WS)
    check("高置信入库即晋升", m_hi["workspace_promoted"] is True,
          str(m_hi["workspace_promoted"]))
    check("低置信入库不晋升", m_lo["workspace_promoted"] is False,
          str(m_lo["workspace_promoted"]))
    check("salience 为真实显著度(非裸 confidence 占位)",
          abs(m_hi["salience"] - compute_salience(m_hi, WS)) < 1e-9
          and m_hi["salience"] != m_hi["confidence"],
          f"salience={m_hi['salience']} conf={m_hi['confidence']}")
    check("高置信 salience >= 阈值", m_hi["salience"] >= get_threshold(WS))
    check("低置信 salience < 阈值", m_lo["salience"] < get_threshold(WS))

    # --- longterm ingest 入口同样自动晋升 ---
    res = auto_ingest(
        "牛顿是经典力学的奠基人，提出了三大运动定律。这一发现改变了物理学。",
        workspace=WS)
    check("longterm ingest 有产物", len(res.get("stored", [])) >= 1, str(res)[:120])
    ingested_ids = [s["id"] for s in res.get("stored", [])]
    ingested_mems = [m for m in read_memories(WS) if m["id"] in ingested_ids]
    check("ingest 产物 salience 已计算(=compute_salience，无占位残留)",
          all(abs(m["salience"] - compute_salience(m, WS)) < 1e-9 for m in ingested_mems),
          "存在未覆盖占位的记忆")
    check("ingest 产物带 workspace_promoted 布尔标记",
          all(isinstance(m.get("workspace_promoted"), bool) for m in ingested_mems))

    # --- T4 修复：promote 低置信 -> demote -> 不应再出现（修复前 demote 被 salience 覆盖失效）---
    promote(m_lo["id"], workspace=WS)
    active_after_promote = [m["id"] for m in get_active_workspace(WS, cap=DEFAULT_CAP)]
    check("promote 后低置信进入工作空间", m_lo["id"] in active_after_promote)
    demote(m_lo["id"], workspace=WS)
    active_after_demote = [m["id"] for m in get_active_workspace(WS, cap=DEFAULT_CAP)]
    check("demote 修复：demote 后不再出现(修复前 bug 会返回 True)",
          m_lo["id"] not in active_after_demote)
    m_lo_after = [m for m in read_memories(WS) if m["id"] == m_lo["id"]][0]
    check("demote 写入 gating_override='demote'",
          m_lo_after.get("gating_override") == "demote")


if __name__ == "__main__":
    ensure_workspace(WS)

    test_salience_monotonicity()
    test_chain_ignite()
    test_reasoning_capture()
    test_active_workspace()
    test_context_workspace_only()
    test_gating_cli_functions()
    test_auto_promotion_and_demote()

    # 清理隔离 workspace（避免 rmtree，沙箱禁用；原地清空记忆）
    write_memories([], WS)

    print(f"\n=== v3.6 测试结果: {PASS} 通过 / {FAIL} 失败 ===")
    sys.exit(1 if FAIL else 0)
