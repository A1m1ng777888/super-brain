#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
schedule_manager — 守护任务调度管理（开发者兜底通道 + 工作台底层接口）
======================================================================

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.

定位（2026-08-31 方案 B 调整版，用户拍板）：
  - **主通道是可视化工作台的「自动化组件面板」**（面向无代码用户，
    组件默认全关）；本脚本提供与之**同一语义**的命令行三动作
    install / uninstall / status，供无 GUI 环境与工作台底层调用。
  - **默认关闭**：install 必须由用户显式执行；卸载随时可用。

用法：
  python schedule_manager.py status [--json]
  python schedule_manager.py install [--time 09:00]
  python schedule_manager.py uninstall

Windows 实现：schtasks（系统自带，无需管理员——当前用户级任务）。
Linux/macOS：打印 cron 行由用户自行安装（不代写 crontab，最小惊讶原则）。

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

TASK_NAME = "SuperBrain-HealthLite"
IS_WIN = sys.platform == "win32"

# v3.12.1 (审计 P1-6)：HH:MM 严格校验（00:00~23:59），非法输入拒绝安装。
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _script_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "sb_healthlite.py")


def _state_path():
    import sb_core
    return os.path.join(sb_core.DEFAULT_DATA_DIR, "health_state.json")


def _schtasks(*args):
    # ⚠️ 中文 Windows 的 schtasks 输出是 ANSI/GBK 码页，默认 UTF-8 解码会在
    # 读线程 UnicodeDecodeError（2026-08-31 实测）。按系统码页解码 + replace 兜底。
    enc = "mbcs" if IS_WIN else "utf-8"
    r = subprocess.run(["schtasks", *args], capture_output=True,
                       encoding=enc, errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _registry():
    """读 automation_registry.json（组件契约：task_name/entry/workspace/time）。

    v3.12.2 (M2 工作台)：调度管理从「单任务硬编码」升级为「registry 组件驱动」。
    组件缺字段时回退硬编码默认（向后兼容 v3.12.1 行为）。
    """
    try:
        import sb_core
        p = os.path.join(sb_core.DEFAULT_DATA_DIR, "automation_registry.json")
        data = sb_core.read_json(p) or {}
        return {c.get("id"): c for c in data.get("components", [])}
    except Exception:  # noqa: BLE001 —— registry 缺失不阻断 CLI 兜底通道
        return {}


DEFAULT_COMPONENT = "daily_health_lite"


def _task_def(task_id=None):
    """组件 id → (task_name, script 绝对路径, 额外参数, workspace, 默认时间)。"""
    comp = _registry().get(task_id or DEFAULT_COMPONENT) or {}
    impl = comp.get("implementation", {})
    entry = impl.get("entry") or "sb_healthlite.py"
    # entry 形如 "sb_healthlite.py --consolidate"：首 token=脚本名，其余=参数
    parts = entry.split()
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), parts[0])
    extra = parts[1:]
    name = impl.get("task_name") or TASK_NAME
    ws = impl.get("workspace")
    sch = comp.get("schedule", {}) or {}
    dtime = sch.get("time") or "09:00"
    return name, script, extra, ws, dtime


def install(time_hhmm=None, task_id=None):
    """安装组件的每日计划任务。幂等（/F 覆盖）。

    v3.12.2 (M2)：
      - task_id 按 registry 组件安装（默认 daily_health_lite，兼容旧调用）；
      - 任务命令行带 --workspace（来自 registry implementation.workspace）——
        修复 v3.12.1 的洞：schtasks 触发时无 SUPERBRAIN_WORKSPACE 环境变量，
        healthlite 会跑在 default 空库上；
      - 时间缺省取 registry schedule.time（v3.12.1 固定 09:00）。

    v3.12.1 (审计 P1-6)：--time 必须匹配 HH:MM（00:00~23:59），
    非法输入直接报错返回 2——防 IndexError/ValueError 崩溃与非法 cron
    （如 "25:00" 会产出 25 点 cron 静默失效）。
    """
    name, script, extra, ws, dtime = _task_def(task_id)
    time_hhmm = time_hhmm or dtime
    if not TIME_RE.match(time_hhmm):
        print(f"[schedule_manager] 非法时间格式: {time_hhmm!r}"
              f"（需 HH:MM，00:00~23:59）", file=sys.stderr)
        return 2
    if not IS_WIN:
        cron = (f"{_minute_of(time_hhmm)} {_hour_of(time_hhmm)} * * * "
                f'"{sys.executable}" "{script}" {" ".join(extra)} --quiet'
                + (f" --workspace {ws}" if ws else ""))
        print("[schedule_manager] 请将以下 cron 行加入 crontab（本工具不代写）：")
        print(f"  {cron}")
        return 0
    tr = (f'"{sys.executable}" "{script}"'
          + (f" {' '.join(extra)}" if extra else "")
          + " --quiet"
          + (f" --workspace {ws}" if ws else ""))
    code, out = _schtasks("/Create", "/TN", name, "/TR", tr,
                          "/SC", "DAILY", "/ST", time_hhmm, "/F")
    ok = code == 0
    print(f"[schedule_manager] {'已安装' if ok else '安装失败'}："
          f"每日 {time_hhmm} 运行 {os.path.basename(script)}"
          f"{' ' + ' '.join(extra) if extra else ''}（任务名 {name}）")
    if not ok:
        print(out.strip()[:300])
    return 0 if ok else 1


def _minute_of(t):
    return int(t.split(":")[1])


def _hour_of(t):
    return int(t.split(":")[0])


def uninstall(task_id=None):
    """卸载组件的每日计划任务（v3.12.2：按 registry 组件名卸载）。"""
    name = _task_def(task_id)[0]
    if not IS_WIN:
        print(f"[schedule_manager] POSIX 平台请自行移除对应 cron 行（{name}）")
        return 0
    code, out = _schtasks("/Delete", "/TN", name, "/F")
    if code == 0:
        print(f"[schedule_manager] 已卸载：任务 {name}")
        return 0
    # v3.12.1 (审计 P1-7)：schtasks /Delete 对「任务不存在」也返回非 0
    # （0x80070002 file not found）。这种算成功；其余失败才报错返回 1。
    low = out.lower()
    if any(k in low for k in ("0x80070002", "cannot find", "not found",
                              "找不到", "没有找到", "无法找到")):
        print(f"[schedule_manager] 未找到任务 {name}（视为已卸载）")
        return 0
    print(f"[schedule_manager] 删除失败：\n{out.strip()[:300]}", file=sys.stderr)
    return 1


def status(as_json=False, task_id=None):
    """查询调度与引擎状态（v3.12.2：按 registry 组件查询）。

    task_id=None 时聚合全部组件（工作台/JSON 用）；指定时单组件
    （v3.12.1 CLI 兼容：默认 daily_health_lite）。
    """
    ids = [task_id] if task_id else list(_registry().keys()) or [DEFAULT_COMPONENT]
    results = {}
    for cid in ids:
        name = _task_def(cid)[0]
        st = {"component_id": cid, "task_name": name, "installed": False,
              "schedule": None, "last_run_state": None}
        if IS_WIN:
            # 用 CSV 输出解析：列序（TaskName, Next Run Time, Status）跨语言稳定，
            # /V LIST 的标签名会随系统语言变化（中文系统无 "Next Run Time:"）
            code, out = _schtasks("/Query", "/TN", name, "/FO", "CSV", "/NH")
            if code == 0:
                st["installed"] = True
                try:
                    import csv as _csv
                    rows = list(_csv.reader(out.splitlines()))
                    if rows and len(rows[0]) >= 3:
                        st["schedule"] = rows[0][1] or None
                        st["task_status"] = rows[0][2] or None
                except Exception:  # noqa: BLE001 —— 解析失败不影响 installed 判定
                    pass
        results[cid] = st
    # 附加守护引擎最近状态（意图 vs 现实分离：任务装了≠跑成功）
    # v3.12.1 (审计 P0-1)：区分「从未运行」（文件不存在）与「文件损坏」。
    # 损坏时标 corrupt 而非吞成 never_ran——否则真实 error 状态会被假绿掩盖。
    try:
        with open(_state_path(), encoding="utf-8") as f:
            d = json.load(f)
        engine = {"engine_status": d.get("status"),
                  "engine_timestamp": d.get("timestamp"),
                  "engine_issues": len(d.get("issues", []))}
    except FileNotFoundError:
        engine = {"engine_status": "never_ran"}
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        engine = {"engine_status": "corrupt", "engine_status_detail": type(e).__name__}
    for st in results.values():
        st.update(engine)

    if as_json:
        if task_id:
            print(json.dumps(results[task_id], ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"components": results, **engine}, ensure_ascii=False, indent=2))
    else:
        for cid, st in results.items():
            print(f"任务 {st['task_name']}（{cid}）: "
                  f"{'已安装' if st['installed'] else '未安装（默认关闭）'}"
                  f" | 引擎最近状态: {st['engine_status']}")
            if st.get("engine_issues"):
                print(f"  ⚠️ {st['engine_issues']} 项待关注，详见 health_state.json")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="超脑守护调度管理（默认关闭，显式开启；v3.12.2 起 registry 组件驱动）")
    ap.add_argument("action", choices=["status", "install", "uninstall"])
    ap.add_argument("--task", default=None,
                    help="registry 组件 id（默认 daily_health_lite；status 缺省聚合全部）")
    ap.add_argument("--time", default=None,
                    help="每日运行时间 HH:MM（默认取 registry schedule.time）")
    ap.add_argument("--json", action="store_true", help="status 输出 JSON（供工作台调用）")
    args = ap.parse_args()
    tid = args.task or (DEFAULT_COMPONENT if args.action != "status" else None)
    return {"status": lambda: status(args.json, task_id=tid),
            "install": lambda: install(args.time, task_id=tid),
            "uninstall": lambda: uninstall(task_id=tid)}[args.action]()


if __name__ == "__main__":
    sys.exit(main())
