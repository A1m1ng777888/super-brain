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


def install(time_hhmm="09:00"):
    """安装每日计划任务。幂等（/F 覆盖）。

    v3.12.1 (审计 P1-6)：--time 必须匹配 HH:MM（00:00~23:59），
    非法输入直接报错返回 2——防 IndexError/ValueError 崩溃与非法 cron
    （如 "25:00" 会产出 25 点 cron 静默失效）。
    """
    if not TIME_RE.match(time_hhmm):
        print(f"[schedule_manager] 非法时间格式: {time_hhmm!r}"
              f"（需 HH:MM，00:00~23:59）", file=sys.stderr)
        return 2
    if not IS_WIN:
        cron = (f"{_minute_of(time_hhmm)} {_hour_of(time_hhmm)} * * * "
                f'"{sys.executable}" "{_script_path()}" --quiet')
        print("[schedule_manager] 请将以下 cron 行加入 crontab（本工具不代写）：")
        print(f"  {cron}")
        return 0
    tr = f'"{sys.executable}" "{_script_path()}" --quiet'
    code, out = _schtasks("/Create", "/TN", TASK_NAME, "/TR", tr,
                          "/SC", "DAILY", "/ST", time_hhmm, "/F")
    ok = code == 0
    print(f"[schedule_manager] {'已安装' if ok else '安装失败'}："
          f"每日 {time_hhmm} 运行 sb_healthlite --quiet（任务名 {TASK_NAME}）")
    if not ok:
        print(out.strip()[:300])
    return 0 if ok else 1


def _minute_of(t):
    return int(t.split(":")[1])


def _hour_of(t):
    return int(t.split(":")[0])


def uninstall():
    if not IS_WIN:
        print("[schedule_manager] POSIX 平台请自行移除对应 cron 行")
        return 0
    code, out = _schtasks("/Delete", "/TN", TASK_NAME, "/F")
    if code == 0:
        print("[schedule_manager] 已卸载")
        return 0
    # v3.12.1 (审计 P1-7)：schtasks /Delete 对「任务不存在」也返回非 0
    # （0x80070002 file not found）。这种算成功；其余失败才报错返回 1。
    low = out.lower()
    if any(k in low for k in ("0x80070002", "cannot find", "not found",
                              "找不到", "没有找到", "无法找到")):
        print("[schedule_manager] 未找到任务（视为已卸载）")
        return 0
    print(f"[schedule_manager] 删除失败：\n{out.strip()[:300]}", file=sys.stderr)
    return 1


def status(as_json=False):
    st = {"task_name": TASK_NAME, "installed": False, "schedule": None,
          "last_run_state": None}
    if IS_WIN:
        # 用 CSV 输出解析：列序（TaskName, Next Run Time, Status）跨语言稳定，
        # /V LIST 的标签名会随系统语言变化（中文系统无 "Next Run Time:"）
        code, out = _schtasks("/Query", "/TN", TASK_NAME, "/FO", "CSV", "/NH")
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
    # 附加守护引擎最近状态（意图 vs 现实分离：任务装了≠跑成功）
    # v3.12.1 (审计 P0-1)：区分「从未运行」（文件不存在）与「文件损坏」。
    # 损坏时标 corrupt 而非吞成 never_ran——否则真实 error 状态会被假绿掩盖。
    try:
        with open(_state_path(), encoding="utf-8") as f:
            d = json.load(f)
        st["engine_status"] = d.get("status")
        st["engine_timestamp"] = d.get("timestamp")
        st["engine_issues"] = len(d.get("issues", []))
    except FileNotFoundError:
        st["engine_status"] = "never_ran"
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        st["engine_status"] = "corrupt"
        st["engine_status_detail"] = type(e).__name__
    if as_json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
    else:
        print(f"任务 {TASK_NAME}: {'已安装' if st['installed'] else '未安装（默认关闭）'}"
              f" | 引擎最近状态: {st['engine_status']}")
        if st.get("engine_issues"):
            print(f"  ⚠️ {st['engine_issues']} 项待关注，详见 health_state.json")
    return 0


def main():
    ap = argparse.ArgumentParser(description="超脑守护调度管理（默认关闭，显式开启）")
    ap.add_argument("action", choices=["status", "install", "uninstall"])
    ap.add_argument("--time", default="09:00", help="每日运行时间 HH:MM（默认 09:00）")
    ap.add_argument("--json", action="store_true", help="status 输出 JSON（供工作台调用）")
    args = ap.parse_args()
    return {"status": lambda: status(args.json),
            "install": lambda: install(args.time),
            "uninstall": uninstall}[args.action]()


if __name__ == "__main__":
    sys.exit(main())
