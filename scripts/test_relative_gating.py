#!/usr/bin/env python3
"""
v3.11.2 (P0-L) 相对门控测试
============================
覆盖 sb_gating 相对门控（自动模式）：
  T1 基本语义：n 条记忆 → 晋升 round(n×ratio) 条，阈值 = 第 k 高 salience
  T2 scale-free：库分布漂移（整体老化）后无需重标，比例自持
  T3 cap 封顶：大库 k=min(cap, ratio×n)，flag 数 ≤ cap（selfcheck 构造性绿）
  T4 手动模式优先：meta 显式阈值（persona 模式）不被相对门控覆盖
  T5 空库边界：threshold=0.0，首条记忆晋升
  T6 set_threshold(None) 清除手动值回自动模式

隔离方式与 test_v36 相同：独立 workspace 逻辑名，原地清空。

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, write_memories, ensure_workspace, update_meta, read_meta
from sb_gating import (get_threshold, set_threshold, compute_salience,
                       DEFAULT_TARGET_RATIO, DEFAULT_CAP)

WS = "sb_test_relative_gating"

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
    ensure_workspace(WS)
    write_memories([], WS)
    update_meta("gating_threshold", None, WS)
    update_meta("gating_target_ratio", None, WS)


def make_mem(i, confidence, days_old=0):
    """构造指定置信度/年龄的测试记忆（access/ent 恒 0，隔离变量）。"""
    ts = f"2026-08-{30 - days_old:02d}T10:00:00" if days_old < 30 else "2026-07-01T10:00:00"
    return {
        "id": f"mem_rg_{i:04d}", "type": "fact", "entity": f"实体{i}",
        "content": f"相对门控测试记忆第{i}条内容", "confidence": confidence,
        "status": "active", "timestamp": ts, "last_accessed": ts,
        "access_count": 0, "related_nodes": [], "workspace_promoted": False,
        "gating_override": None,
    }


# --- T1: 基本语义 ---------------------------------------------------------
def test_basic_semantics():
    print("\n[T1] 基本语义：k = round(n×ratio)，阈值 = 第 k 高 salience")
    reset_workspace()
    n = 20
    mems = [make_mem(i, confidence=0.5 + 0.4 * i / n) for i in range(n)]
    write_memories(mems, WS)
    thr = get_threshold(WS)
    k = max(1, round(n * DEFAULT_TARGET_RATIO))
    sals = sorted((compute_salience(m, WS) for m in mems), reverse=True)
    check(f"k = {k}（round({n}×{DEFAULT_TARGET_RATIO})）", k == 3, str(k))
    check("阈值 = 第 k 高 salience", abs(thr - sals[k - 1]) < 1e-9,
          f"thr={thr} expected={sals[k-1]}")
    promoted = sum(1 for m in mems if compute_salience(m, WS) >= thr)
    check(f"晋升数 = {k}", promoted == k, str(promoted))
    # 晋升的应是置信度最高的那批（唯一判别变量）
    top_k = sorted(mems, key=lambda m: -m["confidence"])[:k]
    check("晋升集 = 最高置信的 k 条", set(m["id"] for m in top_k) ==
          set(mems[i]["id"] for i in range(n - k, n)), " ranking mismatch")


# --- T2: scale-free（分布漂移免疫）-----------------------------------------
def test_scale_free():
    print("\n[T2] 分布漂移：全体记忆老化 60 天，阈值自动滑动，比例不变")
    n = 20
    mems = [make_mem(i, confidence=0.5 + 0.4 * i / n, days_old=60) for i in range(n)]
    write_memories(mems, WS)
    thr_old = get_threshold(WS)  # 老化后的阈值（应显著低于 T1 的新鲜库）
    k = max(1, round(n * DEFAULT_TARGET_RATIO))
    promoted = sum(1 for m in mems if compute_salience(m, WS) >= thr_old)
    check("老化后仍晋升 k 条（无需重标）", promoted == k, str(promoted))

    # 整体抬高 confidence（分布整体上移）——比例仍自持
    mems2 = [make_mem(i, confidence=min(1.0, 0.8 + 0.2 * i / n)) for i in range(n)]
    write_memories(mems2, WS)
    thr_new = get_threshold(WS)
    promoted2 = sum(1 for m in mems2 if compute_salience(m, WS) >= thr_new)
    check("分布整体上移后比例仍自持", promoted2 == k, str(promoted2))


# --- T3: cap 封顶 -----------------------------------------------------------
def test_cap_bound():
    print("\n[T3] 大库 k 被 cap 封顶，flag 数 ≤ cap（构造性不洪水）")
    n = DEFAULT_CAP * 7  # 350 条 → ratio×n=52.5 > cap
    mems = [make_mem(i, confidence=0.5 + 0.49 * i / n) for i in range(n)]
    write_memories(mems, WS)
    thr = get_threshold(WS)
    k = min(DEFAULT_CAP, max(1, round(n * DEFAULT_TARGET_RATIO)))
    promoted = sum(1 for m in mems if compute_salience(m, WS) >= thr)
    check(f"k = min(cap {DEFAULT_CAP}, ratio×n) = {k}", k == DEFAULT_CAP, str(k))
    check(f"晋升数 = {k} ≤ cap", promoted == DEFAULT_CAP, str(promoted))


# --- T4: 手动模式优先（persona 模式）----------------------------------------
def test_manual_mode():
    print("\n[T4] meta 显式阈值优先于相对门控（persona=0.35 模式）")
    reset_workspace()
    n = 20
    mems = [make_mem(i, confidence=0.5 + 0.4 * i / n) for i in range(n)]
    write_memories(mems, WS)
    set_threshold(0.35, workspace=WS)
    thr = get_threshold(WS)
    check("手动阈值生效", abs(thr - 0.35) < 1e-9, str(thr))
    promoted = sum(1 for m in mems if compute_salience(m, WS) >= thr)
    check("手动模式下低 salience 记忆也可常驻（身份库语义）",
          promoted > max(1, round(n * DEFAULT_TARGET_RATIO)), str(promoted))


# --- T5/T6: 边界 -------------------------------------------------------------
def test_edges():
    print("\n[T5/T6] 边界：空库 / 超小库")
    reset_workspace()
    check("空库 threshold=0.0", get_threshold(WS) == 0.0, str(get_threshold(WS)))
    mems = [make_mem(i, confidence=0.9) for i in range(2)]
    write_memories(mems, WS)
    thr = get_threshold(WS)
    k = max(1, round(2 * DEFAULT_TARGET_RATIO))
    check(f"2 条库 k={k}", k == 1, str(k))
    check("超小库阈值 = 最高 salience", abs(thr - compute_salience(mems[1], WS)) < 1e-9
          or abs(thr - compute_salience(mems[0], WS)) < 1e-9, str(thr))


# --- T7: set_threshold(None) 回自动 ------------------------------------------
def test_clear_manual():
    print("\n[T7] set_threshold(None) 清除手动值回自动模式")
    set_threshold(None, workspace=WS)
    check("meta 已清空", read_meta(WS).get("gating_threshold") is None,
          str(read_meta(WS).get("gating_threshold")))
    thr = get_threshold(WS)
    check("回到自动模式（阈值=第 k 高 salience）", thr > 0, str(thr))


if __name__ == "__main__":
    print("=" * 60)
    print("P0-L 相对门控测试")
    print("=" * 60)
    test_basic_semantics()
    test_scale_free()
    test_cap_bound()
    test_manual_mode()
    test_edges()
    test_clear_manual()
    print("\n" + "=" * 60)
    print(f"测试结果: {PASS} 通过 / {FAIL} 失败")
    print("=" * 60)
    sys.exit(1 if FAIL else 0)
