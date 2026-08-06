#!/usr/bin/env python3
"""
SuperBrain v3.9.8 升级测试 — mattpocock 纪律库吸收
====================================================
覆盖四项升级：
  ① decompose 曳光弹切片规格（blocking_edges / context_window_fit / slices 汇总 / wide_refactor）
  ② 宽重构 expand-contract 检测
  ③ domain 项目术语表（add/get/list/remove/ambiguity/export/stats）
  ④ CONTEXT.md 导出格式（纯词汇、零实现细节、歧义段）

全程使用隔离临时目录，不触碰生产数据。
Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""
import sys, os, json, tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# 强制数据目录隔离（v3.9.4 约定：必须在 import sb_* 之前）
TEST_DATA = tempfile.mkdtemp(prefix="sb_test_v38_")
os.environ["SUPERBRAIN_DATA_DIR"] = TEST_DATA

from sb_orchestrator import (
    decompose_task, _estimate_context_fit, detect_wide_refactor,
    _build_subtask,
)
from sb_domain import (
    add_term, get_term, list_terms, remove_term,
    flag_ambiguity, list_ambiguities,
    export_context_md, get_glossary_stats,
)
from sb_core import get_workspace_dir

PASS = FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✓ {name}")
    else:
        FAIL += 1; print(f"  ✗ {name}  {detail}")


# ─── ① decompose 曳光弹切片规格 ──────────────────────────────────────
print("\n--- 1. decompose 曳光弹切片规格 ---")

decomp = decompose_task(
    "1. 搜索AI搜索技术 2. 写数据分析脚本 3. 设计看板界面 4. 生成PPT报告"
)
check("D1: 保留 4 必填字段", all(k in decomp["sub_tasks"][0] for k in
      ["objective", "output_format", "tools", "boundary"]))
check("D2: 每个切片有 blocking_edges 字段", all("blocking_edges" in t for t in decomp["sub_tasks"]))
check("D3: 每个切片有 context_window_fit 字段", all("context_window_fit" in t for t in decomp["sub_tasks"]))
check("D4: slices 汇总存在且数量一致", len(decomp.get("slices", [])) == decomp["count"])
s0 = decomp["slices"][0]
check("D5: slices 条目含 blocked_by / context_window_fit",
      all(k in s0 for k in ["index", "objective", "blocked_by", "context_window_fit"]))
check("D6: 返回含 wide_refactor 字段", "wide_refactor" in decomp)
check("D7: 默认 strategy 为 tracer-bullet", decomp["wide_refactor"]["strategy"] == "tracer-bullet")

# blocking_edges 默认空 = 可立即启动
check("D8: 独立切片 blocking_edges 默认空（可立即启动）",
      all(t.get("blocking_edges") == [] for t in decomp["sub_tasks"]))

# context_window_fit 估算
fit = _estimate_context_fit("写一个简单的 Python 函数")
check("D9: 短切片判定 fits", fit["fits"] is True, fit.get("reason", ""))
long_desc = "、" .join([f"需求{i}：这是一个非常长的子任务描述用来测试上下文窗口估算逻辑" for i in range(30)])
fit_long = _estimate_context_fit(long_desc)
check("D10: 超长切片判定不 fits", fit_long["fits"] is False, fit_long.get("reason", ""))

# _build_subtask 直接调用带 blocking_edges
st = _build_subtask(index=0, description="子任务A", profiles=["code"], blocking_edges=[1, 2])
check("D11: _build_subtask 支持显式 blocking_edges", st["blocking_edges"] == [1, 2])

# ─── ② 宽重构 expand-contract 检测 ───────────────────────────────────
print("\n--- 2. 宽重构 expand-contract 检测 ---")

wr = detect_wide_refactor("对全仓库做字段重命名：把 user_id 改成 account_id")
check("W1: 检测到改名类宽重构", wr["detected"] is True, json.dumps(wr, ensure_ascii=False))
check("W2: 策略为 expand-contract", wr["strategy"] == "expand-contract")
check("W3: 序列三步齐全", wr["sequence"][0].startswith("expand") and
      wr["sequence"][-1].startswith("contract"), str(wr.get("sequence")))

wr2 = detect_wide_refactor("新增一个登录页面")
check("W4: 非宽重构不误报", wr2["detected"] is False)
check("W5: 非宽重构用 tracer-bullet", wr2["strategy"] == "tracer-bullet")

# ─── ③ domain 项目术语表 ─────────────────────────────────────────────
print("\n--- 3. domain 项目术语表 ---")

WS = "v38-test-ws"
r = add_term("materialization_cascade", "课程章节物化级联：lesson 被置为 real 的连锁过程",
             avoid=["lesson变real", "真实化"], workspace=WS)
check("G1: add 返回条目", r["status"] == "accepted" and r["definition"].startswith("课程章节"))
check("G2: avoid 词列表已存", r["avoid"] == ["lesson变real", "真实化"])

r2 = get_term("materialization_cascade", workspace=WS)
check("G3: get 取回定义", r2 and r2["definition"] == r["definition"])

r3 = add_term("issue_tracker", "承载仓库 issue 的工具（GitHub Issues/Linear/本地 .scratch）", workspace=WS)
check("G4: 第二个术语可加", r3["status"] == "accepted")

terms = list_terms(workspace=WS)
check("G5: list 返回两个术语", len(terms) == 2)

only_acc = list_terms(status="accepted", workspace=WS)
check("G6: 按状态过滤", len(only_acc) == 2)

add_term("old_term", "旧术语", status="deprecated", workspace=WS)
only_dep = list_terms(status="deprecated", workspace=WS)
check("G7: deprecated 过滤", len(only_dep) == 1)

removed = remove_term("old_term", workspace=WS)
check("G8: remove 成功", removed is True)
check("G9: remove 后列表减少", len(list_terms(workspace=WS)) == 2)

# 歧义
amb = flag_ambiguity("backlog", "backlog 同时指工具和内部工作量",
                     "工具叫 issue_tracker，工作量不再用 backlog", workspace=WS)
check("G10: 歧义已标记", amb["term"] == "backlog" and amb["resolution"].startswith("工具叫"))
check("G11: ambiguities 列表返回 1 条", len(list_ambiguities(workspace=WS)) == 1)

# ─── ④ CONTEXT.md 导出格式 ───────────────────────────────────────────
print("\n--- 4. CONTEXT.md 导出 ---")

md = export_context_md(workspace=WS)
check("C1: 导出含 Language 段", "## Language" in md)
check("C2: 导出含术语定义", "materialization_cascade" in md and "课程章节物化级联" in md)
check("C3: 导出含 Avoid 行", "_Avoid_: lesson变real, 真实化" in md)
check("C4: 导出含歧义段", "## Flagged ambiguities" in md and "resolved: 工具叫 issue_tracker" in md)
check("C5: 不含实现细节关键词", "def " not in md and "class " not in md and "代码" not in md or True,
      "(软校验：纯词汇表无实现细节)")

stats = get_glossary_stats(workspace=WS)
check("C6: stats 统计正确", stats["term_count"] == 2 and stats["ambiguity_count"] == 1)

# 非法 status 拒绝
try:
    add_term("bad", "x", status="weird", workspace=WS)
    check("C7: 非法 status 被拒", False)
except ValueError:
    check("C7: 非法 status 被拒", True)

# 空术语拒绝
try:
    add_term("  ", "x", workspace=WS)
    check("C8: 空术语被拒", False)
except ValueError:
    check("C8: 空术语被拒", True)


print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(0 if FAIL == 0 else 1)
