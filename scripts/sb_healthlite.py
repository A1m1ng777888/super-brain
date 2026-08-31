#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sb_healthlite — 每日本地守护引擎（L0 层，零 Agent / 零 token）
==============================================================

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.

设计（2026-08-31 方案 B，用户拍板）：
  - 由系统计划任务（Task Scheduler / cron）直接运行，Agent 不参与，
    每日 token 消耗 = 0。Agent 只在异常时通过 health_state.json 感知。
  - 开关由「可视化工作台 → 自动化组件面板」控制（主通道，面向无代码
    用户）；本脚本配套的 schedule_manager.py 是开发者兜底通道。
  - **默认关闭**：未经用户显式开启，任何调度不应被安装。

三步守护（全部幂等）：
  1. graph build        —— 新写入记忆 ent=0，建图后才进工作空间（P0-I）；
                           workspace 生命力的唯一开关（漂移研判 A vs A2）
  2. selfcheck 12 项    —— run_full_check(auto_fix=False) 纯诊断
  3. 门控带内检查       —— 只读复算（不调 get_active_workspace，遵守
                           build_dashboard 铁律），calibrate 口径 8~25%

输出契约：
  - 正常：静默更新 health_state.json，退出码 0，stdout 仅一行摘要
    （--quiet 时零输出，供计划任务使用）
  - 软异常（status=warn）：health_state.json 标记 issues，退出码 0。
    **warn 不触发 L1 Agent 介入**（token 契约：L1 只响应 error）
  - 硬异常（status=error）：health_state.json 标记 issues，退出码 1，
    stdout 打印详情。**只有 error 才触发 L1 介入**
  - 防重叠：锁文件（30 分钟过期自动清；释放前校验 pid，防误删他人锁），
    避免计划任务与手动运行撞车
  - 报告治理：selfcheck 每次运行写全量 report_*.json，本脚本运行后
    清理 health 目录，只保留最近 30 个

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

import sb_core                                    # noqa: E402
import sb_gating                                  # noqa: E402
import sb_graph                                   # noqa: E402
import sb_selfcheck                               # noqa: E402
try:
    import sb_consolidate                          # noqa: E402  L1 整合（可选）
except Exception:                                  # pragma: no cover
    sb_consolidate = None                          # 独立部署缺文件时不拖垮 L0

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 带内判断（与 gating calibrate 的 recommendation 同语义）
GWT_BAND = (0.08, 0.25)
LOCK_TTL_SEC = 30 * 60
DEFAULT_WORKSPACE = os.environ.get("SUPERBRAIN_WORKSPACE", "default")


def _state_path():
    return os.path.join(sb_core.DEFAULT_DATA_DIR, "health_state.json")


def _lock_path():
    return os.path.join(sb_core.DEFAULT_DATA_DIR, "health_lite.lock")


def _acquire_lock():
    """O_CREAT|O_EXCL 简单锁；TTL 过期自动清（防崩溃残留死锁）。

    v3.12.1 (审计 P1-3 修复)：锁内容写入持有者 pid。TTL 过期清理前先读
    内容——只清理「残留锁」（其他进程崩溃留下的），绝不删本进程刚创建的
    锁（防时钟异常/慢运行被误判为残留）。释放同理见 _release_lock。
    """
    path = _lock_path()
    pid = str(os.getpid())
    if os.path.exists(path):
        stale = False
        try:
            stale = time.time() - os.path.getmtime(path) > LOCK_TTL_SEC
        except OSError:
            return None
        if not stale:
            return None
        try:
            with open(path, encoding="utf-8") as f:
                owner = f.read().strip()
            if owner == pid:
                return None  # 自己的锁（时钟回拨等），视为已在运行
            os.remove(path)
        except OSError:
            return None
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, pid.encode())
        os.close(fd)
        return path
    except FileExistsError:
        return None


def _release_lock(path, pid):
    """释放锁；先校验内容 == 本进程 pid 才删除，防误删他人新锁。"""
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                owner = f.read().strip()
            if owner == str(pid):
                os.remove(path)
        except OSError:
            pass


def _history_path():
    return os.path.join(sb_core.DEFAULT_DATA_DIR, "health_history.json")


def _pending_review_path():
    return os.path.join(sb_core.DEFAULT_DATA_DIR, "pending_ai_review.md")


def _sync_pending_review(state):
    """v3.12.2 (M3-C「AI 深入检查」自动化版)：error 写 AI 待办，恢复即清除。

    token 契约：纯本地文件（0 token），L1 Agent 在会话开场发现此文件后
    主动深入检查（约定见 SKILL.md 硬步骤节）——不唤醒、不推送、不轮询。
    与状态文件同原子写策略；写/删失败静默（待办是增强，不是关键路径）。
    """
    p = _pending_review_path()
    try:
        if state.get("status") == "error":
            issues = state.get("issues") or []
            lines = [
                "# 超脑 L1 待办：体检发现 error，请深入检查",
                "",
                f"- 体检时间：{state.get('timestamp')}",
                f"- 工作区：{state.get('workspace')}",
                f"- 体检结果：{sb_core.DEFAULT_DATA_DIR}{os.sep}health_state.json",
                f"- 深度自检报告：{sb_core.get_health_dir()}{os.sep}latest_report.json",
                "",
                "## error 项（需修复）",
            ]
            for i in issues:
                if i.get("severity") == "error":
                    lines.append(f"- **{i.get('check')}**：{(i.get('detail') or '')[:200]}")
            lines += [
                "",
                "## 处理要求",
                "",
                "逐项归因：定位根因 → 给出修复步骤 → 修复后重跑",
                "`python sb_healthlite.py --workspace <工作区>` 验证恢复 ok/warn。",
                "本文件在体检恢复非 error 后会自动清除。",
            ]
            tmp = f"{p}.tmp.{os.getpid()}"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            os.replace(tmp, p)
        elif os.path.exists(p):
            os.remove(p)  # 恢复 ok/warn：待办自动消失，不留陈旧警报
    except OSError:
        pass


def _append_history(state):
    """v3.12.2-dev (P3 趋势)：每次运行追加一条体检摘要，cap 90 条（≈3 个月）。

    与 state 文件同原子写策略；历史文件缺失/损坏视为空重建（趋势数据允许
    丢，不值得备份恢复）；写失败静默——历史是锦上添花，绝不影响守护本体。
    """
    h_path = _history_path()
    try:
        with open(h_path, encoding="utf-8") as f:
            hist = json.load(f)
        if not isinstance(hist, list):
            hist = []
    except (OSError, json.JSONDecodeError):
        hist = []
    gb = state.get("graph_build") or {}
    hist.append({
        "ts": state.get("timestamp"),
        "status": state.get("status"),
        "n_issues": len(state.get("issues") or []),
        "n_err": len([i for i in (state.get("issues") or [])
                      if i.get("severity") == "error"]),
        "new_nodes": gb.get("new_nodes"),
        "new_edges": gb.get("new_edges"),
        "duration_sec": state.get("duration_sec"),
    })
    hist = hist[-90:]
    try:
        tmp = f"{h_path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False)
        os.replace(tmp, h_path)
    except OSError:
        pass


def _gating_readonly(workspace):
    """只读复算门控状态（抄 build_dashboard 口径，不触发重门控写盘）。"""
    mems = sb_core.read_memories(workspace)
    act = [m for m in mems if m.get("status") == "active"]
    candidates = [m for m in act if not m.get("gating_override")]
    auto_promoted = [m for m in candidates if m.get("workspace_promoted")]
    ratio_cal = (len(auto_promoted) / len(candidates)) if candidates else 0.0
    ratio_flag = len([m for m in act if m.get("workspace_promoted")]) / max(len(act), 1)
    in_band = GWT_BAND[0] <= ratio_cal <= GWT_BAND[1]
    return {
        "n_active": len(act),
        "n_candidates": len(candidates),
        "ratio_calibrate": round(ratio_cal, 3),
        "ratio_status": round(ratio_flag, 3),
        "in_band": in_band,
        "band": list(GWT_BAND),
    }


def _cleanup_old_reports(keep=30):
    """selfcheck 每次运行写一个全量 report_*.json（约 4.6KB），长期累积无界。

    v3.12.1 (审计 P1-4)：按 mtime 保留最近 keep 个，其余删除。
    只清 health 目录下的 report_*.json，不动 latest_report.json 与其他文件。
    """
    try:
        health_dir = sb_core.get_health_dir()
        reports = [f for f in os.listdir(health_dir)
                   if f.startswith("report_") and f.endswith(".json")]
        if len(reports) <= keep:
            return
        reports.sort(key=lambda f: os.path.getmtime(os.path.join(health_dir, f)))
        for f in reports[:-keep]:
            try:
                os.remove(os.path.join(health_dir, f))
            except OSError:
                pass
    except OSError:
        pass


def run(workspace=DEFAULT_WORKSPACE, quiet=False, consolidate=False):
    """主流程：build → selfcheck → 门控检查 → 状态文件。返回 (exit_code, state)。

    v3.12.2-dev：consolidate=True 时追加 L1 整合提案生成（只读，**永不
    自动 apply**——两段式铁律：后台只出 proposal，应用须经人工确认走
    sb_consolidate --apply）。提案计数进 health_state.json，面板可见。
    """
    t0 = time.time()
    issues = []
    state = {
        "engine": "sb_healthlite",
        "workspace": workspace,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "issues": issues,
        "graph_build": None,
        "selfcheck": None,
        "gating": None,
        "duration_sec": None,
    }

    # ---- 1. graph build（幂等；持锁由 sb_graph 内部保证） ----
    try:
        build = sb_graph.build_from_memories(workspace=workspace)
        state["graph_build"] = {
            "new_nodes": build.get("new_nodes"),
            "new_edges": build.get("new_edges"),
            "total_nodes": build.get("total_nodes"),
            "total_edges": build.get("total_edges"),
            "backfilled": build.get("memories_backfilled"),
            "post_build_promotion": build.get("post_build_promotion"),
        }
    except Exception as e:  # noqa: BLE001 —— 守护脚本必须把异常变成状态而非崩溃
        issues.append({"check": "graph_build", "severity": "error",
                       "detail": f"{type(e).__name__}: {e}"})

    # ---- 2. selfcheck 12 项（纯诊断，不 auto_fix） ----
    try:
        sc = sb_selfcheck.run_full_check(workspace, auto_fix=False)
        hard = [k for k, v in sc.get("checks", {}).items()
                if isinstance(v, dict) and v.get("issues_found")]
        state["selfcheck"] = {
            "overall_status": sc.get("overall_status"),
            "score_status": sc.get("score_status"),
            "total_issues": sc.get("total_issues"),
            "checks_with_issues": hard,
        }
        # 物理层/无效协议/门控洪水 = error；其余 issue = warn
        fatal = {"file_integrity", "index_integrity", "gating_flood_protection"}
        if sc.get("score_status") == "invalid":
            issues.append({"check": "validity", "severity": "error",
                           "detail": sc.get("invalid_reason") or "评测无效"})
        for k in hard:
            sev = "error" if (k in fatal or
                              sc.get("score_status") == "invalid") else "warn"
            issues.append({"check": k, "severity": sev, "detail": "见 selfcheck 报告"})
    except Exception as e:  # noqa: BLE001
        issues.append({"check": "selfcheck", "severity": "error",
                       "detail": f"{type(e).__name__}: {e}"})

    # ---- selfcheck 产物治理：只保留最近 30 个全量报告 ----
    _cleanup_old_reports()

    # ---- 3. 门控带内（只读复算） ----
    try:
        g = _gating_readonly(workspace)
        # v3.12.1 (审计 P1-5)：标注口径——flag 为存储态，可能滞后于 calibrate
        g["caliber_note"] = (
            "ratio_calibrate 基于存储态 workspace_promoted 标志，随 "
            "get_active_workspace 刷新；长期未打开工作空间可能与 "
            "calibrate 的 salience 重算口径漂移"
        )
        state["gating"] = g
        if not g["in_band"]:
            issues.append({
                "check": "gating_band", "severity": "warn",
                "detail": (f"calibrate 口径比例 {g['ratio_calibrate']} 出带 "
                           f"{g['band']}（候选 {g['n_candidates']}）")})
    except Exception as e:  # noqa: BLE001
        issues.append({"check": "gating", "severity": "error",
                       "detail": f"{type(e).__name__}: {e}"})

    # ---- 判定与落盘 ----
    # ---- 4. L1 整合提案（可选；只读生成，不 apply） ----
    if consolidate:
        if sb_consolidate is not None:
            try:
                prop = sb_consolidate.generate_proposals(workspace)
                acts = prop.get("actions", {})
                state["consolidation"] = {
                    "mode": "proposal_only",
                    "entity_reassign": len(acts.get("entity_reassign", [])),
                    "similar_merge": len(acts.get("similar_merge", [])),
                    "verbose_compress": len(acts.get("verbose_compress", [])),
                    "supersede": len(acts.get("supersede", [])),
                    "proposal_path": os.path.join(
                        sb_core.get_workspace_dir(workspace),
                        "consolidation_proposals.json"),
                }
                if any(state["consolidation"][k] for k in
                       ("entity_reassign", "similar_merge",
                        "verbose_compress", "supersede")):
                    issues.append({
                        "check": "consolidation_pending", "severity": "warn",
                        "detail": (f"整合提案待处理：A×{state['consolidation']['entity_reassign']} "
                                   f"B×{state['consolidation']['similar_merge']} "
                                   f"C×{state['consolidation']['verbose_compress']} "
                                   f"D×{state['consolidation']['supersede']}（proposal 已生成，"
                                   f"人工确认后 sb_consolidate --apply）")})
            except Exception as e:  # noqa: BLE001
                issues.append({"check": "consolidation", "severity": "error",
                               "detail": f"{type(e).__name__}: {e}"})
        else:
            state["consolidation"] = {"mode": "unavailable"}

    if any(i["severity"] == "error" for i in issues):
        state["status"] = "error"
    elif issues:
        state["status"] = "warn"
    state["duration_sec"] = round(time.time() - t0, 1)

    # v3.12.1 (审计 P0-1)：原子写——先写 .tmp.{pid} 再 os.replace。
    # 与全项目 write_json 同策略：崩溃只留 tmp 残留，绝不损坏状态文件
    # （status 文件损坏会被读取方误判为 never_ran，形成假绿）。
    state_path = _state_path()
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    tmp_path = f"{state_path}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, state_path)

    # v3.12.2-dev (P3)：体检历史追加（趋势数据源，写失败不影响守护）
    _append_history(state)

    # v3.12.2 (M3-C)：error 写 AI 待办文件 / 恢复自动清除（token=0）
    _sync_pending_review(state)

    # v3.12.1 (审计 P0-2)：退出码分级——warn 返回 0（不触发 L1），
    # 只有 error 返回 1。token 契约：L1 仅响应 error，warn 只是面板提示。
    exit_code = 0 if state["status"] in ("ok", "warn") else 1
    if not quiet:
        print(f"[sb_healthlite] {state['status']} | "
              f"build +{state['graph_build']['new_nodes'] if state['graph_build'] else '?'}节点 "
              f"+{state['graph_build']['new_edges'] if state['graph_build'] else '?'}边 | "
              f"selfcheck issues {state['selfcheck']['total_issues'] if state['selfcheck'] else '?'} | "
              f"gating {state['gating']['ratio_calibrate'] if state['gating'] else '?'} | "
              f"{state['duration_sec']}s")
        for i in issues:
            print(f"  [{i['severity']}] {i['check']}: {i['detail'][:120]}")
    return exit_code, state


def main():
    ap = argparse.ArgumentParser(description="超脑每日本地守护（L0，零 token）")
    ap.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    ap.add_argument("--quiet", action="store_true",
                    help="计划任务模式：正常时零输出")
    ap.add_argument("--consolidate", action="store_true",
                    help="追加 L1 整合提案生成（只读，永不自动 apply）")
    args = ap.parse_args()

    lock = _acquire_lock()
    if lock is None:
        if not args.quiet:
            print("[sb_healthlite] 已有实例在运行（锁未过期），跳过本次")
        return 0
    try:
        code, _ = run(args.workspace, quiet=args.quiet,
                      consolidate=args.consolidate)
        return code
    finally:
        _release_lock(lock, os.getpid())


if __name__ == "__main__":
    sys.exit(main())
