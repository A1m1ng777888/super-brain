#!/usr/bin/env python3
"""
超脑健康看板生成器（方向② 可视化工作台 · 第一块增量）
======================================================
本副本为 sb_workbench 面板内嵌版（sb_dashboard.py）：默认输出到
super-brain 数据目录 dashboard.html，由工作台本地服务直接托管；
生成逻辑与 superbrain-bench/build_dashboard.py 保持同步。
背景（2026-08-30 基线报告 §18.5）：超脑的结构性 bug（access_count 断裂、
重复只告警不阻断、gating 洪水、图谱空转）全是「藏在地里靠撞见才发现」。
本工具把健康状态持续可见：读取 workspace 数据，渲染单文件离线 HTML 看板。

设计约束：
  - **严格只读**：不调 get_active_workspace / get_status（会触发重门控写盘），
    全部统计用只读路径计算
  - 单文件自包含：数据以 JSON 内嵌，零外部依赖（本地优先原则）
  - 视觉遵循超脑品牌：琥珀 accent on 暖白 #faf9f6
  - 可反复运行：`python build_dashboard.py` 重新生成

用法：
  python build_dashboard.py                    # 默认 workspace
  python build_dashboard.py --output out.html  # 指定输出路径

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import json
import math
import argparse
from collections import Counter, defaultdict
from datetime import datetime

SCRIPTS = os.path.join(os.path.expanduser("~"),
                       ".workbuddy", "skills", "super-brain", "scripts")
sys.path.insert(0, SCRIPTS)

from sb_core import (  # noqa: E402
    DEFAULT_DATA_DIR, read_memories, read_graph, get_workspace_dir)


# ---------------------------------------------------------------------------
# 数据计算（全部只读）
# ---------------------------------------------------------------------------

def compute_stats(workspace=None):
    mems = read_memories(workspace)
    graph = read_graph(workspace)
    act = [m for m in mems if m.get("status") == "active"]
    arch = [m for m in mems if m.get("status") != "active"]

    # --- 概览 ---
    confs = [float(m.get("confidence", 0.5)) for m in act]
    overview = {
        "total": len(mems),
        "active": len(act),
        "archived": len(arch),
        "avg_confidence": round(sum(confs) / len(confs), 3) if confs else 0,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # --- 门控（只读计算，不触发重门控）---
    from sb_gating import get_threshold, compute_salience, DEFAULT_CAP
    threshold = get_threshold(workspace)
    meta_path = os.path.join(get_workspace_dir(workspace), "meta.json")
    meta = {}
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8"))
    mode = "manual" if meta.get("gating_threshold") is not None else "auto"
    candidates = [m for m in act if not m.get("gating_override")]
    promoted = [m for m in act if m.get("workspace_promoted")]
    overrides = Counter(m.get("gating_override") for m in act)
    sal_of = lambda m: compute_salience(m, workspace)  # noqa: E731
    top_promoted = sorted(promoted, key=sal_of, reverse=True)[:20]
    gating = {
        "mode": mode,
        "threshold": round(threshold, 4),
        "cap": DEFAULT_CAP,
        "candidates": len(candidates),
        "promoted": len(promoted),
        "ratio": round(len(promoted) / max(len(candidates), 1), 3),
        "override_demote": overrides.get("demote", 0),
        "top": [
            {"type": m.get("type"), "entity": m.get("entity"),
             "salience": round(sal_of(m), 3), "content": m.get("content", "")[:60]}
            for m in top_promoted
        ],
    }

    # --- 图谱 ---
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", {})
    degree = Counter()
    name_of = {nid: n.get("name", "?") for nid, n in nodes.items()}
    for e in edges.values():
        degree[e["source"]] += 1
        degree[e["target"]] += 1
    hubs = sorted(((name_of.get(nid, "?"), d) for nid, d in degree.items()),
                  key=lambda t: -t[1])[:12]
    connected = set(degree)
    orphans = [nid for nid in nodes if nid not in connected]
    graph_data = {
        "nodes": [{"id": nid, "name": name_of[nid], "degree": degree.get(nid, 0)}
                  for nid in nodes],
        "edges": [{"s": e["source"], "t": e["target"], "w": round(float(e.get("weight", 1)), 3)}
                  for e in edges.values()],
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "orphans": len(orphans),
        "hubs": [{"name": n, "degree": d} for n, d in hubs],
    }

    # --- 记忆体检 ---
    lens = sorted(len(m.get("content", "")) for m in act)
    n = len(lens)
    pct = lambda p: lens[int(n * p)] if n else 0  # noqa: E731
    entity_cnt = Counter((m.get("entity") or "").strip() for m in act
                         if (m.get("entity") or "").strip())
    type_cnt = Counter(m.get("type") for m in act)
    month_cnt = Counter(m.get("timestamp", "")[:7] for m in act)
    verbose = [l for l in lens if l > 200]
    hygiene = {
        "len_p50": pct(0.5), "len_p90": pct(0.9), "len_max": lens[-1] if lens else 0,
        "verbose_count": len(verbose),
        "verbose_share": round(len(verbose) / max(n, 1), 3),
        "general_count": entity_cnt.get("general", 0),
        "general_share": round(entity_cnt.get("general", 0) / max(n, 1), 3),
        "entity_total": len(entity_cnt),
        "top_entities": [{"name": e, "count": c}
                         for e, c in entity_cnt.most_common(12)],
        "types": [{"name": t, "count": c} for t, c in type_cnt.most_common()],
        "months": [{"month": mo, "count": c}
                   for mo, c in sorted(month_cnt.items())],
    }

    # --- 审计 ---
    audit_path = os.path.join(get_workspace_dir(workspace), "audit_log.json")
    audit = {"actions": {}, "recent": []}
    if os.path.exists(audit_path):
        log = json.load(open(audit_path, encoding="utf-8"))
        entries = log.get("entries", [])
        audit["actions"] = dict(Counter(e.get("action") for e in entries))
        audit["recent"] = [
            {"ts": e.get("timestamp", "")[:16], "action": e.get("action"),
             "target": (e.get("target_id") or "")[:24],
             "reason": (e.get("reason") or "")[:70]}
            for e in entries[-10:]
        ]

    # --- 健康红绿灯（等价 selfcheck 关键项的只读复算）---
    checks = []
    checks.append(("门控洪水保护", "healthy" if len(promoted) <= DEFAULT_CAP else "critical",
                   f"{len(promoted)} / cap {DEFAULT_CAP}（候选池 {len(candidates)}，比例 {gating['ratio']:.1%}）"))
    checks.append(("图谱连通", "healthy" if graph_data["total_nodes"] > 50 else "warning",
                   f"{graph_data['total_nodes']} 节点 / {graph_data['total_edges']} 边 / {graph_data['orphans']} 孤立"))
    checks.append(("general 占比", "healthy" if hygiene["general_share"] < 0.12 else "warning",
                   f"{hygiene['general_count']} 条（{hygiene['general_share']:.1%}）"))
    checks.append(("无审计 override", "healthy" if overrides.get("demote", 0) == 0 else "warning",
                   f"{overrides.get('demote', 0)} 条 demote（无审计来源，待拍板清除）"))
    checks.append(("冗长记忆占比", "healthy" if hygiene["verbose_share"] < 0.5 else "warning",
                   f">200 字 {hygiene['verbose_count']} 条（{hygiene['verbose_share']:.1%}）"))
    health = [{"name": nm, "status": st, "detail": dt} for nm, st, dt in checks]

    return {"overview": overview, "gating": gating, "graph": graph_data,
            "hygiene": hygiene, "audit": audit, "health": health}


# ---------------------------------------------------------------------------
# HTML 模板（零依赖单文件；__DATA__ 占位替换）
# ---------------------------------------------------------------------------

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>超脑 · 健康看板</title>
<style>
  :root {
    --bg: #faf9f6; --card: #ffffff; --ink: #1c1917; --ink-2: #78716c;
    --line: #e7e5e4; --amber: #d97706; --amber-soft: #fef3c7;
    --ok: #15803d; --warn: #b45309; --crit: #b91c1c;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--ink);
         font: 14px/1.6 -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
         padding: 32px 4vw; max-width: 1200px; margin: 0 auto; }
  header { display: flex; align-items: baseline; gap: 16px; margin-bottom: 24px;
           flex-wrap: wrap; }
  h1 { font-size: 22px; font-weight: 700; letter-spacing: .5px; }
  h1 .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%;
            background: var(--amber); margin-right: 10px; }
  .sub { color: var(--ink-2); font-size: 13px; }
  .grid { display: grid; gap: 16px; }
  .kpi { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin-bottom: 16px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
          padding: 18px 20px; }
  .kpi .num { font-size: 26px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .kpi .lbl { color: var(--ink-2); font-size: 12px; margin-top: 2px; }
  .kpi .num.accent { color: var(--amber); }
  h2 { font-size: 15px; font-weight: 600; margin-bottom: 12px; display: flex;
       align-items: center; gap: 8px; }
  h2::before { content: ""; width: 3px; height: 14px; background: var(--amber);
               border-radius: 2px; }
  .stack { grid-template-columns: 1fr; }
  .two-col { grid-template-columns: 3fr 2fr; }
  @media (max-width: 860px) { .two-col { grid-template-columns: 1fr; } }
  .check { display: flex; align-items: flex-start; gap: 10px; padding: 8px 0;
           border-bottom: 1px solid var(--line); }
  .check:last-child { border-bottom: none; }
  .light { width: 9px; height: 9px; border-radius: 50%; margin-top: 6px; flex-shrink: 0; }
  .light.healthy { background: var(--ok); }
  .light.warning { background: var(--warn); }
  .light.critical { background: var(--crit); }
  .check .nm { font-weight: 600; min-width: 110px; }
  .check .dt { color: var(--ink-2); font-size: 13px; }
  .bar-row { display: flex; align-items: center; gap: 10px; margin: 5px 0; font-size: 13px; }
  .bar-row .bl { width: 130px; text-align: right; color: var(--ink-2);
                 white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar-row .tr { flex: 1; background: var(--line); border-radius: 4px; height: 14px; }
  .bar-row .fl { height: 100%; background: var(--amber); border-radius: 4px;
                 min-width: 2px; }
  .bar-row .bv { width: 52px; font-variant-numeric: tabular-nums; color: var(--ink-2); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; color: var(--ink-2); font-weight: 500; padding: 6px 8px;
       border-bottom: 1px solid var(--line); font-size: 12px; }
  td { padding: 6px 8px; border-bottom: 1px solid var(--line); }
  tr:last-child td { border-bottom: none; }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 10px;
         font-size: 12px; background: var(--amber-soft); color: var(--amber); }
  canvas { width: 100%; height: 420px; display: block; }
  .hint { color: var(--ink-2); font-size: 12px; margin-top: 6px; }
  footer { margin-top: 28px; color: var(--ink-2); font-size: 12px;
           text-align: center; }
</style>
</head>
<body>
<header>
  <h1><span class="dot"></span>超脑 · 健康看板</h1>
  <span class="sub" id="meta"></span>
</header>

<div class="grid kpi" id="kpis"></div>

<div class="grid two-col">
  <div class="card">
    <h2>健康红绿灯</h2>
    <div id="health"></div>
  </div>
  <div class="card">
    <h2>门控看板</h2>
    <div id="gating"></div>
  </div>
</div>

<div class="card" style="margin-top:16px">
  <h2>知识图谱</h2>
  <canvas id="graph"></canvas>
  <div class="hint" id="graph-hint">拖拽节点可固定位置；滚轮缩放；琥珀色大小=连接度。</div>
</div>

<div class="grid two-col" style="margin-top:16px">
  <div class="card">
    <h2>实体簇 Top 12</h2>
    <div id="entities"></div>
  </div>
  <div class="card">
    <h2>记忆类型 / 月度增长</h2>
    <div id="types"></div>
    <div id="months" style="margin-top:14px"></div>
  </div>
</div>

<div class="grid two-col" style="margin-top:16px">
  <div class="card">
    <h2>工作空间 · 晋升 Top 20</h2>
    <table id="promoted"><thead><tr>
      <th>类型</th><th>实体</th><th>salience</th><th>内容</th>
    </tr></thead><tbody></tbody></table>
  </div>
  <div class="card">
    <h2>审计动态</h2>
    <div id="audit-actions" style="margin-bottom:10px"></div>
    <table id="audit"><thead><tr>
      <th>时间</th><th>动作</th><th>说明</th>
    </tr></thead><tbody></tbody></table>
  </div>
</div>

<footer>超脑健康看板 · 数据为生成时快照 · 由 build_dashboard.py 离线生成</footer>

<script>
const D = __DATA__;
const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};

// --- 头部与 KPI ---
$("#meta").textContent = D.overview.generated_at + " · active " +
  D.overview.active + " · 置信度均值 " + D.overview.avg_confidence;
const kpis = [
  [D.overview.active, "active 记忆", ""],
  [D.gating.promoted + " / " + D.gating.cap, "工作空间晋升", "accent"],
  [(D.gating.ratio * 100).toFixed(1) + "%", "候选池比例", ""],
  [D.graph.total_nodes + " / " + D.graph.total_edges, "图谱节点 / 边", ""],
  [D.hygiene.general_share * 100 > 0 ? (D.hygiene.general_share * 100).toFixed(1) + "%" : "0%",
   "general 占比", ""],
  [D.hygiene.len_p50, "长度中位(字)", ""],
];
kpis.forEach(([num, lbl, cls]) => {
  const c = el("div", "card kpi");
  c.appendChild(el("div", "num " + cls, num));
  c.appendChild(el("div", "lbl", lbl));
  $("#kpis").appendChild(c);
});

// --- 健康红绿灯 ---
D.health.forEach(h => {
  const row = el("div", "check");
  row.appendChild(el("span", "light " + h.status));
  row.appendChild(el("span", "nm", h.name));
  row.appendChild(el("span", "dt", h.detail));
  $("#health").appendChild(row);
});

// --- 门控 ---
const g = D.gating;
$("#gating").innerHTML =
  "<div class='bar-row'><span class='bl'>模式</span><span class='tag'>" +
  (g.mode === "auto" ? "自动 · 相对门控" : "手动 · 阈值 " + g.threshold) + "</span></div>" +
  "<div class='bar-row'><span class='bl'>阈值(动态)</span><span class='bv'>" +
  g.threshold + "</span></div>" +
  "<div class='bar-row'><span class='bl'>候选池</span><span class='bv'>" +
  g.candidates + " 条</span></div>" +
  "<div class='bar-row'><span class='bl'>晋升 / cap</span><div class='tr'><div class='fl' style='width:" +
  Math.min(100, g.promoted / g.cap * 100) + "%'></div></div><span class='bv'>" +
  g.promoted + " / " + g.cap + "</span></div>" +
  "<div class='bar-row'><span class='bl'>demote override</span><span class='bv'>" +
  g.override_demote + " 条</span></div>";

// --- 实体簇 / 类型 / 月度 ---
function barChart(container, rows, maxOverride) {
  const max = maxOverride || Math.max(...rows.map(r => r.count));
  rows.forEach(r => {
    const row = el("div", "bar-row");
    row.appendChild(el("span", "bl", r.name));
    const tr = el("div", "tr");
    tr.appendChild(el("div", "fl")).style.width = (r.count / max * 100) + "%";
    row.appendChild(tr);
    row.appendChild(el("span", "bv", r.count));
    $(container).appendChild(row);
  });
}
barChart("#entities", D.hygiene.top_entities);
barChart("#types", D.hygiene.types);
barChart("#months", D.hygiene.months);

// --- 晋升 Top20 ---
D.gating.top.forEach(t => {
  const tr = document.createElement("tr");
  tr.innerHTML = "<td><span class='tag'>" + t.type + "</span></td><td>" +
    t.entity + "</td><td>" + t.salience + "</td><td style='color:var(--ink-2)'>" +
    t.content + "</td>";
  $("#promoted tbody").appendChild(tr);
});

// --- 审计 ---
const acts = Object.entries(D.audit.actions);
if (acts.length) {
  $("#audit-actions").innerHTML = acts.map(([a, c]) =>
    "<span class='tag' style='margin-right:8px'>" + a + " × " + c + "</span>").join("");
}
D.audit.recent.slice().reverse().forEach(e => {
  const tr = document.createElement("tr");
  tr.innerHTML = "<td style='white-space:nowrap;color:var(--ink-2)'>" + e.ts +
    "</td><td><span class='tag'>" + e.action + "</span></td><td style='color:var(--ink-2)'>" +
    e.reason + "</td>";
  $("#audit tbody").appendChild(tr);
});

// --- 力导向图（canvas，零依赖）---
(function () {
  const cv = $("#graph"), ctx = cv.getContext("2d");
  let W, H;
  function resize() {
    W = cv.width = cv.clientWidth * devicePixelRatio;
    H = cv.height = cv.clientHeight * devicePixelRatio;
  }
  resize(); addEventListener("resize", resize);

  const nodes = D.graph.nodes.map(n => ({
    id: n.id, name: n.name, deg: n.degree,
    x: 0, y: 0, vx: 0, vy: 0, fixed: false,
  }));
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const es = D.graph.edges.map(e => ({s: byId[e.s], t: byId[e.t], w: e.w}))
    .filter(e => e.s && e.t);
  const maxDeg = Math.max(1, ...nodes.map(n => n.deg));
  nodes.forEach((n, i) => {
    const a = 2 * Math.PI * i / nodes.length;
    n.x = Math.cos(a) * 200 + (Math.random() - .5) * 40;
    n.y = Math.sin(a) * 160 + (Math.random() - .5) * 40;
  });

  let scale = 1, panX = 0, panY = 0, hover = null;
  function r(n, dpr) { return (2 + 7 * Math.sqrt(n.deg / maxDeg)) * dpr; }

  let sim = 0;
  function step() {
    // 斥力
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        let d2 = dx * dx + dy * dy || 1;
        const f = 2600 / d2;
        const d = Math.sqrt(d2);
        dx /= d; dy /= d;
        a.vx += dx * f; a.vy += dy * f;
        b.vx -= dx * f; b.vy -= dy * f;
      }
    }
    // 引力
    es.forEach(e => {
      let dx = e.t.x - e.s.x, dy = e.t.y - e.s.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const f = (d - 70) * 0.012;
      dx /= d; dy /= d;
      e.s.vx += dx * f * d; e.s.vy += dy * f * d;
      e.t.vx -= dx * f * d; e.t.vy -= dy * f * d;
    });
    nodes.forEach(n => {
      if (n.fixed) { n.vx = n.vy = 0; return; }
      n.vx *= 0.82; n.vy *= 0.82;
      n.x += Math.max(-8, Math.min(8, n.vx));
      n.y += Math.max(-8, Math.min(8, n.vy));
    });
    if (++sim < 400) requestAnimationFrame(step);
    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    ctx.translate(W / 2 + panX, H / 2 + panY);
    ctx.scale(scale, scale);
    // 边
    es.forEach(e => {
      const hot = hover && (e.s === hover || e.t === hover);
      ctx.strokeStyle = hot ? "rgba(217,119,6,.85)" : "rgba(120,113,108,.18)";
      ctx.lineWidth = hot ? 1.6 : .7;
      ctx.beginPath(); ctx.moveTo(e.s.x, e.s.y); ctx.lineTo(e.t.x, e.t.y); ctx.stroke();
    });
    // 点
    nodes.forEach(n => {
      const hot = hover && (n === hover || es.some(e =>
        (e.s === hover && e.t === n) || (e.t === hover && e.s === n)));
      ctx.beginPath();
      ctx.arc(n.x, n.y, r(n, 1), 0, 7);
      ctx.fillStyle = hot ? "#d97706" : (hover && hover !== n ? "rgba(197,183,166,.5)" : "#a1662a");
      ctx.fill();
      if (n.deg >= 6 || n === hover || hot) {
        ctx.fillStyle = "#1c1917";
        ctx.font = "11px sans-serif";
        ctx.fillText(n.name, n.x + r(n, 1) + 3, n.y + 4);
      }
    });
    ctx.restore();
  }

  function pick(mx, my) {
    const x = (mx - W / 2 - panX) / scale, y = (my - H / 2 - panY) / scale;
    let best = null, bd = 1e9;
    nodes.forEach(n => {
      const d = (n.x - x) ** 2 + (n.y - y) ** 2;
      if (d < bd && d < (r(n, 1) + 6) ** 2) { bd = d; best = n; }
    });
    return best;
  }
  let drag = null, moved = false;
  cv.addEventListener("pointerdown", e => {
    const b = cv.getBoundingClientRect();
    const n = pick((e.clientX - b.left) * devicePixelRatio,
                   (e.clientY - b.top) * devicePixelRatio);
    drag = n; moved = false;
    if (n) { n.fixed = true; cv.setPointerCapture(e.pointerId); }
  });
  cv.addEventListener("pointermove", e => {
    const b = cv.getBoundingClientRect();
    const mx = (e.clientX - b.left) * devicePixelRatio;
    const my = (e.clientY - b.top) * devicePixelRatio;
    if (drag) {
      drag.x = (mx - W / 2 - panX) / scale;
      drag.y = (my - H / 2 - panY) / scale;
      moved = true; sim = Math.min(sim, 390);
      draw();
    } else {
      hover = pick(mx, my);
      cv.style.cursor = hover ? "pointer" : "default";
      draw();
      $("#graph-hint").textContent = hover
        ? hover.name + " · 度 " + hover.deg
        : "拖拽节点可固定位置；滚轮缩放；琥珀色大小=连接度。";
    }
  });
  cv.addEventListener("pointerup", () => { drag = null; });
  cv.addEventListener("wheel", e => {
    e.preventDefault();
    scale *= e.deltaY < 0 ? 1.12 : 0.89;
    scale = Math.max(.3, Math.min(4, scale));
    draw();
  }, { passive: false });
  step();
})();
</script>
</body>
</html>
"""


def render(stats):
    return TEMPLATE.replace("__DATA__", json.dumps(stats, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description="超脑健康看板生成器（只读）")
    ap.add_argument("--output", default=None, help="输出 HTML 路径")
    ap.add_argument("--workspace", default=None, help="workspace 名（默认当前）")
    args = ap.parse_args()

    stats = compute_stats(args.workspace)
    # 工作台内嵌版：默认输出到 super-brain 数据目录（sb_workbench 服务同源读取）
    out = args.output or os.path.join(DEFAULT_DATA_DIR, "dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(stats))
    size_kb = os.path.getsize(out) / 1024
    print(f"看板已生成: {out} ({size_kb:.0f} KB)")
    print(f"数据快照: active={stats['overview']['active']}, "
          f"promoted={stats['gating']['promoted']}/{stats['gating']['cap']}, "
          f"图={stats['graph']['total_nodes']}节点/{stats['graph']['total_edges']}边")


if __name__ == "__main__":
    main()
