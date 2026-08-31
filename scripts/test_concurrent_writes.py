# -*- coding: utf-8 -*-
"""
跨进程并发写安全测试（workspace_lock 互斥 + 写入完整性）。

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并发写回归测试（2026-08-30 并发安全修复配套）。

背景：DSH（鲸砚）/ WorkBuddy（砚）/ tdai-memory 三客户端并发写同一份超脑库，
read→modify→write 序列存在 lost update。修复 = sb_core.workspace_lock +
sb_memory / sb_graph 写事务装饰器。本测试分两组：

  对照组（worker-unlocked）：绕过锁直接 read_memories → sleep → write_memories，
      两个进程交错 → 必然丢数据。用于证明测试本身能捕获丢失（测试有效性）。
  实验组（worker-locked）：走 add_memory（已挂锁），6 进程 × 3 条并发写入，
      期望 18 条全部落盘、零丢失（修复有效性）。

用法：
  python test_concurrent_writes.py run          # 跑完整对照+实验
  python test_concurrent_writes.py worker-unlocked <id>
  python test_concurrent_writes.py worker-locked <id>
"""

import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PY = sys.executable
WS = "test_concurrency_lock"          # 独立测试 workspace，不碰真实数据
N_PROC = 6                             # 实验组并发进程数
N_ADD = 3                              # 每进程写入条数
UNLOCKED_DELAY = 1.5                   # 对照组竞态窗口（秒）


def run_worker(mode, wid):
    """以独立进程跑一个 worker（模拟一个独立的 Agent 客户端）。"""
    return subprocess.Popen(
        [PY, os.path.abspath(__file__), mode, str(wid)],
        cwd=HERE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
    )


def count_memories():
    from sb_core import read_memories
    return len(read_memories(workspace=WS))


def reset_workspace():
    """清空测试 workspace，保证每组实验从零开始。"""
    from sb_core import get_workspace_dir
    ws_dir = get_workspace_dir(WS)
    if os.path.isdir(ws_dir):
        shutil.rmtree(ws_dir)


def phase_unlocked():
    """对照组：无锁路径，2 进程并发 read→sleep→write，期望丢失（证明测试有效）。"""
    print("── 对照组（无锁，期望丢数据）──")
    procs = [run_worker("worker-unlocked", i) for i in range(2)]
    for p in procs:
        p.wait(timeout=60)
    n = count_memories()
    print(f"   写入 2 条，落盘 {n} 条")
    if n == 2:
        print("   ⚠ 竞态未复现（概率性），本次对照不具说服力，但实验组仍有效")
        return None
    print(f"   ✓ 复现 lost update：丢了 {2 - n} 条 —— 测试具备捕获能力")
    return n


def phase_locked():
    """实验组：挂锁路径，6 进程并发 add_memory，期望零丢失。"""
    print("── 实验组（挂锁，期望零丢失）──")
    procs = [run_worker("worker-locked", i) for i in range(N_PROC)]
    fails = []
    for p in procs:
        p.wait(timeout=180)
        if p.returncode != 0:
            fails.append(p.returncode)
    n = count_memories()
    expected = N_PROC * N_ADD
    print(f"   写入 {expected} 条，落盘 {n} 条，失败进程 {len(fails)} 个")
    return n == expected and not fails


def main():
    print("超脑并发写回归测试\n")

    reset_workspace()
    unlocked = phase_unlocked()

    reset_workspace()
    locked_ok = phase_locked()

    print("\n── 结论 ──")
    print(f"  对照组丢失复现：{'是' if unlocked is not None else '未复现（概率性）'}")
    print(f"  实验组零丢失  ：{'✓ PASS' if locked_ok else '✗ FAIL'}")
    if locked_ok:
        print("\n全部通过：跨进程锁有效，lost update 已消除。")
        reset_workspace()  # 清理测试数据
        return 0
    print("\n失败：并发写入仍有丢失或进程报错，锁实现有问题。")
    return 1


def worker_unlocked(wid):
    """绕过锁的裸 read→sleep→write（对照组专用）。"""
    from sb_core import read_memories, write_memories
    mems = read_memories(workspace=WS)
    time.sleep(UNLOCKED_DELAY)  # 拉开竞态窗口：两个进程都完成 read 后才 write
    mems.append({"id": f"unlocked-{wid}", "content": f"raw-write-{wid}",
                 "type": "fact", "entity": "并发测试对照组"})
    write_memories(mems, workspace=WS)


def worker_locked(wid):
    """走正常带锁入口 add_memory（实验组专用，等价于真实客户端路径）。"""
    from sb_memory import add_memory
    for i in range(N_ADD):
        add_memory(content=f"concurrency-test-p{wid}-m{i}",
                   mem_type="fact", entity="并发测试",
                   source="concurrency_test", workspace=WS)
        time.sleep(0.2)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "run":
        sys.exit(main())
    elif mode == "worker-unlocked":
        worker_unlocked(sys.argv[2])
    elif mode == "worker-locked":
        worker_locked(sys.argv[2])
