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


def run(workspace=DEFAULT_WORKSPACE, quiet=False):
    """主流程：build → selfcheck → 门控检查 → 状态文件。返回 (exit_code, state)。"""
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
    args = ap.parse_args()

    lock = _acquire_lock()
    if lock is None:
        if not args.quiet:
            print("[sb_healthlite] 已有实例在运行（锁未过期），跳过本次")
        return 0
    try:
        code, _ = run(args.workspace, quiet=args.quiet)
        return code
    finally:
        _release_lock(lock, os.getpid())


if __name__ == "__main__":
    sys.exit(main())
