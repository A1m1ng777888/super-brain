# -*- coding: utf-8 -*-
"""
superbrain-bench 性能基准导入压测（LOCOMO conv-26 模拟，进程内循环不 fork）。

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量导入性能基准测试（P0-0 前置验证）

目的
----
证明当前 `add_memory` 逐条写入的开销随库规模增长（全量读盘 + O(N) 冲突检测 +
全量写盘 + 审计日志读写），灌入 LOCOMO 的 5882 turns 不可行。

设计
----
- 分阶段写入，观察**耗时随库规模的增长曲线**（判断是 O(N) 还是 O(N²)）
- 若 sb_memory 已提供 `add_memories_batch`，则同时测批量模式做对比
- 脚本在改动前后都能运行，用于前后对比

隔离
----
用 SUPERBRAIN_DATA_DIR 指向临时目录，不触碰真实数据。运行结束自动清理。

运行
----
    python test_batch_import.py          # 默认每阶段 200 条，共 3 阶段
    python test_batch_import.py 300 4    # 每阶段 300 条，共 4 阶段
"""

import sys
import os
import time
import shutil
import tempfile

# 必须在 import sb_core 之前设置——超脑测试隔离约定（见 test_p1.py / test_v3.py）
TEST_DATA = tempfile.mkdtemp(prefix="sb_batch_bench_")
os.environ["SUPERBRAIN_DATA_DIR"] = TEST_DATA

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_memory import add_memory  # noqa: E402

try:
    from sb_memory import add_memories_batch  # noqa: E402
    HAS_BATCH = True
except ImportError:
    HAS_BATCH = False


# LOCOMO 实测规模：5882 turns（见 项目档案/超脑竞品对标矩阵_20260830.md §5.2）
LOCOMO_TURNS = 5882


def _make_content(i, phase):
    """生成互不重复的内容，避免触发重复合并而掩盖真实开销。"""
    return f"phase{phase} memory {i}: 基准测试样本内容，用于测量写入开销随库规模的变化。"


def bench_sequential(ws, n_new, phase, base_count):
    """逐条调用 add_memory，返回 (耗时秒, 成功条数)。"""
    t0 = time.perf_counter()
    ok = 0
    for i in range(n_new):
        add_memory(
            content=_make_content(i, phase),
            mem_type="fact",
            entity="bench",
            confidence=0.8,
            source="bench",
            workspace=ws,
        )
        ok += 1
    elapsed = time.perf_counter() - t0
    return elapsed, ok


def bench_batch(ws, n_new, phase):
    """一次性调用 add_memories_batch，返回 (耗时秒, 成功条数)。"""
    specs = [
        {
            "content": _make_content(i, phase),
            "mem_type": "fact",
            "entity": "bench",
            "confidence": 0.8,
            "source": "bench",
        }
        for i in range(n_new)
    ]
    t0 = time.perf_counter()
    created = add_memories_batch(specs, workspace=ws)
    elapsed = time.perf_counter() - t0
    return elapsed, len(created)


def fmt_dur(sec):
    """秒 → 人类可读时长。"""
    if sec < 60:
        return f"{sec:.1f}s"
    if sec < 3600:
        return f"{sec / 60:.1f}min"
    return f"{sec / 3600:.2f}h"


def main():
    per_phase = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    n_phases = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    print("=" * 68)
    print(" 超脑批量导入性能基准（P0-0 验证）")
    print("=" * 68)
    print(f" 隔离数据目录 : {TEST_DATA}")
    print(f" 每阶段条数   : {per_phase}")
    print(f" 阶段数       : {n_phases}")
    print(f" 批量函数可用 : {'是' if HAS_BATCH else '否（仅测逐条写入现状）'}")
    print(f" 外推目标     : LOCOMO {LOCOMO_TURNS} turns")
    print()

    ws_seq = "bench_seq"
    results = []

    print("-" * 68)
    print("【A】逐条 add_memory（当前现状）")
    print("-" * 68)
    print(f"{'阶段':<6}{'库规模(前→后)':<18}{'耗时':>10}{'吞吐':>12}{'单条':>10}")
    base = 0
    for phase in range(1, n_phases + 1):
        elapsed, ok = bench_sequential(ws_seq, per_phase, phase, base)
        rate = ok / elapsed if elapsed > 0 else 0
        per_item = elapsed / ok * 1000 if ok else 0
        print(
            f"{phase:<6}{f'{base}→{base + ok}':<18}"
            f"{fmt_dur(elapsed):>10}{rate:>10.1f}/s{per_item:>9.1f}ms"
        )
        results.append({"base": base, "elapsed": elapsed, "n": ok, "rate": rate})
        base += ok

    # 增长曲线分析：比较首尾两个阶段的单条耗时
    first = results[0]
    last = results[-1]
    degrade = last["elapsed"] / first["elapsed"] if first["elapsed"] > 0 else 0
    print()
    print(f" 单阶段耗时退化倍数（第{n_phases}阶段 / 第1阶段）: {degrade:.2f}×")

    if degrade >= 1.3:
        print(" → 判定：**超线性增长**（库越大写得越慢，逐条写入不可扩展）")
    else:
        print(" → 判定：近似线性（瓶颈恒定，主要是一次性开销）")

    # 外推到 LOCOMO 全量
    # 用最后一阶段的吞吐外推（最保守，因为库最大时最慢）
    worst_rate = last["rate"]
    extrapolated = LOCOMO_TURNS / worst_rate if worst_rate > 0 else float("inf")
    print()
    print(f" 外推 LOCOMO {LOCOMO_TURNS} 条（按最慢阶段吞吐 {worst_rate:.1f}/s）: "
          f"**{fmt_dur(extrapolated)}**")

    if HAS_BATCH:
        print()
        print("-" * 68)
        print("【B】add_memories_batch（优化后）")
        print("-" * 68)
        ws_batch = "bench_batch"
        print(f"{'阶段':<6}{'库规模(前→后)':<18}{'耗时':>10}{'吞吐':>12}{'单条':>10}")
        base_b = 0
        batch_results = []
        for phase in range(1, n_phases + 1):
            elapsed, ok = bench_batch(ws_batch, per_phase, phase)
            rate = ok / elapsed if elapsed > 0 else 0
            per_item = elapsed / ok * 1000 if ok else 0
            print(
                f"{phase:<6}{f'{base_b}→{base_b + ok}':<18}"
                f"{fmt_dur(elapsed):>10}{rate:>10.1f}/s{per_item:>9.1f}ms"
            )
            batch_results.append({"elapsed": elapsed, "n": ok, "rate": rate})
            base_b += ok

        total_seq = sum(r["elapsed"] for r in results)
        total_batch = sum(r["elapsed"] for r in batch_results)
        total_n = sum(r["n"] for r in results)
        speedup = total_seq / total_batch if total_batch > 0 else 0
        batch_rate = total_n / total_batch if total_batch > 0 else 0
        extrapolated_batch = LOCOMO_TURNS / batch_rate if batch_rate > 0 else float("inf")

        print()
        print(f" 同等工作量（{total_n} 条）: 逐条 {fmt_dur(total_seq)} → 批量 {fmt_dur(total_batch)}"
              f"  **提速 {speedup:.1f}×**")
        print(f" 外推 LOCOMO {LOCOMO_TURNS} 条（批量模式）: **{fmt_dur(extrapolated_batch)}**")
        print()
        if extrapolated_batch < 600:
            print(" ✅ 批量模式可在 10 分钟内灌完 LOCOMO，P0-0 目标达成")
        else:
            print(" ⚠ 批量模式仍未达标，需要进一步优化")

    print()
    print("=" * 68)
    if not HAS_BATCH:
        print(" 结论：当前逐条写入外推需 "
              f"{fmt_dur(extrapolated)}，P0-0 必须先解决。")
    print("=" * 68)

    # 清理
    shutil.rmtree(TEST_DATA, ignore_errors=True)


if __name__ == "__main__":
    main()
