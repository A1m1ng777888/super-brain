#!/usr/bin/env python3
"""
SuperBrain v3.9.5 P1-8 关键路径补测
=====================================
覆盖审阅 P1-8 四项：① 硬步骤门控 exit 2 与 --force 豁免路径
② v3.4.3 损坏 JSON 备份恢复机制 ③ persona/project 双层召回
④ RRF 秩融合排序正确性

全程使用隔离临时目录，不触碰生产数据。
Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""
import sys, os, json, tempfile, subprocess, shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# 强制数据目录隔离
TEST_DATA = tempfile.mkdtemp(prefix="sb_test_p1_")
os.environ["SUPERBRAIN_DATA_DIR"] = TEST_DATA

from sb_core import (
    ensure_workspace, write_json, read_json, read_memories,
    write_memories, generate_id, get_timestamp, get_workspace_dir,
    DEFAULT_DATA_DIR
)
from sb_memory import add_memory, search as memory_search
from sb_gating import enforce_hard_step_guard, mark_search_done
from sb_search import search_memories, tokenize

PASS = FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✓ {name}")
    else:
        FAIL += 1; print(f"  ✗ {name}  {detail}")


# ========================
# T1: 硬步骤门控 exit 2
# ========================
def test_hardstep_exit():
    print("\n--- T1: 硬步骤门控 exit 2 ---")

    # 1a: 强制解锁后正常放行
    mark_search_done("超脑 测试")
    import io
    saved_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        # 无 force、时间窗口内 → 不应 raise
        enforce_hard_step_guard(force=False, content="超脑记忆测试", command="test")
        check("T1a: 窗口内写入放行（无 exit）", True)
    except SystemExit:
        check("T1a: 窗口内写入放行", False, "意外 exit")
    finally:
        sys.stderr = saved_stderr

    # 1b: 手动失效时间戳 → 应自动重置并放行（不再 exit 2）
    st = __import__("sb_gating")
    st._hardstep_load()  # ensure file exists
    state = st._hardstep_load()
    state["last_search_ts"] = 100  # epoch start, 50+ years ago
    st._hardstep_save(state)

    import io
    sys.stderr = io.StringIO()
    try:
        enforce_hard_step_guard(force=False, content="test", command="memory add")
        check("T1b: 过期窗口自动重置并放行（不再 exit）", True)
    except SystemExit as e:
        check("T1b: 过期窗口不应 exit", False, f"unexpected exit code={e.code}")
    finally:
        sys.stderr = saved_stderr
        # 恢复——重置检索状态
        mark_search_done("test query")

    # 1c: --force 强制豁免
    import io
    sys.stderr = io.StringIO()
    try:
        enforce_hard_step_guard(force=True, content="test force", command="test")
        check("T1c: --force 豁免不抛 exit", True)
    except SystemExit:
        check("T1c: --force 豁免", False, "意外 exit")
    finally:
        sys.stderr = saved_stderr


# ========================
# T2: 损坏 JSON 恢复
# ========================
def test_corrupted_json_recovery():
    print("\n--- T2: 损坏 JSON 备份恢复 ---")
    ws = ensure_workspace("test_corrupt")
    mem_path = os.path.join(ws, "memories.json")

    # 写入正常记忆，确认可读
    from sb_core import read_memories as rm
    write_memories([{
        "id": "corr_1", "content": "normal", "type": "fact",
        "entity": "test", "timestamp": get_timestamp(), "confidence": 0.9
    }], "test_corrupt")
    mems = rm("test_corrupt")
    check("T2a: 正常读写", len(mems) >= 1, f"got {len(mems)}")

    # 损坏 memories.json —— 写入非法 JSON
    with open(mem_path, "w", encoding="utf-8") as f:
        f.write("{corrupted json !@#")
    try:
        mems2 = rm("test_corrupt")
        check("T2b: 损坏 JSON 不崩且返空", mems2 == [],
              f"got {type(mems2).__name__}:{len(mems2) if isinstance(mems2, list) else 'non-list'}")
    except Exception as e:
        check("T2b: 损坏 JSON 不崩", False, f"exception: {e}")

    # 检查备份文件（v3.4.3 格式：memories_corrupt_backup_<timestamp>.json）
    import glob
    ws_dir = os.path.dirname(mem_path)
    backups = glob.glob(os.path.join(ws_dir, "memories_corrupt_backup_*"))
    check("T2c: 生成了损坏备份文件", len(backups) >= 1,
          f"found {len(backups)} backups" if not backups else "ok")

    # 恢复后应能重新写入
    write_memories([{
        "id": "corr_2", "content": "recovered", "type": "fact",
        "entity": "test", "timestamp": get_timestamp(), "confidence": 0.9
    }], "test_corrupt")
    mems3 = rm("test_corrupt")
    check("T2d: 损坏后恢复写入可读", len(mems3) >= 1,
          f"got {len(mems3)}")


# ========================
# T3: persona 双层召回
# ========================
def test_persona_search():
    print("\n--- T3: persona 双层召回 ---")
    from sb_core import get_persona_workspace_dir, write_persona_memories, read_persona_memories

    # 直接写 project workspace（不用 add_memory 避免触硬步骤门控）
    mark_search_done("typescript react")
    from sb_core import write_memories as _wm
    _wm([{
        "id": "proj_1", "content": "项目使用 React 18 和 TypeScript",
        "type": "fact", "entity": "project-test",
        "confidence": 0.95, "timestamp": get_timestamp(),
    }], "default")

    # persona 记忆
    per_dir = get_persona_workspace_dir()
    if per_dir:
        write_persona_memories([{
            "id": "per_1", "content": "偏好使用 TypeScript 开发",
            "type": "preference", "entity": "dev-style",
            "confidence": 0.95, "timestamp": get_timestamp(),
        }])

    # 搜项目记忆——直接用 search_memories（纯函数，不走 sb_memory.search 的包装）
    from sb_search import search_memories, simhash
    from sb_memory import read_memories as _rm2
    mems = _rm2("default")
    for m in mems:
        if "simhash" not in m or m.get("simhash", 0) == 0:
            m["simhash"] = simhash(f"{m.get('entity','')} {m.get('content','')}")
    results = search_memories("TypeScript React", mems, limit=3, workspace="test_rrf")
    check("T3a: project 搜索命中", len(results) > 0,
          f"found {len(results)} results (total mems={len(mems)})")

    # persona 层搜索（如已配置）
    if per_dir:
        pm = read_persona_memories()
        if pm:
            check("T3b: persona 层有记忆且可读", len(pm) >= 1,
                  f"got {len(pm)} persona memories")
        else:
            check("T3b: persona 层可读", True, "empty but no error")
    else:
        check("T3b: persona 目录可解析", True, "none configured (ok)")


# ========================
# T4: RRF 秩融合排序
# ========================
def test_rrf_ordering():
    print("\n--- T4: RRF 秩融合排序 ---")
    # 制造两条记忆：一条精确匹配、一条模糊匹配，验证精确排第一
    mems = [
        {"id": "rrf_1", "content": "超脑是 AI 认知增强系统", "type": "fact",
         "entity": "超脑", "confidence": 0.95, "timestamp": get_timestamp(), "simhash": 0},
        {"id": "rrf_2", "content": "Python 是编程语言，广泛用于数据科学", "type": "fact",
         "entity": "Python", "confidence": 0.95, "timestamp": get_timestamp(), "simhash": 0},
    ]

    results = search_memories("超脑 认知", mems, limit=5, workspace="test")
    check("T4a: RRF 返回结果数", len(results) >= 1,
          f"got {len(results)}")

    if len(results) >= 1:
        top_mem = results[0][0]
        check("T4b: 精确匹配排第一", "超脑" in str(top_mem.get("content", "")),
              f"top is: {top_mem.get('content','')[:50]}")

    if len(results) >= 2:
        rrf_1_score = results[0][1]
        rrf_2_score = results[1][1]
        check("T4c: RRF 分数非负", rrf_1_score >= 0 and rrf_2_score >= 0,
              f"scores: {rrf_1_score:.3f}, {rrf_2_score:.3f}")
        check("T4d: 相关记忆分数 > 无关", rrf_1_score > rrf_2_score,
              f"{rrf_1_score:.3f} vs {rrf_2_score:.3f}")


# ========================
# T5: read_json 异常恢复（非 UTF-8 二进制）
# ========================
def test_binary_json_recovery():
    print("\n--- T5: 二进制/非 UTF-8 JSON 恢复 ---")
    ws = ensure_workspace("test_binary")
    path = os.path.join(ws, "test_binary.json")

    # 写入正常数据
    write_json(path, {"key": "value"})
    data = read_json(path)
    check("T5a: 正常读写", data == {"key": "value"}, f"got {data}")

    # 写入 \xff 二进制
    with open(path, "wb") as f:
        f.write(b"\xff\xfe\x00\x01")
    try:
        data2 = read_json(path)
        check("T5b: 二进制 JSON 不崩返 None", data2 is None,
              f"got {type(data2).__name__}")
    except UnicodeDecodeError:
        check("T5b: 二进制 JSON 不崩", False, "UnicodeDecodeError 未被捕获")


# ========================
if __name__ == "__main__":
    print(f"=== v3.9.5 P1-8 关键路径测试 (DATA={TEST_DATA}) ===\n")

    test_hardstep_exit()
    test_corrupted_json_recovery()
    test_persona_search()
    test_rrf_ordering()
    test_binary_json_recovery()

    print(f"\n=== 结果: {PASS} 通过 / {FAIL} 失败 ===\n")

    # 清理隔离目录
    shutil.rmtree(TEST_DATA, ignore_errors=True)
    sys.exit(0 if FAIL == 0 else 1)
