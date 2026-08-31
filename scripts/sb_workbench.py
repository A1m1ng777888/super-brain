#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sb_workbench — 超脑工作台本地服务（M2 写通道，方案 C，2026-08-31）
===================================================================

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888

阶段2「补差距」工作台 M2：把纯静态看板（只能看）升级为**本地控制面**
（能开关、能立即运行、能看提案）。选型结论（2026-08-31 调研）：
Electron 壳最重（本机实证 9 类坑）、「发布为应用」是云端沙箱碰不到本地
文件——**本地服务（本文件）是唯一同时满足最快 + 权限完备的方案**，
且纯标准库零依赖，与超脑「断网可跑」DNA 一致。

架构（意图/现实分离，与守护设计方案 §三 一致）：
  - automation_registry.json = 用户意图权威源（面板开关写它）
  - health_state.json / schtasks = 运行现实（面板只读展示）
  - 开关 ON  = registry.enabled=true + schedule_manager install（真装任务）
  - 开关 OFF = registry.enabled=false + schedule_manager uninstall
  - 「立即检查」= 直接 subprocess 跑 sb_healthlite（不依赖调度）

安全边界：
  - 默认只绑定 127.0.0.1（局域网不可达）——本地控制面的主要防线；
    --host 0.0.0.0 局域网模式为显式 opt-in，服务无鉴权，仅限可信网络
  - 写操作仅限 registry 开关与显式按钮动作；**绝不自动 apply
    整合提案**（两段式铁律：apply 永远走 sb_consolidate --apply 人工通道）

用法：
  python sb_workbench.py                 # 默认 127.0.0.1:8917，自动开浏览器
  python sb_workbench.py --port 8918     # 换端口
  python sb_workbench.py --no-browser    # 不自动开浏览器（计划任务场景）
  python sb_workbench.py --host 0.0.0.0  # 局域网模式：手机同 Wi-Fi 访问（无鉴权，可信网络用完即关）
  双击 Start-Workbench.bat               # 无代码用户入口
  双击 Start-Workbench-LAN.bat           # 无代码用户的局域网入口（R4）
"""

import argparse
import html
import json
import os
import socket
import subprocess
import sys
import threading
import uuid
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

import sb_core                                    # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DEFAULT_PORT = 8917
RUN_TIMEOUT_SEC = 300          # 「立即检查」子进程超时（selfcheck 约 5-30s）
SCHTASKS_TIMEOUT_SEC = 60

_REGISTRY_PATH = os.path.join(sb_core.DEFAULT_DATA_DIR, "automation_registry.json")
_HEALTH_PATH = os.path.join(sb_core.DEFAULT_DATA_DIR, "health_state.json")
_DASHBOARD_PATH = os.path.join(sb_core.DEFAULT_DATA_DIR, "dashboard.html")
_BOARD_PATH = os.path.join(sb_core.DEFAULT_DATA_DIR, "workbench_board.json")
_HISTORY_PATH = os.path.join(sb_core.DEFAULT_DATA_DIR, "health_history.json")
DASHBOARD_TIMEOUT_SEC = 120   # 看板生成（只读统计）子进程超时

# 子进程输出解码：我们的脚本会自我包 UTF-8 stdout，管道场景按 UTF-8 读
_SUB_ENC = "utf-8"

# ---------------------------------------------------------------------------
# C 端人话层（2026-08-31 改造）：机制语言 → 结果语言
# 原则（见 项目档案/超脑工作台C端化改造方案_20260831）：说影响不说机制；
# 组件按用户价值命名；空状态给引导；复制内容即贴即用（真实路径注入）。
# ---------------------------------------------------------------------------
# 体检 issue 的人话解释：check 名 → (标题, 说明)。未命中的回退通用文案。
ISSUE_COPY = {
    "graph_build": ("知识图谱没能建起来",
                    "图谱负责把相关记忆连成网。它没建成时检索照常可用，"
                    "但记忆的组织和关联会暂时停滞。交给 AI 深入检查即可定位。"),
    "validity": ("部分记忆的数据不完整",
                 "有些记忆缺少时间等字段。不影响日常使用，交给 AI 可定位具体条目。"),
    "selfcheck": ("深度自检发现问题",
                  "记忆库例行深度自检发现了值得注意的地方。"),
    "gating_band": ("记忆晋升比例偏离常态",
                    "进入「常用工作区」的记忆比例超出正常范围。不影响使用，"
                    "系统会自动校准。"),
    "gating": ("记忆优先级机制异常",
               "管理记忆优先级的机制出了问题，建议交给 AI 深入检查。"),
    "consolidation_pending": ("有整理建议等你决定",
                              "引擎发现一些记忆可以精简或归类。不用急，"
                              "在下方「需要你决定」里查看即可。"),
    "consolidation": ("整理引擎运行异常",
                      "生成整理建议的环节出了问题。不影响记忆的存取，"
                      "建议交给 AI 深入检查。"),
    "consistency": ("少数记忆内容比较相似",
                    "它们不一定是重复，可能是同一件事的多次记录。不影响使用。"),
    "duplicates": ("发现疑似重复的记忆",
                   "有几对记忆内容高度相似。可在「需要你决定」里复核处理。"),
    "verbose": ("部分记忆偏长",
                "一些较早的长记录可以精简，检索会更快。可参考「需要你决定」。"),
    "temporal": ("部分记忆的时间信息需要复核",
                 "有些记忆标注的时间相互矛盾，建议交给 AI 深入检查。"),
}
_ISSUE_FALLBACK = ("发现一项待关注", "可交给 AI 深入检查定位原因。")

# 整理建议的人话分型（kind → 展示名）
_KIND_LABEL = {
    "entity_reassign": "还没归类的记忆",
    "similar_merge": "内容相近的重复记忆",
    "verbose_compress": "过长且陈旧的记忆",
    "supersede": "已被新信息更正的旧记忆",
}

# 服务展示映射（组件 id → 用户价值话术；未命中回退 registry 原文案）
SERVICE_DISPLAY = {
    "daily_health_lite": {
        "name": "记忆库自动体检",
        "description": "开启后每天早上自动给记忆库做一次体检：构建知识图谱、"
                       "健康自检、汇总整理建议。全程本地、不联网、不花钱。",
        "run_label": "立即体检",
        "off_hint": "开启后每天早上 8:30 自动体检",
    },
}
_SERVICE_FALLBACK = {"run_label": "立即运行", "off_hint": ""}


def _friendly_issues(health):
    """把 health.issues 翻译成 C 端人话（标题+说明），前端直接渲染。"""
    out = []
    for i in (health or {}).get("issues") or []:
        title, meaning = ISSUE_COPY.get(i.get("check"), _ISSUE_FALLBACK)
        out.append({"title": title, "meaning": meaning,
                    "severity": i.get("severity") or "warn"})
    return out


def _services(reg, ws=None):
    """组件 → 服务视角（display 人话字段），前端不再自行映射。"""
    services = []
    for c in reg.get("components", []):
        d = dict(SERVICE_DISPLAY.get(c.get("id"), _SERVICE_FALLBACK))
        d.setdefault("name", c.get("name"))
        d.setdefault("description", c.get("description"))
        item = dict(c)
        item["display"] = d
        services.append(item)
    return services


def _ai_prompt(health, ws):
    """「交给 AI 深入检查」的提示词——注入真实路径，复制即用零占位符。"""
    status = (health or {}).get("status") or "unknown"
    n = len((health or {}).get("issues") or [])
    sep = os.sep
    lines = [
        "我的「超脑」本地记忆库自动体检发现问题，请帮我深入检查。",
        f"- 体检状态：{status}（{n} 项提醒）",
        f"- 体检结果文件：{sb_core.DEFAULT_DATA_DIR}{sep}health_state.json",
        f"- 深度自检报告：{sb_core.get_health_dir()}{sep}latest_report.json",
        f"- 数据工作区：{ws or 'default'}",
        "请逐项归因：warn 项说明是否要紧、要不要处理；error 项给出具体修复步骤。",
    ]
    return "\n".join(lines)


def _proposal_items(acts):
    """提案明细 → C 端人话条目（看看建议列表用）。"""
    out = []
    for kind, label in _KIND_LABEL.items():
        for p in acts.get(kind) or []:
            pre = p.get("content_prefix") or p.get("deprecated_prefix") or ""
            if kind == "entity_reassign":
                desc = f"「{pre}…」还没有归类 → 建议归入「{p.get('to', '')}」"
            elif kind == "similar_merge":
                try:
                    pct = int(float(p.get("similarity", 0)) * 100)
                except (TypeError, ValueError):
                    pct = "?"
                desc = (f"「{pre}…」与另一条记忆内容相近（相似度 {pct}%）"
                        "→ 建议合并保留一条，内容不丢失")
            elif kind == "verbose_compress":
                desc = (f"「{pre}…」已有 {p.get('old_len', '?')} 字且超过 30 天没更新"
                        f" → 压缩到约 {p.get('new_len', '?')} 字")
            elif kind == "supersede":
                desc = f"「{pre}…」已被新记忆更正 → 标记为已更新（不删除，可追溯）"
            else:
                desc = p.get("reason") or ""
            out.append({"kind": kind, "label": label, "desc": desc})
    return out


# ---------------------------------------------------------------------------
# 控制面原语（工作台的所有写动作都收敛为这三个，边界清晰可审计）
# ---------------------------------------------------------------------------
def _read_registry():
    return sb_core.read_json(_REGISTRY_PATH) or {"components": []}


def _write_registry(reg):
    sb_core.write_json(_REGISTRY_PATH, reg)


def _read_health():
    return sb_core.read_json(_HEALTH_PATH)


# ---------------------------------------------------------------------------
# 激励层数据（R1）：全部服务端预聚合，前端只渲染。
# streak 遵循「渐变式不归零」语义（学 Loop 习惯打卡）：中断不清零——
# 显示「上次连续 N 天 + 已中断 M 天 + 历史最高 K 天」，跑一次就续上。
# ---------------------------------------------------------------------------
_STATUS_RANK = {"ok": 0, "warn": 1, "error": 2, "corrupt": 3}


def _worst_status(a, b):
    return b if _STATUS_RANK.get(b, 0) > _STATUS_RANK.get(a, 0) else a


def _board_stats(b):
    """看板完成率统计：全局 + 各项目 done/total（完成率环与项目进度条的数据源）。"""
    tasks = [t for t in (b.get("tasks") or []) if isinstance(t, dict)]
    done = sum(1 for t in tasks if t.get("done"))
    by_project = {}
    for p in (b.get("projects") or []):
        if not isinstance(p, dict):
            continue
        pt = [t for t in tasks if t.get("project") == p.get("name")]
        by_project[p.get("id")] = {
            "done": sum(1 for t in pt if t.get("done")),
            "total": len(pt),
        }
    return {"tasks_total": len(tasks), "tasks_done": done,
            "rate": round(done / len(tasks) * 100) if tasks else 0,
            "by_project": by_project}


def _health_pulse(history):
    """体检激励数据：连续天数（渐变式）+ 近 30 天次数 + 42 天日历热力图聚合。"""
    days = {}  # "YYYY-MM-DD" -> {"count": n, "worst": 最差状态}
    for r in history or []:
        if not isinstance(r, dict):
            continue
        d = str(r.get("ts") or "")[:10]
        if not d:
            continue
        e = days.setdefault(d, {"count": 0, "worst": "ok"})
        e["count"] += 1
        e["worst"] = _worst_status(e["worst"], r.get("status") or "ok")
    if not days:
        # 空历史也返回 42 格灰格：用户能看到「记录会出现在这里」的结构
        today = date.today()
        return {"current": 0, "best": 0, "broken_days": 0, "runs30": 0,
                "last": None,
                "heatmap": [{"date": (today - timedelta(days=i)).isoformat(),
                             "count": 0, "worst": None}
                            for i in range(41, -1, -1)]}
    today = date.today()
    dts = sorted(days.keys(), reverse=True)
    try:
        last_d = date.fromisoformat(dts[0])
    except ValueError:
        last_d = today
    # 中断天数：最后一次体检到今天之间漏掉的天数（今天/昨天跑过都不算断）
    broken = max(0, (today - last_d).days - 1)
    # 当前连续段：从最后一次体检日往回数每天都有记录的天数
    current, cur = 0, last_d
    while cur.isoformat() in days:
        current += 1
        cur -= timedelta(days=1)
    # 历史最高连续（全历史扫描）
    best = run = 0
    prev = None
    for d in sorted(days.keys()):
        try:
            dd = date.fromisoformat(d)
        except ValueError:
            continue
        run = run + 1 if (prev is not None and (dd - prev).days == 1) else 1
        best = max(best, run)
        prev = dd
    d30 = (today - timedelta(days=29)).isoformat()
    runs30 = sum(e["count"] for d, e in days.items() if d >= d30)
    # 42 天热力图（含今天，向前推 41 天；timedelta 自动处理跨月/跨年）
    heatmap = []
    for i in range(41, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        e = days.get(d) or {}
        heatmap.append({"date": d, "count": e.get("count", 0),
                        "worst": e.get("worst")})
    return {"current": current, "best": best, "broken_days": broken,
            "runs30": runs30, "last": dts[0], "heatmap": heatmap}


def _run_sm(*args, timeout=SCHTASKS_TIMEOUT_SEC):
    """调 schedule_manager（调度动作唯一通道，不直写 schtasks）。"""
    cmd = [sys.executable, os.path.join(SCRIPTS, "schedule_manager.py"), *args]
    r = subprocess.run(cmd, capture_output=True, encoding=_SUB_ENC,
                       errors="replace", timeout=timeout, cwd=SCRIPTS)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def api_state():
    """聚合态：registry 意图 + schtasks 现实 + 引擎最近状态 + C 端人话层。"""
    reg = _read_registry()
    rc, out = _run_sm("status", "--json")
    sch = {}
    try:
        sch = json.loads(out) if rc == 0 else {}
    except json.JSONDecodeError:
        sch = {}
    health = _read_health() or {}
    ws = _active_ws(reg)
    # 整合提案摘要 + 明细人话（只读；存在才显示）
    proposals = None
    try:
        if ws:
            prop_path = os.path.join(sb_core.get_workspace_dir(ws),
                                     "consolidation_proposals.json")
            p = sb_core.read_json(prop_path)
            if p:
                acts = p.get("actions") or {}
                counts = {k: len(v) for k, v in acts.items()}
                total = sum(counts.values())
                proposals = {
                    "generated_at": p.get("timestamp"),
                    "counts": counts,
                    "total": total,
                    "kind_labels": dict(_KIND_LABEL),
                    "items": _proposal_items(acts),
                    "proposal_path": prop_path,
                }
    except Exception:  # noqa: BLE001 —— 提案摘要是锦上添花，失败不阻断面板
        proposals = None
    # 看板文件元信息（生成时间，只读展示）
    dash = None
    if os.path.exists(_DASHBOARD_PATH):
        dash = {"mtime": datetime.fromtimestamp(
            os.path.getmtime(_DASHBOARD_PATH)).strftime("%Y-%m-%d %H:%M")}
    # 体检历史（P3 趋势，只读取最近 30 条；缺失/损坏给空表不阻断面板）
    try:
        with open(_HISTORY_PATH, encoding="utf-8") as f:
            history = json.load(f)
        if not isinstance(history, list):
            history = []
    except (OSError, json.JSONDecodeError):
        history = []
    board = _read_board()
    return {
        "registry": reg,
        "services": _services(reg, ws),
        "schedule": sch,
        "health": health,
        "health_friendly": _friendly_issues(health),
        "health_history": history[-30:],
        "pulse": _health_pulse(history),      # R1 激励层（streak+热力图聚合）
        "consolidation_proposals": proposals,
        "copy": {"ai_prompt": _ai_prompt(health, ws)},
        "dashboard": dash,
        "board": board,
        "board_stats": _board_stats(board),   # R1 完成率（全局+各项目）
    }


def api_toggle(component_id, enabled):
    """开关=意图落 registry + 现实落 schtasks（装/卸）。返回最新聚合态。"""
    reg = _read_registry()
    found = False
    for c in reg.get("components", []):
        if c.get("id") == component_id:
            c["enabled"] = bool(enabled)
            found = True
            break
    if not found:
        return {"ok": False, "error": f"未知组件: {component_id}"}
    _write_registry(reg)

    if enabled:
        rc, out = _run_sm("install", "--task", component_id)
    else:
        rc, out = _run_sm("uninstall", "--task", component_id)
    return {"ok": rc == 0, "action": "install" if enabled else "uninstall",
            "detail": out.strip()[:400], "state": api_state()}


def api_run(component_id):
    """立即运行组件入口（不依赖调度）。完成后返回最新聚合态。"""
    reg = _read_registry()
    comp = next((c for c in reg.get("components", [])
                 if c.get("id") == component_id), None)
    if not comp:
        return {"ok": False, "error": f"未知组件: {component_id}"}
    impl = comp.get("implementation", {})
    entry = impl.get("entry") or "sb_healthlite.py"
    parts = entry.split()
    script = os.path.join(SCRIPTS, parts[0])
    cmd = [sys.executable, script, *parts[1:], "--quiet"]
    ws = impl.get("workspace")
    if ws:
        cmd += ["--workspace", ws]
    try:
        r = subprocess.run(cmd, capture_output=True, encoding=_SUB_ENC,
                           errors="replace", timeout=RUN_TIMEOUT_SEC, cwd=SCRIPTS)
        rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"运行超时（>{RUN_TIMEOUT_SEC}s）"}
    return {"ok": rc == 0, "exit_code": rc, "detail": out.strip()[:400],
            "state": api_state()}


# ---------------------------------------------------------------------------
# 健康看板（M3-A：M1 只读看板迁入服务，/dashboard 托管 + 一键重新生成）
# ---------------------------------------------------------------------------
def _active_ws(reg=None):
    """取 registry 中声明的活动 workspace（第一个带 implementation.workspace 的组件）。"""
    reg = reg or _read_registry()
    for c in reg.get("components", []):
        ws = (c.get("implementation") or {}).get("workspace")
        if ws:
            return ws
    return None


def _build_dashboard():
    """生成健康看板：白名单固定脚本 sb_dashboard.py（严格只读，不写记忆数据）。"""
    cmd = [sys.executable, os.path.join(SCRIPTS, "sb_dashboard.py"),
           "--output", _DASHBOARD_PATH]
    ws = _active_ws()
    if ws:
        cmd += ["--workspace", ws]
    try:
        r = subprocess.run(cmd, capture_output=True, encoding=_SUB_ENC,
                           errors="replace", timeout=DASHBOARD_TIMEOUT_SEC,
                           cwd=SCRIPTS)
        rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"生成超时（>{DASHBOARD_TIMEOUT_SEC}s）"
    if rc != 0:
        return False, (out.strip()[-300:] or f"退出码 {rc}")
    return True, out.strip()[-200:]


def api_dashboard_refresh():
    ok, detail = _build_dashboard()
    return {"ok": ok, "detail": detail}


# ---------------------------------------------------------------------------
# 整理建议应用（D1-B：两段式的 C 端化——「人工确认」不再等于「必须命令行」。
# 铁律不变：面板永不自动 apply；这里是用户显式点击「确认应用」才触发的
# 人工通道，后端白名单固定脚本、无参数透传，apply 前引擎自动备份+审计）
# ---------------------------------------------------------------------------
CONSOLIDATE_TIMEOUT_SEC = 300


def api_consolidate_apply():
    ws = _active_ws()
    if not ws:
        return {"ok": False, "error": "未找到数据工作区，无法应用"}
    prop_path = os.path.join(sb_core.get_workspace_dir(ws),
                             "consolidation_proposals.json")
    p = sb_core.read_json(prop_path)
    total = sum(len(v) for v in ((p or {}).get("actions") or {}).values())
    if not total:
        return {"ok": False, "error": "当前没有待应用的整理建议"}
    # 与 CLI 默认一致：--apply 不带 --actions（默认 a,b,c；D 档 supersede
    # 仍走开发者通道）
    cmd = [sys.executable, os.path.join(SCRIPTS, "sb_consolidate.py"),
           "--workspace", ws, "--apply"]
    try:
        r = subprocess.run(cmd, capture_output=True, encoding=_SUB_ENC,
                           errors="replace", timeout=CONSOLIDATE_TIMEOUT_SEC,
                           cwd=SCRIPTS)
        rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return {"ok": False,
                "error": f"应用超时（>{CONSOLIDATE_TIMEOUT_SEC}s），建议交给 AI 深入检查"}
    return {"ok": rc == 0, "exit_code": rc, "applied_before": total,
            "detail": out.strip()[-400:], "state": api_state()}


# ---------------------------------------------------------------------------
# 正在推进（项目 + 任务看板，2026-08-31 第四区）
# 数据：~/.workbuddy/super-brain/workbench_board.json（本地单文件，原子写）。
# 双通道：面板 CRUD + Agent「对话即上板」（砚在对话收尾直接写此文件，
# schema 见 SKILL.md §10.4）。首次读取时用真实项目数据播种。
# ---------------------------------------------------------------------------
BOARD_STATUSES = ["进行中", "待拍板", "规划中", "已完成", "暂停"]


def _seed_board():
    """首次播种：手上正在推进的真实项目与对话中提到的任务（来源：工作记忆）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return {
        "version": 1,
        "updated_at": now,
        "projects": [
            {"id": "p_superbrain", "name": "超脑（Super Brain）",
             "status": "进行中",
             "note": "阶段2 全量收尾；v3.12.2 攒发布（后台整合+时态+图谱消融+工作台）",
             "updated_at": now},
            {"id": "p_workbench", "name": "超脑工作台",
             "status": "进行中",
             "note": "C 端化改造完成；P3 体检历史趋势待做",
             "updated_at": now},
            {"id": "p_portfolio", "name": "作品集网站 v8",
             "status": "进行中",
             "note": "a1m1ng.cn；开发统一在知识库框架下",
             "updated_at": now},
            {"id": "p_yanshen", "name": "砚之身",
             "status": "规划中",
             "note": "M0-M3 完成；M4+ 规划中（VTuber 集成、TTS 全链路、桌宠打包）",
             "updated_at": now},
            {"id": "p_tarot", "name": "Liquid Tarot",
             "status": "进行中",
             "note": "iOS 27 Liquid Glass 风格 web app；塔罗 KB 14 本建设中",
             "updated_at": now},
            {"id": "p_mobile", "name": "mobile-hifi-B",
             "status": "进行中",
             "note": "v3.5.0+；dock 栏玻璃效果偏移排查中",
             "updated_at": now},
        ],
        "tasks": [
            {"id": "t_seed1", "title": "v3.12.2 发布（走 github-project-publisher，需拍板）",
             "project": "超脑（Super Brain）", "done": False, "due": None},
            {"id": "t_seed2", "title": "graph build 定期跑（新记忆 ent=0，建图后才进工作空间）",
             "project": "超脑（Super Brain）", "done": False, "due": None},
            {"id": "t_seed3", "title": "「AI 深入检查」自动化版（error 写待办文件，先评估 token 契约）",
             "project": "超脑工作台", "done": False, "due": None},
            {"id": "t_seed4", "title": "工作台 P3：体检历史趋势视图",
             "project": "超脑工作台", "done": False, "due": None},
            {"id": "t_seed5", "title": "清理 super-brain 数据目录 health_lite.lock.deleted.* 残留",
             "project": "超脑（Super Brain）", "done": False, "due": None},
            {"id": "t_seed6", "title": "access 统计死字段恢复",
             "project": "超脑（Super Brain）", "done": False, "due": None},
        ],
    }


def _read_board():
    b = sb_core.read_json(_BOARD_PATH)
    if not (isinstance(b, dict) and isinstance(b.get("projects"), list)
            and isinstance(b.get("tasks"), list)):
        b = _seed_board()          # 文件缺失或损坏 → 播种（损坏不静默覆盖：先备份）
        if os.path.exists(_BOARD_PATH):
            try:
                os.replace(_BOARD_PATH, _BOARD_PATH + ".corrupt.bak")
            except OSError:
                pass
        sb_core.write_json(_BOARD_PATH, b)
    return b


def _write_board(b):
    b["version"] = 1
    b["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    sb_core.write_json(_BOARD_PATH, b)     # 原子写（tmp+rename）


def _new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _norm_due(d):
    """截止日期规范化：仅接受 YYYY-MM-DD，其他返回 None。"""
    s = str(d or "").strip()[:10]
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return None


def _validate_import(b):
    """R2 导入消毒：结构合法才放行，字段逐条净化重建（不信任外部文件）。

    返回 (ok, result)：失败时 result 是人话错误；成功时是重建后的干净 board。"""
    if not isinstance(b, dict):
        return False, "文件格式不对：应该是一个 JSON 对象"
    if not (isinstance(b.get("projects"), list)
            and isinstance(b.get("tasks"), list)):
        return False, "文件里没有 projects / tasks 数据，不像本工作台导出的备份"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    clean = {"version": 1, "projects": [], "tasks": []}
    seen_p, seen_t = set(), set()
    for p in b["projects"][:200]:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()[:40]
        if not name:
            continue
        if len(clean["projects"]) >= 200:
            break
        pid = str(p.get("id") or "")[:40]
        if not pid or pid in seen_p:
            pid = _new_id("p")
        seen_p.add(pid)
        clean["projects"].append({
            "id": pid, "name": name,
            "status": p.get("status") if p.get("status") in BOARD_STATUSES else "进行中",
            "note": str(p.get("note") or "").strip()[:200],
            "pinned": bool(p.get("pinned")),
            "updated_at": str(p.get("updated_at") or now)[:20],
        })
    for t in b["tasks"]:
        # 先过滤后截断：坏数据（空标题/非法条目）不占用 2000 条护栏名额
        if len(clean["tasks"]) >= 2000:
            break
        if not isinstance(t, dict):
            continue
        title = str(t.get("title") or "").strip()[:120]
        if not title:
            continue
        tid = str(t.get("id") or "")[:40]
        if not tid or tid in seen_t:
            tid = _new_id("t")
        seen_t.add(tid)
        clean["tasks"].append({
            "id": tid, "title": title,
            "project": str(t.get("project") or "").strip()[:60],
            "done": bool(t.get("done")),
            "due": _norm_due(t.get("due")),
        })
    return True, clean


def api_board(payload):
    """看板 CRUD 单端点分发（写动作仅限 board JSON，无路径/命令透传）。"""
    action = payload.get("action")
    b = _read_board()
    if action == "add_task":
        title = str(payload.get("title") or "").strip()[:120]
        if not title:
            return {"ok": False, "error": "任务内容不能为空"}
        b["tasks"].insert(0, {
            "id": _new_id("t"), "title": title,
            "project": str(payload.get("project") or "").strip()[:60],
            "done": False, "due": _norm_due(payload.get("due")),
        })
    elif action == "toggle_task":
        t = next((x for x in b["tasks"] if x.get("id") == payload.get("id")), None)
        if not t:
            return {"ok": False, "error": "任务不存在"}
        t["done"] = not t.get("done")
    elif action == "del_task":
        b["tasks"] = [x for x in b["tasks"] if x.get("id") != payload.get("id")]
    elif action == "add_project":
        name = str(payload.get("name") or "").strip()[:40]
        if not name:
            return {"ok": False, "error": "项目名不能为空"}
        status = payload.get("status") if payload.get("status") in BOARD_STATUSES else "进行中"
        b["projects"].append({
            "id": _new_id("p"), "name": name, "status": status,
            "note": str(payload.get("note") or "").strip()[:200],
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
    elif action == "update_project":
        p = next((x for x in b["projects"] if x.get("id") == payload.get("id")), None)
        if not p:
            return {"ok": False, "error": "项目不存在"}
        if payload.get("status") in BOARD_STATUSES:
            p["status"] = payload["status"]
        if "note" in payload:
            p["note"] = str(payload.get("note") or "").strip()[:200]
        p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    elif action == "move_project":
        # 排序：数组顺序即展示顺序（pinned 渲染时置前）
        ps = b["projects"]
        idx = next((i for i, p in enumerate(ps)
                    if p.get("id") == payload.get("id")), None)
        if idx is None:
            return {"ok": False, "error": "项目不存在"}
        step = -1 if payload.get("dir") == "up" else 1
        j = idx + step
        if 0 <= j < len(ps):
            ps[idx], ps[j] = ps[j], ps[idx]
    elif action == "toggle_pin":
        p = next((x for x in b["projects"] if x.get("id") == payload.get("id")), None)
        if not p:
            return {"ok": False, "error": "项目不存在"}
        p["pinned"] = not p.get("pinned")
    elif action == "del_project":
        b["projects"] = [x for x in b["projects"] if x.get("id") != payload.get("id")]
    elif action == "import_board":
        # R2 导入恢复：消毒校验通过才落盘；旧文件先备份 .pre-import.bak
        # （铁律 2：导入必须支持上千条、清空级操作需确认——确认在前端 confirm 完成）
        ok, result = _validate_import(payload.get("data"))
        if not ok:
            return {"ok": False, "error": result}
        if os.path.exists(_BOARD_PATH):
            try:
                os.replace(_BOARD_PATH, _BOARD_PATH + ".pre-import.bak")
            except OSError:
                pass
        _write_board(result)
        return {"ok": True, "imported": {"projects": len(result["projects"]),
                                         "tasks": len(result["tasks"])},
                "state": api_state()}
    else:
        return {"ok": False, "error": f"未知操作: {action}"}
    _write_board(b)
    return {"ok": True, "state": api_state()}


# ---------------------------------------------------------------------------
# HTTP 层
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SBWorkbench/1.0"

    def log_message(self, fmt, *args):  # 计划任务/控制台友好：单行精简日志
        sys.stderr.write("[workbench] %s\n" % (fmt % args))

    # ---- GET ----
    def do_GET(self):
        path_only = self.path.split("?", 1)[0]
        if path_only in ("/", "/index.html"):
            body = PAGE_HTML.replace("__PORT__", str(self.server.server_address[1]))
            self._send_html(body)
        elif path_only == "/api/state":
            self._send_json(api_state())
        elif self.path == "/api/board/poll":
            # 轻量轮询端点：只读 board，无子进程——「对话即上板」实时性靠它（5s）
            self._send_json(_read_board())
        elif self.path == "/dashboard" or self.path.startswith("/dashboard?"):
            # M3-A→v2：健康看板托管。`?embed=1`（工作台「记忆图谱」Tab 内嵌
            # iframe 用）不注入工具条，避免与宿主页功能重复。
            if not os.path.exists(_DASHBOARD_PATH):
                ok, err = _build_dashboard()
                if not ok:
                    self._send_html("<meta charset='utf-8'><body style='font-family:sans-serif'>"
                                    "<h2>看板生成失败</h2><pre>%s</pre></body>" % html.escape(err))
                    return
            try:
                with open(_DASHBOARD_PATH, "r", encoding="utf-8") as f:
                    page = f.read()
            except OSError as e:
                self._send_html("<meta charset='utf-8'><h2>看板读取失败：%s</h2>"
                                % html.escape(str(e)))
                return
            if "embed=1" not in (self.path.split("?", 1) + [""])[1]:
                page = page.replace("</body>", _DASHBOARD_TOOLBAR + "</body>")
            self._send_html(page)
        elif self.path == "/api/proposals":
            st = api_state()
            self._send_json(st.get("consolidation_proposals") or {})
        else:
            self.send_error(404, "not found")

    # ---- POST ----
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        # 256KB：看板导入恢复（R2）的 JSON 体积可达数十 KB；仅本机回环可达
        if length > 262144:
            self._send_json({"ok": False, "error": "payload too large"}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({"ok": False, "error": "invalid JSON"}, 400)
            return
        if self.path == "/api/toggle":
            self._send_json(api_toggle(payload.get("component_id"),
                                       bool(payload.get("enabled"))))
        elif self.path == "/api/run":
            self._send_json(api_run(payload.get("component_id")))
        elif self.path == "/api/dashboard/refresh":
            self._send_json(api_dashboard_refresh())
        elif self.path == "/api/consolidate/apply":
            self._send_json(api_consolidate_apply())
        elif self.path == "/api/board":
            self._send_json(api_board(payload))
        else:
            self._send_json({"ok": False, "error": "unknown endpoint"}, 404)

    # ---- helpers ----
    def _send_html(self, text):
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


# ---------------------------------------------------------------------------
# 面板页（单文件内嵌，零外部依赖，断网可用；超脑品牌=琥珀 on 暖白）
# ---------------------------------------------------------------------------
# 看板托管时注入的固定工具条（重新生成 + 返回面板；零依赖内联 JS）
_DASHBOARD_TOOLBAR = (
    '<div style="position:fixed;bottom:18px;right:18px;z-index:999;display:flex;'
    'gap:8px;font-family:sans-serif">'
    '<button id="sbd-btn" onclick="sbdRefresh()" style="padding:8px 16px;'
    'border:1px solid #e8e2d4;background:#fff;border-radius:8px;font-size:13px;'
    'cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.08)">&#8635; 重新生成</button>'
    '<a href="/" style="padding:8px 16px;border:1px solid #e8e2d4;background:#fff;'
    'border-radius:8px;font-size:13px;text-decoration:none;color:#444;'
    'box-shadow:0 2px 8px rgba(0,0,0,.08)">返回工作台</a></div>'
    '<script>async function sbdRefresh(){var b=document.getElementById("sbd-btn");'
    'b.disabled=true;b.textContent="生成中…";'
    'try{var r=await fetch("/api/dashboard/refresh",{method:"POST"});'
    'var j=await r.json();'
    'if(j.ok){location.reload();}else{alert("生成失败："+(j.detail||j.error||""));'
    'b.disabled=false;b.textContent="\\u21bb 重新生成";}}catch(e){'
    'alert("失败："+e.message);b.disabled=false;}}</script>'
)

PAGE_HTML = r"""
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>超脑工作台</title>
<script>
/* 防闪白：渲染前先定主题（URL 参数 ?theme= > localStorage > 跟随系统） */
(function(){var t=null;
try{var q=new URLSearchParams(location.search).get("theme");
if(q==="dark"||q==="light"){t=q;}else{t=localStorage.getItem("wb_workbench_theme");}}catch(e){}
if(t!=="dark"&&t!=="light"){t=(window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches)?"dark":"light";}
if(t==="dark")document.documentElement.dataset.theme="dark";})();
</script>
<style>
  /* 设计 Token — 白盒子画廊语言（源自 a1m1ng.cn v8）× 超脑琥珀 */
  :root {
    --bg:        #faf9f6;
    --surface:   #ffffff;
    --warm-gray: #ebe8e2;
    --line:      #d9d4cc;
    --ink:       #1a1917;
    --ink2:      #5c5a55;
    --ink3:      #807d76;
    --amber:     #D98A1F;
    --amber-deep:#8a5a0e;
    --amber-soft:rgba(217,138,31,.10);
    --cinnabar:  #b84525;
    --cinnabar-soft: rgba(184,69,37,.08);
    --ok:        #1D9E75;
    --err:       #C0442B;
    --card-dark: #1a1917;
    --due-ink:   #7c3117;
    --serif: 'Noto Serif SC', Georgia, 'Songti SC', serif;
    --mono:  'JetBrains Mono', 'SF Mono', Consolas, monospace;
    --sans:  'Inter', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    --shadow: 0 12px 36px rgba(26,25,23,.09);
    --shadow-hover: 0 18px 48px rgba(26,25,23,.14);
  }
  /* ── 暗色主题（R3）：琥珀提亮一档保对比；amber-deep 语义反转
     （亮色=更深的琥珀字，暗色=更亮的琥珀字）；color-scheme 让原生
     控件（checkbox/date/滚动条）跟随暗色。iframe 内 dashboard 暂保持亮色。 */
  :root[data-theme="dark"] {
    color-scheme: dark;
    --bg:        #141311;
    --surface:   #1e1d1a;
    --warm-gray: #2a2721;
    --line:      #3a362e;
    --ink:       #ece9e2;
    --ink2:      #b3afa4;
    --ink3:      #837f74;
    --amber:     #E89B2E;
    --amber-deep:#f0b45e;
    --amber-soft:rgba(232,155,46,.13);
    --cinnabar:  #d4694a;
    --cinnabar-soft: rgba(212,105,74,.13);
    --ok:        #2fb98c;
    --err:       #e06a4e;
    --card-dark: #1e1c19;
    --due-ink:   #f0a58f;
    --shadow: 0 12px 36px rgba(0,0,0,.45);
    --shadow-hover: 0 18px 48px rgba(0,0,0,.55);
  }
  :root[data-theme="dark"] .hero { border:1px solid rgba(255,255,255,.07); }
  :root[data-theme="dark"] .slider { background:#45413a; }
  :root[data-theme="dark"] .toast { border:1px solid var(--line); }
  /* 主题切换小圆钮（sub 行右侧） */
  .themebtn { width:34px; height:34px; min-height:0; padding:0; display:inline-flex;
              align-items:center; justify-content:center; border-radius:50%;
              color:var(--ink3); flex:none; }
  .themebtn:hover { color:var(--amber); }
  * { box-sizing:border-box; margin:0; padding:0; }
  ::selection { background:var(--cinnabar); color:#fff; }
  body { background:var(--bg); color:var(--ink); font-family:var(--sans);
         font-size:14px; line-height:1.65;
         -webkit-font-smoothing:antialiased; }
  .wrap { max-width:880px; margin:0 auto; padding:34px 20px 72px; }

  /* 页头：mono 小字距排版（编辑物感） */
  .kicker { font-family:var(--mono); font-size:10px; letter-spacing:3px;
            text-transform:uppercase; color:var(--cinnabar); }
  h1 { font-family:var(--serif); font-size:30px; font-weight:900;
       letter-spacing:-.5px; line-height:1.15; margin-top:6px; }
  h1 small { font-family:var(--mono); font-size:11px; font-weight:400;
             letter-spacing:1.5px; color:var(--ink3); margin-left:14px; }
  .sub { color:var(--ink3); font-size:12.5px; margin:8px 0 26px; }

  /* 区块标题：mono 编号 + 细线 */
  h2.sec { display:flex; align-items:center; gap:12px; margin:34px 0 12px;
           font-family:var(--mono); font-size:11px; font-weight:600;
           letter-spacing:2.5px; text-transform:uppercase; color:var(--ink2); }
  h2.sec::after { content:""; flex:1; height:1px; background:var(--line); }
  h2.sec .no { color:var(--cinnabar); }

  /* 双 Tab 融合导航（管家 / 记忆图谱） */
  .tabs { display:flex; gap:4px; margin:0 0 22px; border-bottom:1px solid var(--line); }
  .tab { font-family:var(--mono); font-size:12px; letter-spacing:2px;
         text-transform:uppercase; padding:11px 20px; cursor:pointer; color:var(--ink3);
         border:none; background:none; border-bottom:2px solid transparent;
         margin-bottom:-1px; transition:color .2s, border-color .2s; }
  .tab:hover { color:var(--ink); }
  .tab.active { color:var(--ink); border-bottom-color:var(--amber); font-weight:600; }
  .tab .tno { color:var(--cinnabar); margin-right:6px; }
  /* 记忆图谱 Tab */
  .graphbar { display:flex; align-items:center; gap:12px; margin-bottom:12px;
              flex-wrap:wrap; }
  .graph-frame-wrap { border:1px solid var(--line); border-radius:16px; overflow:hidden;
                      background:var(--surface); box-shadow:var(--shadow); }
  #graph-frame { width:100%; height:78vh; border:none; display:block; }

  .card { background:var(--card); border:1px solid var(--line); border-radius:16px;
          padding:20px 22px; margin-bottom:14px;
          box-shadow:0 1px 2px rgba(26,25,23,.04);
          transition:box-shadow .35s, transform .35s; }
  .card.lift:hover { box-shadow:var(--shadow-hover); transform:translateY(-2px); }

  /* ── 01 状态横幅：白盒子里的深色作品卡 ── */
  .hero { background:var(--card-dark); color:#f5f3ee; border:none;
          border-radius:16px; padding:26px 28px; box-shadow:var(--shadow); }
  .hero .kicker { color:var(--amber); }
  .hero-title { font-family:var(--serif); font-size:24px; font-weight:900;
                letter-spacing:-.3px; display:flex; align-items:center; gap:10px; }
  .hero-meta { color:#a8a49b; font-size:12.5px; margin-top:6px; }
  .btnrow { display:flex; gap:8px; flex-wrap:wrap; margin-top:16px; }
  .ilist { margin-top:14px; display:flex; flex-direction:column; gap:8px; }
  .ilist .it { background:rgba(255,255,255,.055); border:1px solid rgba(255,255,255,.08);
               border-radius:10px; padding:10px 13px; font-size:12.5px; color:#d8d4cb; }
  .ilist.err .it { background:rgba(192,68,43,.14); border-color:rgba(192,68,43,.3);
                   color:#f2c4b6; }
  .ilist .it b { display:block; font-size:13.5px; color:#f5f3ee; }

  /* 徽章：mono 编辑物感 */
  .badge { display:inline-block; border-radius:3px; padding:2px 9px; font-size:10.5px;
           font-family:var(--mono); font-weight:600; letter-spacing:1.5px;
           cursor:pointer; border:1px solid transparent; vertical-align:2px; }
  .badge.进行中 { background:var(--amber-soft); color:var(--amber-deep); border-color:rgba(217,138,31,.25); }
  .badge.待拍板 { background:var(--cinnabar-soft); color:var(--cinnabar); border-color:rgba(184,69,37,.22); }
  .badge.规划中 { background:var(--warm-gray); color:var(--ink2); border-color:var(--line); }
  .badge.暂停   { background:var(--warm-gray); color:var(--ink3); border-color:var(--line); }
  .badge.已完成 { background:rgba(29,158,117,.10); color:#177a58; border-color:rgba(29,158,117,.22); }

  .dot { display:inline-block; width:8px; height:8px; border-radius:50%;
         margin-right:6px; vertical-align:1px; flex:none; }
  .dot.ok{background:var(--ok);} .dot.warn{background:var(--amber);}
  .dot.err{background:var(--err);} .dot.off{background:#c9c4b4;}
  .dot.run{background:var(--amber); animation:pulse 1.1s infinite;}
  @keyframes pulse { 50% { opacity:.3; } }
  /* R5 微交互：完成率环加载/更新时从满圈扫到目标值（勾任务即重放=完成反馈） */
  @keyframes ringfill { from { stroke-dashoffset:157.1; } }
  /* R5 勾选完成 pop：checkbox 先放大再回弹（物理手感） */
  @keyframes pop { 0% { transform:scale(1); } 40% { transform:scale(1.3); }
                   100% { transform:scale(1); } }

  /* 按钮 */
  button, a.btn { border:1px solid var(--line); background:var(--surface); border-radius:9px;
           padding:7px 15px; font-size:13px; cursor:pointer; color:var(--ink2);
           text-decoration:none; display:inline-block; font-family:var(--sans);
           transition:transform .2s, box-shadow .2s, border-color .2s, color .2s; }
  button:hover, a.btn:hover { border-color:var(--amber); color:var(--amber-deep);
           transform:translateY(-1px); box-shadow:0 4px 12px rgba(26,25,23,.08); }
  button:disabled { opacity:.45; cursor:default; transform:none; box-shadow:none; }
  /* R5 微交互：物理按压手感（hover 抬起 → active 压下，卡槽反馈） */
  button:active, a.btn:active { transform:translateY(0) scale(.97); box-shadow:none; }
  /* R5 键盘可达基线：Tab 聚焦可见环（hover 态不干扰鼠标用户） */
  button:focus-visible, a.btn:focus-visible, .binput:focus-visible,
  input[type="checkbox"]:focus-visible, input[type="date"]:focus-visible {
           outline:2px solid var(--amber); outline-offset:2px; }
  button.primary { background:var(--amber); border-color:var(--amber); color:#fff;
                   font-weight:600; }
  button.primary:hover { background:var(--amber-deep); border-color:var(--amber-deep); color:#fff; }
  button.danger { border-color:rgba(192,68,43,.4); color:var(--cinnabar); }

  /* 服务卡 */
  .row { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
  .cname { font-size:15px; font-weight:650; }
  .cdesc { font-size:12.5px; color:var(--ink2); margin:5px 0 10px; max-width:540px; }
  .meta { font-size:12px; color:var(--ink3); }
  .mno { font-family:var(--mono); font-size:10px; letter-spacing:2px;
         text-transform:uppercase; color:var(--ink3); }

  .switch { position:relative; width:44px; height:24px; flex:none; cursor:pointer; }
  .switch input { display:none; }
  .slider { position:absolute; inset:0; background:#d9d3c2; border-radius:12px;
            transition:background .25s; }
  .slider::after { content:""; position:absolute; width:18px; height:18px; border-radius:50%;
            background:#fff; top:3px; left:3px;
            transition:left .25s cubic-bezier(.34,1.56,.64,1);   /* R5 spring 回弹 */
            box-shadow:0 1px 3px rgba(0,0,0,.18); }
  .switch input:checked + .slider { background:var(--amber); }
  .switch input:checked + .slider::after { left:23px; }

  /* ── 03 需要你决定 ── */
  .plist { margin:10px 0 4px; display:flex; flex-direction:column; gap:7px; }
  .plist .p { border:1px solid var(--line); border-radius:10px; padding:9px 13px;
              font-size:12.5px; color:var(--ink2); }
  .plist .p em { font-style:normal; color:var(--cinnabar); font-weight:600;
                 margin-right:8px; font-size:10.5px; font-family:var(--mono);
                 letter-spacing:1px; }
  .confirm { margin-top:12px; background:var(--amber-soft); border:1px solid rgba(217,138,31,.3);
             border-radius:10px; padding:12px 14px; font-size:13px; color:var(--amber-deep); }

  /* ── 节奏条（R1 激励层）：完成率环 + 体检连续 + 热力图 ── */
  .pulse { display:flex; align-items:center; gap:26px; flex-wrap:wrap;
           background:var(--surface); border:1px solid var(--line); border-radius:16px;
           padding:16px 22px; margin:14px 0 0;
           box-shadow:0 1px 2px rgba(26,25,23,.04); }
  .pulse .seg { display:flex; align-items:center; gap:13px; }
  .pulse .big { font-family:var(--serif); font-size:27px; font-weight:900;
                letter-spacing:-.5px; line-height:1.1; }
  .pulse .lbl { font-size:11.5px; color:var(--ink3); line-height:1.55; }
  .pulse .lbl b { color:var(--ink2); font-weight:600; }
  .pulse .heat { display:flex; gap:3px; flex-wrap:wrap; margin-left:auto;
                 max-width:270px; }
  .heat i { width:11px; height:11px; border-radius:3px; background:var(--warm-gray); }
  .heat i.h1 { background:#f0d8ae; }
  .heat i.h2 { background:var(--amber); }
  .heat i.herr { background:var(--err); }
  .heat i.today { outline:2px solid var(--cinnabar); outline-offset:1px; }

  /* ── 04 正在推进 ── */
  .duebox { background:var(--cinnabar-soft); border:1px solid rgba(184,69,37,.2);
            border-radius:10px; padding:10px 13px; font-size:12.5px;
            color:var(--due-ink); margin-bottom:14px; }
  .duebox.soon { background:var(--amber-soft); border-color:rgba(217,138,31,.28);
                 color:var(--amber-deep); }
  /* 项目进度条（R1）：任务完成度一眼可见 */
  .pbar { height:3px; background:var(--warm-gray); border-radius:2px;
          margin-top:8px; overflow:hidden; }
  .pbar i { display:block; height:100%; background:var(--amber);
            border-radius:2px; transition:width .4s; }
  .proj { padding:14px 0; border-bottom:1px dashed var(--line); }
  .proj:last-of-type { border-bottom:none; }
  .proj.ispinned { background:linear-gradient(90deg, var(--amber-soft), transparent 55%);
                   border-radius:10px; padding-left:10px; padding-right:10px;
                   margin-left:-10px; margin-right:-10px; }
  /* 树形展开：▸/▾ 在项目名左侧，点击整行切换（工具钮不再混入展开） */
  .proj-head { display:flex; align-items:center; gap:9px; flex-wrap:wrap;
               cursor:pointer; }
  .proj-head:hover .pname { color:var(--amber-deep); }
  .chev { display:inline-flex; line-height:0; color:var(--ink3); flex:none;
          transition:transform .2s; transform:rotate(-90deg); }
  .chev.open { transform:rotate(0deg); color:var(--amber-deep); }
  .pname { font-family:var(--serif); font-size:16.5px; font-weight:900;
           letter-spacing:-.2px; }
  .t-count { font-family:var(--mono); font-size:10px; letter-spacing:1.5px;
             color:var(--ink3); }
  .proj-tools { margin-left:auto; display:flex; gap:2px; align-items:center; }
  .iconbtn { border:none; background:none; color:#b5ae9c; cursor:pointer; padding:4px 6px;
             border-radius:6px; line-height:0; transition:color .2s, background .2s; }
  .iconbtn:hover { color:var(--cinnabar); background:var(--warm-gray); }
  .iconbtn.pin-on { color:var(--amber); }
  .iconbtn:disabled { opacity:.3; cursor:default; }
  .pnote { font-size:12.5px; color:var(--ink3); margin:6px 0 2px; }
  .ptasks { margin:10px 0 2px 4px; border-left:2px solid var(--warm-gray);
            padding-left:14px; }
  .task { display:flex; align-items:flex-start; gap:9px; padding:6px 0;
          font-size:13.5px; }
  .task input[type="checkbox"] { width:16px; height:16px; accent-color:var(--amber);
          margin-top:2px; cursor:pointer; flex:none; }
  .task input[type="checkbox"]:checked { animation:pop .25s ease-out; }   /* R5 勾选 pop */
  .task.done .t-title { text-decoration:line-through; color:#b0aa9c; }
  .t-title { flex:1 1 auto; word-break:break-word;
             transition:color .3s, opacity .3s; }   /* R5 完成划线颜色渐变 */
  .t-due { flex:none; font-family:var(--mono); font-size:10.5px; letter-spacing:.5px;
           color:var(--ink3); margin-top:3px; }
  .t-due.over { color:var(--err); font-weight:700; }
  .t-due.soon { color:var(--amber-deep); font-weight:700; }
  .bform { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; }
  .binput { flex:1 1 180px; border:1px solid var(--line); border-radius:9px;
            padding:8px 12px; font-size:16px; font-family:var(--sans); color:var(--ink);
            background:var(--surface); min-width:0; }
  .binput:focus { outline:none; border-color:var(--amber);
            box-shadow:0 0 0 3px var(--amber-soft); }
  .binput.short { flex:0 1 150px; }
  .okmark { width:20px; height:20px; flex:none; }
  .empty { display:flex; gap:10px; align-items:center; }
  .note { font-size:11.5px; color:#a49e8c; margin-top:20px; line-height:1.8; }
  .toast { position:fixed; bottom:24px; left:50%; transform:translateX(-50%);
           background:var(--card-dark); color:#fff; font-size:12.5px; border-radius:9px;
           padding:9px 18px; opacity:0; transition:opacity .3s; pointer-events:none;
           max-width:86vw; box-shadow:var(--shadow); }
  .toast.show { opacity:.96; }
  @media (max-width:768px) {
    .wrap { padding:22px 14px calc(56px + env(safe-area-inset-bottom)); }
    .hero { padding:20px 18px; }
    .row { flex-direction:column; }
    .row .side { flex-direction:row !important; width:100%;
                 justify-content:space-between; align-items:center !important; }
    .proj-tools { margin-left:0; width:100%; justify-content:flex-start; }
    button, a.btn { padding:11px 16px; font-size:14px; min-height:44px; }
    h1 { font-size:24px; }
    .pulse { gap:16px; padding:14px 16px; }
    .pulse .heat { margin-left:0; max-width:none; width:100%; }
  }
  /* R5 无障碍基线：系统开启「减弱动态效果」时全站动效一刀切关闭
     （环/热力图直接显示终值，功能不受影响） */
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation:none !important; transition:none !important; }
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="kicker">Super Brain · Workbench</div>
  <h1>超脑工作台<small>记忆库管家 · 127.0.0.1:__PORT__</small></h1>
  <div class="sub" style="display:flex;align-items:center;gap:12px">
    <span style="flex:1">全部在你的电脑上完成：不联网、不花 AI 用量、无遥测。<span id="dashmeta"></span></span>
    <button id="theme-btn" class="themebtn" onclick="toggleTheme()" title="切换深色/浅色" aria-label="切换深色/浅色主题"></button>
  </div>

  <nav class="tabs">
    <button class="tab active" id="tabbtn-home" onclick="switchTab('home')">
      <span class="tno">A</span>管家</button>
    <button class="tab" id="tabbtn-graph" onclick="switchTab('graph')">
      <span class="tno">B</span>记忆图谱</button>
  </nav>

  <div id="tab-home">
  <section id="hero" class="hero" aria-live="polite"></section>
  <section id="pulse" class="pulse" aria-label="完成率与体检节奏"></section>

  <h2 class="sec"><span class="no">01</span>自动打理</h2>
  <div id="services"></div>

  <h2 class="sec"><span class="no">02</span>需要你决定</h2>
  <section id="decide" class="card"></section>

  <h2 class="sec"><span class="no">03</span>正在推进</h2>
  <section id="board" class="card"></section>

  <div class="note">
    「自动打理」的开关 = 是否安装每日自动任务，随时可以关；「需要你决定」遵循两段式，应用前自动备份、可在审计中追溯；「正在推进」的看板数据与 AI 对话实时同步——在对话里说的任务和项目进展，几秒内会出现在这里。
  </div>
  </div><!-- /tab-home -->

  <div id="tab-graph" style="display:none">
    <div class="graphbar">
      <span class="mno" id="graph-meta">数据快照（只读统计）</span>
      <button onclick="refreshGraph(this)">↻ 重新生成数据</button>
    </div>
    <div class="graph-frame-wrap">
      <iframe id="graph-frame" src="about:blank" title="超脑健康看板"></iframe>
    </div>
    <div class="note">健康红绿灯 · 门控看板 · 力导向知识图谱 · 实体/类型分布 · 晋升 Top20 · 审计动态——「管家」Tab 是此刻状态与动作，这里是全量数据快照与探索；体检或对话改动后点上方按钮刷新。</div>
  </div><!-- /tab-graph -->
</div>
<div id="toast" class="toast"></div>

<script>
"use strict";
let STATE = null;
let RUNNING = false;          // 体检进行中：横幅转运行态、全部按钮禁用
let DECIDE_OPEN = false;
let CONFIRMING = false;       // 整理建议二次确认态
let EXPANDED = new Set();     // 展开任务清单的项目 id
let EDIT_ID = null;           // 正在编辑 note 的项目 id

const $ = id => document.getElementById(id);

// ---------------- 主题（R3 暗色模式）：localStorage 记忆，首次跟随系统 ----------------
const THEME_KEY = "wb_workbench_theme";
function themeIcon(dark) {
  return dark
    ? '<svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">'
      + '<circle cx="12" cy="12" r="4.2" fill="currentColor"/>'
      + '<path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M4.9 4.9L7 7M17 17l2.1 2.1'
      + 'M19.1 4.9L17 7M7 17l-2.1 2.1" stroke="currentColor" stroke-width="1.8"'
      + ' stroke-linecap="round"/></svg>'
    : '<svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">'
      + '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z" fill="none"'
      + ' stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';
}
function applyTheme(t) {
  const dark = t === "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  const b = $("theme-btn");
  if (b) { b.innerHTML = themeIcon(dark);
           b.title = dark ? "切换到浅色" : "切换到深色"; }
}
function initTheme() {
  let t = null;
  try {
    const q = new URLSearchParams(location.search).get("theme");
    t = (q === "dark" || q === "light") ? q : localStorage.getItem(THEME_KEY);
  } catch (e) {}
  if (t !== "dark" && t !== "light") {
    t = (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches)
        ? "dark" : "light";
  }
  applyTheme(t);   // head 防闪脚本已设 dataset，这里补齐按钮图标
}
function toggleTheme() {
  const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(t);
  try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g,
    c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
}
function dot(cls) { return '<span class="dot ' + cls + '"></span>'; }
function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2400);
}
function fmtWhen(ts) {
  if (!ts) return "";
  const d = new Date(String(ts).replace(" ", "T").replace(/\//g, "-"));
  if (isNaN(d)) return String(ts);
  const hm = String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  if (d.toDateString() === new Date().toDateString()) return "今天 " + hm;
  if (d.toDateString() === new Date(Date.now() + 864e5).toDateString()) return "明天 " + hm;
  return (d.getMonth() + 1) + "月" + d.getDate() + "日 " + hm;
}
const SVG_OK = '<svg class="okmark" viewBox="0 0 24 24" aria-hidden="true">'
  + '<circle cx="12" cy="12" r="10" fill="#1D9E75"/>'
  + '<path d="M7.5 12.5l3 3 6-6.5" stroke="#fff" stroke-width="2.2" fill="none"'
  + ' stroke-linecap="round" stroke-linejoin="round"/></svg>';
const SVG_X = '<svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">'
  + '<path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.8"'
  + ' stroke-linecap="round"/></svg>';
const SVG_UP = '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">'
  + '<path d="M6 10V2M2.5 5.5L6 2l3.5 3.5" stroke="currentColor" stroke-width="1.7"'
  + ' fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const SVG_DOWN = '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">'
  + '<path d="M6 2v8M2.5 6.5L6 10l3.5-3.5" stroke="currentColor" stroke-width="1.7"'
  + ' fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const SVG_PIN = '<svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true">'
  + '<path d="M14.5 3l6.5 6.5-2.2.7-4.3 4.3.3 4.2-1.6 1.6-4-4L4 21l-1-1 4.7-5.2-4-4L5.3 9.2l4.2.3L13.8 5.2z"'
  + ' fill="currentColor"/></svg>';
const SVG_CHEV = '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">'
  + '<path d="M3 4.5L6 7.5l3-3" stroke="currentColor" stroke-width="1.7" fill="none"'
  + ' stroke-linecap="round" stroke-linejoin="round"/></svg>';
const SVG_EDIT = '<svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true">'
  + '<path d="M4 20l4.5-1L20 7.5 16.5 4 5 15.5 4 20z" fill="none"'
  + ' stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';

// ---------------- 数据 ----------------
async function load() {
  try {
    const r = await fetch("/api/state");
    STATE = await r.json();
    refreshAll();
  } catch (e) { toast("面板连接失败：" + e.message); }
}

// 统一刷新入口（铁律：渲染函数之间禁止互调，全部经由此处调度）
function refreshAll() {
  const dm = STATE.dashboard && STATE.dashboard.mtime;
  $("dashmeta").textContent = dm ? "健康看板数据生成于 " + dm + "。" : "";
  renderHero();
  renderPulse();
  renderServices();
  renderDecide();
  renderBoard();
  renderGraphBar();
}

// 「对话即上板」实时同步：轻量轮询 board（无子进程，5s），有变化只刷看板区。
// 编辑/确认/输入聚焦时跳过本轮应用，不打断操作。
async function pollBoard() {
  if (CONFIRMING || EDIT_ID || RUNNING) return;
  const box = $("board");
  if (document.activeElement && box.contains(document.activeElement)) return;
  try {
    const r = await fetch("/api/board/poll");
    const b = await r.json();
    const cur = STATE.board && STATE.board.updated_at;
    if (b && b.updated_at !== cur) {
      STATE.board = b;
      STATE.board_stats = localBoardStats(b);  // 完成率环即时反映（本地重算，不回源）
      renderBoard();
      renderPulse();
    }
  } catch (e) { /* 静默：下一轮再试 */ }
}
setInterval(pollBoard, 5000);

// board 统计的本地重算（与服务端 _board_stats 同口径）：poll 轻量更新用
function localBoardStats(b) {
  const tasks = (b && b.tasks) || [];
  const projects = (b && b.projects) || [];
  const done = tasks.filter(t => t.done).length;
  const by = {};
  projects.forEach(p => {
    const pt = tasks.filter(t => t.project === p.name);
    by[p.id] = { done: pt.filter(t => t.done).length, total: pt.length };
  });
  return { tasks_total: tasks.length, tasks_done: done,
           rate: tasks.length ? Math.round(done / tasks.length * 100) : 0,
           by_project: by };
}

// ---------------- Tab 融合导航（管家 / 记忆图谱） ----------------
let GRAPH_LOADED = false;
function switchTab(name) {
  const isHome = name === "home";
  $("tabbtn-home").classList.toggle("active", isHome);
  $("tabbtn-graph").classList.toggle("active", !isHome);
  $("tab-home").style.display = isHome ? "" : "none";
  $("tab-graph").style.display = isHome ? "none" : "";
  if (!isHome && !GRAPH_LOADED) {
    // 懒加载：首次进入图谱 Tab 才请求看板（59KB 单文件，含力导向图谱）
    $("graph-frame").src = "/dashboard?embed=1";
    GRAPH_LOADED = true;
  }
  renderGraphBar();
}
async function refreshGraph(btn) {
  if (btn) btn.disabled = true;
  toast("正在重新生成（只读统计，约 1-2 秒）…");
  try {
    const r = await fetch("/api/dashboard/refresh", { method: "POST" });
    const res = await r.json();
    if (res.ok) {
      await load();   // 刷新 STATE（含 dashboard.mtime），renderGraphBar 随 refreshAll 更新
      $("graph-frame").src = "/dashboard?embed=1&t=" + Date.now();  // 强制重载快照
      GRAPH_LOADED = true;
      toast("数据已更新");
    } else {
      toast("生成失败：" + esc(res.detail || res.error || ""));
    }
  } catch (e) { toast("刷新失败：" + e.message); }
  if (btn) btn.disabled = false;
}
function renderGraphBar() {
  const el = $("graph-meta");
  if (!el) return;
  const dm = STATE && STATE.dashboard && STATE.dashboard.mtime;   // null 防护：?tab=graph 直达时数据未到
  el.textContent = "数据快照（只读统计）"
    + (dm ? " · 生成于 " + dm : " · 进入本页时自动生成");
}
// R4：iframe 高度自适应 —— /dashboard 与宿主同源（本服务托管），直接量内容高度，
// 看板随宿主页面自然滚动（移动端无嵌套滚动陷阱）；量不到时保持 CSS 78vh 内滚兜底。
function fitGraphFrame() {
  const f = $("graph-frame");
  if (!f) return;
  try {
    const h = f.contentDocument && f.contentDocument.documentElement.scrollHeight;
    if (h && h > 240) f.style.height = (h + 24) + "px";
  } catch (e) { /* 跨域/加载异常：保持 78vh */ }
}

// ---------------- 01 状态横幅（深色作品卡） ----------------
function heroActions(extraErr) {
  return '<div class="btnrow">'
    + '<button class="primary" onclick="runNow()">立即体检</button>'
    + '<button onclick="switchTab(\'graph\')">查看记忆图谱</button>'
    + (extraErr ? '<button onclick="copyAI()">把体检结果交给 AI 深入检查</button>' : "")
    + '</div>';
}
function renderHero() {
  const el = $("hero");
  const h = STATE.health || {};
  const fi = STATE.health_friendly || [];
  const nErr = fi.filter(i => i.severity === "error").length;
  const nWarn = fi.length - nErr;
  const last = h.timestamp ? "上次体检：" + fmtWhen(h.timestamp) : "";
  const kicker = '<div class="kicker">Health · ' + esc(STATE.health_history
    ? STATE.health_history.length + " 次记录" : "—") + '</div>';

  if (RUNNING) {
    el.innerHTML = kicker + '<div class="hero-title">' + dot("run") + '正在体检…</div>'
      + '<div class="hero-meta">构建知识图谱 + 健康自检，约 10-30 秒，请勿关闭页面</div>';
    return;
  }
  if (!h.status || h.status === "never_ran") {
    el.innerHTML = kicker + '<div class="hero-title">' + dot("warn") + '还没体检过</div>'
      + '<div class="hero-meta">给记忆库做一次全面体检：构建知识图谱、检查健康状况、'
      + '汇总整理建议。完成后你会在这里看到体检结果和整理建议。'
      + '约 10-30 秒，全程本地、不联网、不花钱。</div>' + heroActions(false);
    return;
  }
  if (h.status === "ok") {
    el.innerHTML = kicker + '<div class="hero-title">' + SVG_OK + '一切正常</div>'
      + '<div class="hero-meta">' + esc(last) + ' · 未发现问题</div>'
      + trendSvg(STATE.health_history)
      + heroActions(false);
    return;
  }
  const isErr = h.status === "error" || h.status === "corrupt" || nErr > 0;
  const headline = isErr
    ? "发现 " + (nErr || fi.length) + " 个问题，建议处理"
    : nWarn + " 项提醒 · 都不影响使用";
  let html = kicker + '<div class="hero-title">' + dot(isErr ? "err" : "warn")
    + esc(headline) + '</div>'
    + '<div class="hero-meta">' + esc(last) + '</div>';
  if (fi.length) {
    html += '<div class="ilist' + (isErr ? " err" : "") + '">'
      + fi.map(i => '<div class="it"><b>' + esc(i.title) + '</b>'
        + esc(i.meaning) + '</div>').join("")
      + '</div>';
  }
  html += trendSvg(STATE.health_history) + heroActions(isErr);
  el.innerHTML = html;
}

// 体检历史微趋势：竖条颜色=结果、高度=提醒数、悬停看详情
function trendSvg(hist) {
  const items = (hist || []).slice(-30);
  if (items.length < 2) return "";
  const w = items.length * 10, h = 24;
  const bars = items.map((r, i) => {
    const c = r.status === "ok" ? "#1D9E75"
            : r.status === "warn" ? "#D98A1F" : "#C0442B";
    const hh = 6 + Math.min(18, (r.n_issues || 0) * 5);
    const when = String(r.ts || "").slice(0, 16).replace("T", " ");
    return '<rect x="' + (i * 10) + '" y="' + (h - hh) + '" width="6" height="'
      + hh + '" rx="2" fill="' + c + '"><title>' + esc(when + " · "
      + esc(r.status || "?") + " · " + (r.n_issues || 0) + " 项提醒")
      + '</title></rect>';
  }).join("");
  return '<div style="margin-top:12px"><span class="mno">Last ' + items.length
    + ' checks</span><svg width="' + w + '" height="' + h
    + '" style="display:block;margin-top:5px" aria-hidden="true">' + bars
    + '</svg></div>';
}

// ---------------- 节奏条（R1 激励层）：完成率环 + streak + 热力图 ----------------
function ringSvg(pct) {
  const r = 25, c = 2 * Math.PI * r;
  const off = (c * (1 - Math.max(0, Math.min(100, pct)) / 100)).toFixed(1);
  return '<svg width="62" height="62" viewBox="0 0 64 64" role="img"'
    + ' aria-label="任务完成率 ' + pct + '%">'
    + '<circle cx="32" cy="32" r="' + r + '" fill="none" stroke-width="6.5"'
    + ' style="stroke:var(--warm-gray)"/>'
    + '<circle cx="32" cy="32" r="' + r + '" fill="none" stroke-width="6.5"'
    + ' stroke-linecap="round" stroke-dasharray="' + c.toFixed(1) + '"'
    + ' stroke-dashoffset="' + off + '" transform="rotate(-90 32 32)"'
    + ' style="stroke:var(--amber); animation:ringfill .9s cubic-bezier(.2,.8,.2,1)"/>'
    + '<text x="32" y="30" text-anchor="middle" dominant-baseline="middle"'
    + ' style="font:900 15px Georgia,serif;fill:var(--ink)">' + pct + '</text>'
    + '<text x="32" y="45" text-anchor="middle"'
    + ' style="font:600 6.5px Consolas,monospace;letter-spacing:1px;'
    + 'fill:var(--ink3)">DONE</text></svg>';
}
function renderPulse() {
  const el = $("pulse");
  if (!el) return;
  const bs = STATE.board_stats || {};
  const pl = STATE.pulse || {};
  const total = bs.tasks_total || 0;
  const rate = bs.rate || 0;
  // streak 文案：中断不清零（渐变式语义），历史最高始终在
  let streak;
  if (!pl.last) {
    streak = '<span class="big">—</span><div class="lbl">还没体检过<br>跑一次开始积累连续记录</div>';
  } else if (pl.broken_days > 0) {
    streak = '<span class="big">' + (pl.current || 0) + '</span><div class="lbl">'
      + '上次连续 <b>' + (pl.current || 0) + '</b> 天 · 已中断 <b>' + pl.broken_days
      + '</b> 天<br>历史最高 <b>' + (pl.best || 0) + '</b> 天 · 跑一次体检就续上，记录还在</div>';
  } else {
    streak = '<span class="big">' + (pl.current || 0) + '</span><div class="lbl">'
      + '天连续体检 · 近 30 天 <b>' + (pl.runs30 || 0) + '</b> 次<br>历史最高 <b>'
      + (pl.best || 0) + '</b> 天</div>';
  }
  // 42 天热力图：灰=无记录、浅琥珀=1 次、琥珀=2+ 次、红=当天有 error
  const cells = (pl.heatmap || []).map((d, i) => {
    const cls = (d.worst === "error" || d.worst === "corrupt") ? " herr"
              : d.count >= 2 ? " h2" : d.count === 1 ? " h1" : "";
    const dt = d.date.slice(5).replace("-", "月") + "日";
    const tip = d.count ? dt + " · 体检 " + d.count + " 次 · " + d.worst
                        : dt + " · 无记录";
    return '<i class="' + cls.trim()
      + (i === (pl.heatmap.length - 1) ? " today" : "")
      + '" title="' + esc(tip) + '"></i>';
  }).join("");
  el.innerHTML = '<div class="seg">' + ringSvg(rate)
    + '<div class="lbl">任务完成率<br><b>' + (bs.tasks_done || 0) + " / " + total
    + '</b> 件</div></div>'
    + '<div class="seg">' + streak + '</div>'
    + '<div class="heat" aria-hidden="true">' + cells + '</div>';
}

// ---------------- 02 自动打理 ----------------
function renderServices() {
  const box = $("services");
  const svcs = STATE.services || [];
  const sch = (STATE.schedule && STATE.schedule.components) || {};
  box.innerHTML = svcs.map(s => {
    const d = s.display || {};
    const sc = sch[s.id] || {};
    const on = !!s.enabled;
    const statusLine = RUNNING
      ? dot("run") + "体检进行中…"
      : sc.installed
        ? dot("ok") + "已开启 · 下次自动体检 " + esc(sc.schedule || "")
        : dot("off") + "未开启" + (d.off_hint ? " · " + esc(d.off_hint) : "");
    const cost = s.token_cost || "不花钱";
    return '<div class="card lift"><div class="row">'
      + '<div><div class="cname">' + esc(d.name || s.id) + '</div>'
      + '<div class="cdesc">' + esc(d.description || "") + '</div>'
      + '<div class="meta">' + statusLine + '<br><span class="mno">Cost</span> '
      + esc(cost) + '</div></div>'
      + '<div class="side" style="flex:none;display:flex;flex-direction:column;gap:10px;align-items:flex-end">'
      + '<label class="switch"><input type="checkbox" ' + (on ? "checked" : "")
      + (RUNNING ? " disabled" : "")
      + ' onchange="toggle(\'' + s.id + '\', this.checked)"><span class="slider"></span></label>'
      + '<button' + (RUNNING ? " disabled" : "") + ' onclick="runNow()">'
      + esc(d.run_label || "立即运行") + '</button>'
      + '</div></div></div>';
  }).join("");
}

// ---------------- 03 需要你决定 ----------------
function renderDecide() {
  const el = $("decide");
  const p = STATE.consolidation_proposals;
  if (!p || !p.total) {
    CONFIRMING = false; DECIDE_OPEN = false;
    el.className = "card";
    el.innerHTML = '<div class="empty">' + SVG_OK
      + '<div><div class="cname">暂无整理建议</div>'
      + '<div class="meta">超脑检查过记忆库后，没有发现需要整理的东西。</div></div></div>';
    return;
  }
  const counts = p.counts || {};
  const labelOf = k => (p.kind_labels || {})[k] || k;
  const lines = Object.entries(counts).filter(([, n]) => n > 0)
    .map(([k, n]) => "· " + esc(labelOf(k)) + "：" + n + " 条").join("<br>");
  let html = '<div class="cname">有 ' + p.total + ' 条整理建议</div>'
    + '<div class="meta" style="margin:5px 0 2px">'
    + (p.generated_at ? "生成于 " + esc(fmtWhen(p.generated_at)) + "<br>" : "") + lines + '</div>';
  if (!DECIDE_OPEN) {
    html += '<div class="btnrow"><button onclick="openDecide()">看看建议</button></div>';
  } else {
    html += '<div class="plist">'
      + (p.items || []).map(i => '<div class="p"><em>' + esc(i.label) + '</em>'
        + esc(i.desc) + '</div>').join("")
      + '</div>';
    if (!CONFIRMING) {
      html += '<div class="btnrow">'
        + '<button class="primary" onclick="askApply()">应用这 ' + p.total + ' 条建议</button>'
        + '<button onclick="closeDecide()">收起</button></div>';
    } else {
      html += '<div class="confirm"><b>确认应用这 ' + p.total + ' 条建议？</b><br>'
        + '引擎会先自动备份，所有改动都能在审计记录中追溯。'
        + '<div class="btnrow" style="margin-top:10px">'
        + '<button class="danger" id="btn-apply" onclick="doApply()">确认应用</button>'
        + '<button onclick="cancelApply()">先不应用</button></div></div>';
    }
  }
  el.className = "card";
  el.innerHTML = html;
}

// ---------------- 04 正在推进（项目 + 任务看板） ----------------
const STATUS_ORDER = ["进行中", "待拍板", "规划中", "暂停", "已完成"];
function todayStr() {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0")
       + "-" + String(d.getDate()).padStart(2, "0");
}
function dueMeta(due) {
  if (!due) return null;
  const t = todayStr();
  if (due < t) {
    const n = Math.round((new Date(t) - new Date(due)) / 864e5);
    return { cls: "over", text: "已逾期 " + n + " 天" };
  }
  if (due === t) return { cls: "soon", text: "今天到期" };
  const diff = Math.round((new Date(due) - new Date(t)) / 864e5);
  if (diff <= 7) return { cls: "soon", text: diff + " 天后到期" };
  return { cls: "", text: due.slice(5) };
}
function taskRow(t, inProject) {
  const m = t.done ? null : dueMeta(t.due);
  return '<div class="task' + (t.done ? " done" : "") + '">'
    + '<input type="checkbox" ' + (t.done ? "checked" : "")
    + ' onchange="toggleTask(\'' + t.id + '\')">'
    + '<span class="t-title">' + esc(t.title) + '</span>'
    + (inProject ? "" : (t.project ? '<span class="badge ' + esc(t.project)
        + '" style="pointer-events:none">' + esc(t.project) + '</span>' : ""))
    + (m ? '<span class="t-due ' + m.cls + '">' + m.text + '</span>'
         : (t.due ? '<span class="t-due">' + esc(t.due.slice(5)) + '</span>' : ""))
    + '<button class="iconbtn" title="删除任务" onclick="delTask(\'' + t.id
    + '\')">' + SVG_X + '</button></div>';
}

function renderBoard() {
  const el = $("board");
  const b = STATE.board || { projects: [], tasks: [] };
  const tasks = b.tasks || [];
  const open = tasks.filter(t => !t.done);
  const done = tasks.filter(t => t.done);
  const projects = (b.projects || []);
  // 置顶优先，同层保持手动排序（稳定排序）
  const ordered = [...projects].sort((a, b2) => (b2.pinned ? 1 : 0) - (a.pinned ? 1 : 0));
  const today = todayStr();

  // 「今天要处理」：逾期 + 7 天内到期，全局置顶（铁律 5）
  const urgent = open.map(t => ({ t, m: dueMeta(t.due) }))
    .filter(x => x.m && x.m.cls !== "")
    .sort((a, b2) => (a.t.due < b2.t.due ? -1 : 1));
  let urgentHtml = "";
  if (urgent.length) {
    const hasOver = urgent.some(x => x.m.cls === "over");
    urgentHtml = '<div class="duebox' + (hasOver ? "" : " soon") + '"><b>'
      + (hasOver ? "有任务逾期：" : "最近到期：") + '</b>'
      + urgent.map(x => esc(x.t.title) + "（" + x.m.text + "）").join("；")
      + '</div>';
  }

  const projBlock = (p, idx, total) => {
    const myOpen = open.filter(t => t.project === p.name);
    const myDoneN = done.filter(t => t.project === p.name).length;
    const myAll = myOpen.length + myDoneN;
    const isOpen = EXPANDED.has(p.id);
    // 工具钮组只留管理动作（置顶/排序/删除），展开改由点击整行触发
    const tools =
        '<button class="iconbtn' + (p.pinned ? " pin-on" : "") + '" title="'
        + (p.pinned ? "取消置顶" : "置顶") + '" onclick="event.stopPropagation();togglePin(\''
        + p.id + '\')">' + SVG_PIN + '</button>'
      + '<button class="iconbtn" title="上移" ' + (idx === 0 ? "disabled" : "")
        + ' onclick="event.stopPropagation();moveProject(\'' + p.id + '\',\'up\')">'
        + SVG_UP + '</button>'
      + '<button class="iconbtn" title="下移" ' + (idx === total - 1 ? "disabled" : "")
        + ' onclick="event.stopPropagation();moveProject(\'' + p.id + '\',\'down\')">'
        + SVG_DOWN + '</button>'
      + '<button class="iconbtn" title="删除项目" onclick="event.stopPropagation();delProject(\''
        + p.id + '\')">' + SVG_X + '</button>';
    let body =
      '<div class="proj' + (p.pinned ? " ispinned" : "") + '">'
      + '<div class="proj-head" title="点击展开/收起该项目的任务" onclick="toggleExpand(\''
        + p.id + '\')">'
      + '<span class="chev' + (isOpen ? " open" : "") + '">' + SVG_CHEV + '</span>'
      + '<span class="pname">' + esc(p.name) + '</span>'
      + '<span class="badge ' + esc(p.status) + '" title="点击切换状态"'
      + ' onclick="event.stopPropagation();cycleStatus(\'' + p.id + '\',\''
        + esc(p.status) + '\')">'
      + esc(p.status) + '</span>'
      + '<span class="t-count" title="已完成/全部任务">'
      + (myAll ? myDoneN + "/" + myAll : "—") + '</span>'
      + '<div class="proj-tools">' + tools + '</div></div>';
    if (myAll) {
      const pct = Math.round(myDoneN / myAll * 100);
      body += '<div class="pbar" title="任务完成 ' + myDoneN + '/' + myAll
        + '（' + pct + '%）"><i style="width:' + pct + '%"></i></div>';
    }
    if (EDIT_ID === p.id) {
      body += '<div class="bform" style="margin-top:8px">'
        + '<input class="binput" id="ed-note" maxlength="200" value="'
        + esc(p.note || "") + '" placeholder="项目现状（一句话进展）">'
        + '<button onclick="saveNote(\'' + p.id + '\')">保存</button>'
        + '<button onclick="cancelEdit()">取消</button></div>';
    } else {
      body += '<div class="pnote">' + esc(p.note || "")
        + (p.note ? "" : '<span style="color:#b5ae9c">（点 ✎ 补充现状）</span>')
        + '</div>';
    }
    if (isOpen) {
      body += '<div class="ptasks">'
        + (myOpen.length ? myOpen.map(t => taskRow(t, true)).join("")
            : '<div class="meta" style="padding:4px 0">这个项目暂无进行中的任务。</div>')
        + '<div class="bform" style="margin-top:6px">'
        + '<input class="binput" id="pt-' + p.id + '" maxlength="120"'
        + ' placeholder="给「' + esc(p.name) + '」加任务，回车添加"'
        + ' onkeydown="if(event.key===\'Enter\')addTaskTo(\'' + p.id + '\')">'
        + '<button onclick="addTaskTo(\'' + p.id + '\')">添加</button></div>'
        + '</div>';
    }
    return body + '</div>';
  };

  // 「日常」：无项目归属的待办
  const loose = open.filter(t => !t.project || !projects.some(p => p.name === t.project));

  // 铁律 2：数据积累 30 条以上时温和提示备份（数据只在本机，无云端）
  const nAll = tasks.length + projects.length;
  const backupHint = (nAll >= 30)
    ? '<div class="duebox soon" style="margin-bottom:12px"><b>看板数据已有 ' + nAll
      + ' 条。</b>它们只保存在这台电脑上——建议点右上「导出 JSON」留一份备份。</div>'
    : "";

  el.innerHTML = urgentHtml + backupHint
    + '<div class="proj" style="border-bottom:none;padding-bottom:4px">'
    + '<div class="proj-head" style="cursor:default;gap:10px">'
    + '<span class="mno">Projects · 点击行展开任务 · 工具钮：置顶 / 排序 / 删除</span>'
    + '<span style="margin-left:auto;display:flex;gap:6px;align-items:center;flex:none">'
    + '<button style="padding:4px 12px;font-size:12px" onclick="exportBoard()">导出 JSON</button>'
    + '<button style="padding:4px 12px;font-size:12px" onclick="importBoardClick()">导入恢复</button>'
    + '<input type="file" id="import-file" accept=".json,application/json" style="display:none"'
    + ' onchange="importBoard(this)">'
    + '</span></div></div>'
    + (ordered.length ? ordered.map((p, i) => projBlock(p, i, ordered.length)).join("")
        : '<div class="meta" style="padding:4px 0 8px">还没有项目，在下方添加一个。</div>')
    + '<div class="bform">'
    + '<input class="binput" id="np-name" maxlength="40" placeholder="新项目名称">'
    + '<button onclick="addProject()">添加项目</button></div>'

    + '<div style="height:14px"></div>'
    + '<div class="mno">Loose tasks · 随手任务（不挂项目）</div>'
    + (loose.length ? loose.map(t => taskRow(t, false)).join("")
        : '<div class="meta" style="padding:4px 0">没有随手任务。</div>')
    + '<div class="bform">'
    + '<input class="binput" id="nt-title" maxlength="120" placeholder="随手记一件要做的事，回车添加"'
    + ' onkeydown="if(event.key===\'Enter\')addTask()">'
    + '<input class="binput short" id="nt-due" type="date" title="截止日期（可选）">'
    + '<button onclick="addTask()">添加任务</button></div>'

    + (done.length
        ? '<div style="height:14px"></div><div class="mno">Done · 已完成 '
          + done.length + '</div>' + done.map(t => taskRow(t, false)).join("")
        : "");
}

// ---------------- 动作（改数据 → refreshAll，渲染不互调） ----------------
function toggleExpand(id) {
  EXPANDED.has(id) ? EXPANDED.delete(id) : EXPANDED.add(id);
  renderBoard();
}
function startEdit(id) { EDIT_ID = id; renderBoard(); }
function cancelEdit() { EDIT_ID = null; renderBoard(); }
function saveNote(id) {
  const v = ($("ed-note").value || "").trim();
  boardAct({ action: "update_project", id: id, note: v }).then(ok => {
    if (ok) { EDIT_ID = null; toast("现状已更新"); }
  });
}
function cycleStatus(id, cur) {
  const i = STATUS_ORDER.indexOf(cur);
  const next = STATUS_ORDER[(i + 1) % STATUS_ORDER.length];
  boardAct({ action: "update_project", id: id, status: next });
}
function togglePin(id) { boardAct({ action: "toggle_pin", id: id }); }
function moveProject(id, dir) { boardAct({ action: "move_project", id: id, dir: dir }); }
function delProject(id) { boardAct({ action: "del_project", id: id }); }
function toggleTask(id) { boardAct({ action: "toggle_task", id: id }); }
function delTask(id) { boardAct({ action: "del_task", id: id }); }
function addTaskTo(pid) {
  const input = $("pt-" + pid);
  const title = (input && input.value || "").trim();
  if (!title) { toast("先写要做什么"); return; }
  const proj = ((STATE.board || {}).projects || []).find(p => p.id === pid);
  boardAct({ action: "add_task", title: title, project: proj ? proj.name : "" });
}
function addTask() {
  const title = ($("nt-title").value || "").trim();
  if (!title) { toast("先写要做什么"); return; }
  const due = $("nt-due").value || "";
  boardAct({ action: "add_task", title: title, due: due });
}
function addProject() {
  const name = ($("np-name").value || "").trim();
  if (!name) { toast("先写项目名"); return; }
  boardAct({ action: "add_project", name: name });
}
function openDecide() { DECIDE_OPEN = true; renderDecide(); }
function closeDecide() { DECIDE_OPEN = false; CONFIRMING = false; renderDecide(); }
function askApply() { CONFIRMING = true; renderDecide(); }
function cancelApply() { CONFIRMING = false; renderDecide(); }

function firstServiceId() {
  const s = (STATE.services || [])[0];
  return s ? s.id : "";
}
async function runNow() {
  if (RUNNING) return;
  const id = firstServiceId();
  if (!id) { toast("没有可运行的服务"); return; }
  RUNNING = true; refreshAll();
  try {
    const r = await fetch("/api/run", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ component_id: id }) });
    const res = await r.json();
    STATE = res.state || STATE;
    if (res.ok) toast("体检完成");
    else toast("体检没跑完（" + esc(res.error || ("退出码 " + res.exit_code)) + "）");
  } catch (e) { toast("体检失败：" + e.message); }
  RUNNING = false; refreshAll();
}
async function toggle(id, on) {
  toast(on ? "正在开启（安装每日自动任务）…" : "正在关闭（卸载每日任务）…");
  try {
    const r = await fetch("/api/toggle", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ component_id: id, enabled: on }) });
    const res = await r.json();
    if (res.ok === false && res.error) { toast(res.error); load(); return; }
    STATE = res.state || STATE; refreshAll();
    toast(on ? "已开启，明早开始自动体检" : "已关闭");
  } catch (e) { toast("操作失败：" + e.message); load(); }
}
async function doApply() {
  const b = $("btn-apply"); if (b) b.disabled = true;
  toast("正在应用（会先自动备份）…");
  try {
    const r = await fetch("/api/consolidate/apply", { method: "POST" });
    const res = await r.json();
    if (res.ok === false && res.error) {
      toast(res.error); CONFIRMING = false; renderDecide(); return;
    }
    STATE = res.state || STATE;
    CONFIRMING = false; DECIDE_OPEN = false;
    refreshAll();
    toast("应用完成，建议清单已更新");
  } catch (e) { toast("应用失败：" + e.message); if (b) b.disabled = false; }
}
async function boardAct(payload) {
  try {
    const r = await fetch("/api/board", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload) });
    const res = await r.json();
    if (res.ok === false && res.error) { toast(res.error); return false; }
    STATE = res.state || STATE; refreshAll(); return true;
  } catch (e) { toast("操作失败：" + e.message); return false; }
}

// ---------------- R2：看板导出 / 导入恢复（铁律 2 数据备份） ----------------
function exportBoard() {
  const b = STATE.board || { projects: [], tasks: [] };
  const blob = new Blob([JSON.stringify(b, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "workbench-board-" + todayStr() + ".json";
  a.click();
  URL.revokeObjectURL(a.href);
  toast("已导出到下载目录（含 " + ((b.tasks || []).length) + " 个任务）");
}
function importBoardClick() {
  const f = $("import-file");
  if (f) f.click();
}
async function importBoard(input) {
  const f = input.files && input.files[0];
  input.value = "";   // 清空以便下次能重选同一文件
  if (!f) return;
  let data;
  try { data = JSON.parse(await f.text()); }
  catch (e) { toast("这个文件不是有效的 JSON"); return; }
  const nProj = (Array.isArray((data || {}).projects) ? data.projects : []).length;
  const nTask = (Array.isArray((data || {}).tasks) ? data.tasks : []).length;
  if (!nProj && !nTask) { toast("文件里没有项目或任务数据"); return; }
  const cur = STATE.board || { projects: [], tasks: [] };
  if (!confirm("导入将覆盖当前看板（现有 " + (cur.projects || []).length + " 个项目、"
    + (cur.tasks || []).length + " 个任务；旧数据会自动备份为 .pre-import.bak）。"
    + "\\n\\n将导入：" + nProj + " 个项目、" + nTask + " 个任务。确定继续？")) return;
  try {
    const r = await fetch("/api/board", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "import_board", data: data }) });
    const res = await r.json();
    if (res.ok === false && res.error) { toast(res.error); return; }
    STATE = res.state || STATE; refreshAll();
    toast("导入完成：" + ((res.imported || {}).projects || 0) + " 个项目、"
      + ((res.imported || {}).tasks || 0) + " 个任务");
  } catch (e) { toast("导入失败：" + e.message); }
}
function copyAI() { copyText((STATE.copy || {}).ai_prompt || ""); }
function copyText(text) {
  navigator.clipboard.writeText(text).then(
    () => toast("已复制，去粘贴给 AI 即可"),
    () => toast("复制失败，请手动选择"));
}

initTheme();
const urlTab = new URLSearchParams(location.search).get("tab");
if (urlTab === "graph") switchTab("graph");   // R4 调试/直达通道（对称 ?theme=）
$("graph-frame").addEventListener("load", () => {
  fitGraphFrame();
  setTimeout(fitGraphFrame, 350);   // 二次校准：字体/图片晚到导致的布局变化
});
load();
setInterval(() => { if (!RUNNING) load(); }, 60000);
</script>
</body>
</html>
"""


def _lan_ip():
    """R4：探测本机局域网 IP——UDP connect 只做路由选择不实际发包，安全即时。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("223.5.5.5", 80))   # 阿里公共 DNS，仅用于选路
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="超脑工作台本地服务（M2 写通道）")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="127.0.0.1",
                    help="默认只绑本机回环；改 0.0.0.0 = 自担安全风险")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    # 启动前检查 registry 在位（首次运行的引导提示）
    if not os.path.exists(_REGISTRY_PATH):
        print(f"[workbench] 未找到组件注册表：{_REGISTRY_PATH}")
        print("[workbench] 请先运行 schedule_manager/sb_healthlite 所在技能的初始化流程。")
        return 1

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    open_url = f"http://127.0.0.1:{args.port}/"   # 打开地址与绑定地址解耦：0.0.0.0 不是可访问 URL
    print(f"[workbench] 超脑工作台已启动 → {open_url}（Ctrl+C 退出）")
    if args.host in ("0.0.0.0", "::"):
        ip = _lan_ip()
        if ip:
            print(f"[workbench] 局域网模式：手机连同一 Wi-Fi 打开 → http://{ip}:{args.port}/")
        else:
            print("[workbench] 局域网模式：未自动探测到局域网 IP，请 ipconfig 查看后手机访问。")
        print("[workbench] 注意：服务无鉴权，仅限可信家庭/办公网络，用完即关。")
    else:
        print(f"[workbench] 只绑定 {args.host}，局域网不可达；写操作仅限组件开关与立即运行")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(open_url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[workbench] 已退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
