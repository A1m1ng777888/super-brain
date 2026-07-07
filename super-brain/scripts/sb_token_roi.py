#!/usr/bin/env python3
"""
SuperBrain Token ROI Calculator v3.5.0
======================================
Quantifies how much each memory saves in token costs.
Based on existing statistics (access_count, memory size, compression ratio).

Metrics:
  - Per-memory token savings rate
  - Category-level savings breakdown
  - Cumulative system-level ROI
  - Net positive/negative flag per memory

Token model (approximate):
  - Raw storage: ~4 chars = 1 token
  - Context injection (without SB): full content injected each access
  - Compressed injection (with SB): ~25% of full content (summary format)
  - Savings per access = (full_size - compressed_size) * 0.25 tokens/char
  - Total savings = savings_per_access * access_count

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, get_timestamp

# Token estimation constants
CHARS_PER_TOKEN = 4.0  # ~4 chars per token (English+Chinese average)
COMPRESSION_RATIO = 0.25  # Compressed context is ~25% of full content
INJECTION_COST_PER_CHAR = 0.25  # tokens per character for injection
STORAGE_COST_PER_CHAR = 0.02  # tokens per character for on-disk storage (very low)


def estimate_tokens(text):
    """Estimate token count from text length."""
    if not text:
        return 0
    # Count Chinese chars (1 char = 1-2 tokens) vs English (4-5 chars = 1 token)
    chinese_cnt = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_cnt = len(text) - chinese_cnt
    return round(chinese_cnt * 1.5 + other_cnt / CHARS_PER_TOKEN)


def calc_memory_roi(memory):
    """
    Calculate ROI for a single memory.
    Returns dict with cost/benefit breakdown + actionable recommendation.
    """
    content = memory.get("content", "")
    access_count = memory.get("access_count", 0)
    category = memory.get("type", "unknown")
    confidence = memory.get("confidence", 0.5)

    # Token counts
    full_tokens = estimate_tokens(content)
    compressed_tokens = round(full_tokens * COMPRESSION_RATIO)

    # Costs
    storage_cost = round(full_tokens * STORAGE_COST_PER_CHAR, 2)

    # Benefits: each access saves the difference
    savings_per_access = full_tokens - compressed_tokens
    total_savings = savings_per_access * max(access_count, 1)

    # Net benefit
    net_benefit = total_savings - storage_cost
    roi_positive = net_benefit > 0

    # PM v3.5: actionable recommendation based on memory state
    recommendation = ""
    if roi_positive:
        if access_count >= 10:
            recommendation = "高价值记忆，保持活跃"
        elif access_count >= 3:
            recommendation = "正在产生价值，可继续复用"
        else:
            recommendation = "已产生正收益，增加访问可提升价值"
    else:
        if access_count == 0:
            recommendation = "从未被访问，建议归档或删除"
        elif storage_cost > 2.0:
            recommendation = "存储成本高但访问少，建议精简内容或归档"
        elif confidence < 0.7:
            recommendation = "ROI 为负且置信度低，建议删除或合并"
        else:
            recommendation = "访问不足，建议主动引用或归档"

    return {
        "id": memory.get("id", "unknown"),
        "category": category,
        "content_preview": content[:60],
        "full_tokens": full_tokens,
        "compressed_tokens": compressed_tokens,
        "savings_per_access": savings_per_access,
        "access_count": access_count,
        "total_savings": total_savings,
        "storage_cost": storage_cost,
        "net_benefit": net_benefit,
        "roi_positive": roi_positive,
        "confidence": confidence,
        "recommendation": recommendation
    }


def calc_token_roi(workspace=None, recent_days=None):
    """
    Calculate system-wide Token ROI.
    If recent_days is set, only count memories from the last N days.
    Returns summary + per-memory breakdown.
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]

    # v3.4.0+: filter by recent days
    if recent_days and recent_days > 0:
        from datetime import datetime, timedelta, timezone as tz
        cutoff = datetime.now(tz.utc) - timedelta(days=recent_days)
        active_recent = []
        for m in active:
            ts_str = m.get("timestamp", "")
            try:
                if "T" in ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.fromisoformat(ts_str + "T00:00:00+00:00")
                if ts >= cutoff:
                    active_recent.append(m)
            except (ValueError, TypeError):
                active_recent.append(m)  # include if can't parse
        active = active_recent

    if not active:
        return {
            "timestamp": get_timestamp(),
            "workspace": workspace or "default",
            "total_memories": 0,
            "total_savings": 0,
            "total_storage_cost": 0,
            "net_roi": 0,
            "roi_ratio": 0,
            "by_category": {},
            "top_savers": [],
            "negative_roi": [],
            "breakdown": []
        }

    breakdown = [calc_memory_roi(m) for m in active]

    # Aggregate
    total_savings = sum(b["total_savings"] for b in breakdown)
    total_storage = sum(b["storage_cost"] for b in breakdown)
    net_roi = total_savings - total_storage
    roi_ratio = round(total_savings / max(total_storage, 0.01), 1)

    # By category
    by_category = {}
    for b in breakdown:
        cat = b["category"]
        if cat not in by_category:
            by_category[cat] = {"count": 0, "total_savings": 0, "total_storage": 0, "net": 0}
        by_category[cat]["count"] += 1
        by_category[cat]["total_savings"] += b["total_savings"]
        by_category[cat]["total_storage"] += b["storage_cost"]
        by_category[cat]["net"] += b["net_benefit"]

    # Top savers (by net_benefit)
    sorted_by_benefit = sorted(breakdown, key=lambda x: x["net_benefit"], reverse=True)
    top_savers = sorted_by_benefit[:10]

    # Negative ROI memories
    negative = [b for b in breakdown if not b["roi_positive"]]

    return {
        "timestamp": get_timestamp(),
        "workspace": workspace or "default",
        "total_memories": len(active),
        "total_savings": round(total_savings, 1),
        "total_storage_cost": round(total_storage, 1),
        "net_roi": round(net_roi, 1),
        "roi_ratio": roi_ratio,
        "estimate_note": f"~{CHARS_PER_TOKEN:.0f}字符/Token, 压缩率{COMPRESSION_RATIO:.0%}",
        "by_category": by_category,
        "top_savers": [{
            "id": b["id"],
            "category": b["category"],
            "preview": b["content_preview"],
            "savings": b["total_savings"],
            "accesses": b["access_count"]
        } for b in top_savers],
        "negative_roi_count": len(negative),
        "negative_roi": [b for b in sorted(negative, key=lambda x: x["net_benefit"])],
        "breakdown": breakdown
    }


def calc_token_roi_trend(workspace=None, days=30):
    """
    v3.5.0: Compute daily ROI snapshots up to today.
    Returns list of {date, total_memories, net_roi, roi_ratio, total_savings}.
    Useful for trend charts in dashboards.
    """
    from datetime import datetime, timedelta, timezone as tz
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    now = datetime.now(tz.utc)
    trend = []

    for offset in range(days - 1, -1, -1):
        day = now - timedelta(days=offset)
        day_str = day.strftime("%Y-%m-%d")
        day_end = datetime(day.year, day.month, day.day, 23, 59, 59)

        # Include memories created on or before this day
        daily_memories = []
        for m in active:
            ts_str = m.get("timestamp", "")
            try:
                if "T" in ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.fromisoformat(ts_str + "T00:00:00")
                # Treat both timestamps as naive for fair comparison
                if ts.tzinfo:
                    ts = ts.replace(tzinfo=None)
                if ts <= day_end:
                    daily_memories.append(m)
            except (ValueError, TypeError):
                continue

        if not daily_memories:
            trend.append({
                "date": day_str,
                "total_memories": 0,
                "net_roi": 0,
                "roi_ratio": 0,
                "total_savings": 0
            })
            continue

        breakdown = [calc_memory_roi(m) for m in daily_memories]
        total_savings = sum(b["total_savings"] for b in breakdown)
        total_storage = sum(b["storage_cost"] for b in breakdown)
        net_roi = total_savings - total_storage
        roi_ratio = round(total_savings / max(total_storage, 0.01), 1)

        trend.append({
            "date": day_str,
            "total_memories": len(daily_memories),
            "net_roi": round(net_roi, 1),
            "roi_ratio": roi_ratio,
            "total_savings": round(total_savings, 1)
        })

    return trend


def get_token_roi_summary(workspace=None, recent_days=None):
    """Generate human-readable ROI summary."""
    data = calc_token_roi(workspace, recent_days=recent_days)

    lines = []
    lines.append("=" * 60)
    lines.append(f"  Token ROI 量化报告 — {data['workspace']}")
    lines.append("=" * 60)
    lines.append(f"  记忆总数: {data['total_memories']}")
    lines.append(f"  总节省: {data['total_savings']} tokens")
    lines.append(f"  存储成本: {data['total_storage_cost']} tokens")
    lines.append(f"  净收益: {data['net_roi']} tokens")
    lines.append(f"  ROI 比率: {data['roi_ratio']}x")
    lines.append(f"  估算说明: {data['estimate_note']}")
    lines.append("")

    if data["by_category"]:
        lines.append("  按类别:")
        for cat, stats in sorted(data["by_category"].items(), key=lambda x: x[1]["net"], reverse=True):
            lines.append(f"    {cat}: {stats['count']}条 | 净收益 {stats['net']:.0f} tokens")
        lines.append("")

    if data["top_savers"]:
        lines.append("  ROI Top-5:")
        for i, m in enumerate(data["top_savers"][:5], 1):
            lines.append(f"    {i}. [{m['category']}] {m['preview'][:40]}... ({m['savings']:.0f}tok)")
        lines.append("")

    if data["negative_roi_count"] > 0:
        lines.append(f"  ⚠️ {data['negative_roi_count']} 条记忆当前为负 ROI（访问少但存储成本高）")
        lines.append("    建议: 增加访问频率或降低存储置信度")

    return "\n".join(lines)


def get_roi_quickline(workspace=None, recent_days=None):
    """
    v3.4.0+: Generate a one-line ROI summary for dialog injection.
    Example: "过去7天新增12条记忆，净节省342 tokens（ROI 28.5x）"
    """
    data = calc_token_roi(workspace, recent_days=recent_days)
    mem_count = data["total_memories"]
    if mem_count == 0:
        return "暂无可量化的 Token 节省数据。"

    period = f"过去{recent_days}天" if recent_days else "累计"
    # Find top category
    top_cat = max(data["by_category"].items(), key=lambda x: x[1]["net"]) if data["by_category"] else (("未知", {"net": 0}),)
    return (
        f"{period}超脑管理了 {mem_count} 条记忆，净节省 {data['net_roi']:.0f} tokens"
        f"（ROI {data['roi_ratio']}x），主要贡献来自 {top_cat[0]} 类"
        f"（{top_cat[1]['net']:.0f} tokens）。"
    )


def generate_dashboard_html(workspace=None, recent_days=None, output_path="token-roi-dashboard.html", trend_days=30):
    """
    v3.5.0: Generate an interactive HTML dashboard for Token ROI visualization.
    Includes trend chart and negative ROI diagnostics.
    Returns the output path on success, None on failure.
    """
    data = calc_token_roi(workspace, recent_days=recent_days)
    if data["total_memories"] == 0:
        return None

    trend = calc_token_roi_trend(workspace, days=trend_days)

    # Prepare data for charts
    cat_data = data["by_category"]
    cat_labels = json.dumps([k for k in sorted(cat_data.keys())])
    cat_values = json.dumps([round(cat_data[k]["net"]) for k in sorted(cat_data.keys())])
    cat_counts = json.dumps([cat_data[k]["count"] for k in sorted(cat_data.keys())])
    cat_colors = json.dumps(["#1d9e75", "#7f77dd", "#378add", "#ef9f27", "#d85a30"][:len(cat_data)])

    top_list = data.get("top_savers", [])
    top_labels = json.dumps([m["preview"][:14] + "…" for m in top_list])
    top_values = json.dumps([m["savings"] for m in top_list])

    trend_dates = json.dumps([t["date"][5:] for t in trend])  # MM-DD
    trend_mems = json.dumps([t["total_memories"] for t in trend])
    trend_net = json.dumps([t["net_roi"] for t in trend])
    trend_ratio = json.dumps([t["roi_ratio"] for t in trend])

    # Build negative ROI panel
    negative = data.get("negative_roi", [])
    negative_html = ""
    if negative:
        rows = []
        for m in negative[:10]:
            rows.append(
                f"<tr><td>{m['category']}</td><td title='{m['content_preview']}'>{m['content_preview'][:40]}…</td>"
                f"<td>{m['access_count']}</td><td>{m['net_benefit']:.1f}</td>"
                f"<td class='rec'>{m['recommendation']}</td></tr>"
            )
        negative_html = (
            "<div class='card full' style='margin-bottom:20px;border-color:#d85a30'>"
            "<h3>负 ROI 诊断</h3>"
            "<p style='font-size:12px;color:#888890;margin-bottom:10px'>"
            "以下记忆存储成本高于节省收益，建议按推荐动作处理：</p>"
            "<table class='diag'><thead><tr><th>类型</th><th>内容</th><th>访问</th>"
            "<th>净收益</th><th>建议</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div>"
        )
    else:
        negative_html = (
            "<div class='card full' style='margin-bottom:20px;'>"
            "<h3>负 ROI 诊断</h3>"
            "<p style='font-size:13px;color:#1d9e75'>当前所有记忆均为正收益，没有负 ROI 项目。</p></div>"
        )

    total_mem = data["total_memories"]
    net_roi_val = data["net_roi"]
    roi_ratio_val = data["roi_ratio"]
    storage_val = data["total_storage_cost"]
    total_savings_val = round(data["total_savings"], 1)
    negative_count = data["negative_roi_count"]

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>超脑 Token ROI 看板</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0e0e10;color:#e8e8ea;padding:24px;max-width:1100px;margin:0 auto}}
  h1{{font-size:20px;font-weight:500;margin-bottom:4px;letter-spacing:-0.02em}}
  .sub{{color:#888890;font-size:13px;margin-bottom:24px}}
  .grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px}}
  .metric{{background:#18181b;border:0.5px solid #2a2a2e;border-radius:10px;padding:14px 16px}}
  .metric .label{{font-size:12px;color:#888890;margin-bottom:4px}}
  .metric .value{{font-size:22px;font-weight:500;letter-spacing:-0.01em}}
  .metric .note{{font-size:11px;color:#888890;margin-top:2px}}
  .teal{{color:#1d9e75}}.coral{{color:#d85a30}}.blue{{color:#378add}}.amber{{color:#ef9f27}}
  .chart-row{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px}}
  .card{{background:#18181b;border:0.5px solid #2a2a2e;border-radius:10px;padding:16px}}
  .card h3{{font-size:13px;font-weight:500;color:#888890;margin-bottom:10px}}
  .full{{grid-column:1/-1}}
  .chart-wrap{{position:relative;height:240px}}
  .chart-wrap.tall{{height:300px}}
  .legend{{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:#888890;margin-top:8px}}
  .legend span{{display:flex;align-items:center;gap:5px}}
  .dot{{width:8px;height:8px;border-radius:2px;display:inline-block}}
  table.diag{{width:100%;border-collapse:collapse;font-size:12px}}
  table.diag th{{text-align:left;padding:8px 4px;border-bottom:0.5px solid #2a2a2e;color:#888890;font-weight:500}}
  table.diag td{{padding:8px 4px;border-bottom:0.5px solid #2a2a2e;color:#e8e8ea}}
  table.diag td.rec{{color:#ef9f27}}
  @media(max-width:700px){{.grid-4{{grid-template-columns:repeat(2,1fr)}}.chart-row{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>Token ROI 看板</h1>
<p class="sub">超脑 · {data["timestamp"]} · {total_mem} 条活跃记忆 · 负 ROI: {negative_count} 条 · 趋势周期 {trend_days} 天</p>

<div class="grid-4">
  <div class="metric"><div class="label">记忆总数</div><div class="value blue">{total_mem}</div><div class="note">条活跃记忆</div></div>
  <div class="metric"><div class="label">净节省 Token</div><div class="value teal">{net_roi_val:,.0f}</div><div class="note">累计净收益</div></div>
  <div class="metric"><div class="label">ROI 比率</div><div class="value amber">{roi_ratio_val}x</div><div class="note">总节省 / 存储成本</div></div>
  <div class="metric"><div class="label">存储成本</div><div class="value coral">{storage_val:.0f}</div><div class="note">tok（{storage_val/max(total_savings_val,1)*100:.1f}% 总节省）</div></div>
</div>

<div class="chart-row">
  <div class="card full">
    <h3>{trend_days} 天 ROI 趋势</h3>
    <div class="chart-wrap"><canvas id="trendChart" role="img" aria-label="Line chart of ROI trend over time"></canvas></div>
  </div>
</div>

<div class="chart-row">
  <div class="card">
    <h3>各类型净节省 Token</h3>
    <div class="chart-wrap"><canvas id="catChart" role="img" aria-label="Bar chart of token savings by category"></canvas></div>
  </div>
  <div class="card">
    <h3>记忆类型分布</h3>
    <div class="chart-wrap"><canvas id="typeChart" role="img" aria-label="Donut chart of memory type distribution"></canvas></div>
  </div>
</div>

{negative_html}

<div class="chart-row">
  <div class="card full">
    <h3>Top 节省记忆</h3>
    <div class="chart-wrap tall"><canvas id="topChart" role="img" aria-label="Horizontal bar of top saving memories"></canvas></div>
  </div>
</div>

<script>
const catLabels={cat_labels};const catValues={cat_values};const catCounts={cat_counts};const catColors={cat_colors};
const topLabels={top_labels};const topValues={top_values};
const trendDates={trend_dates};const trendMems={trend_mems};const trendNet={trend_net};const trendRatio={trend_ratio};

new Chart(document.getElementById('trendChart'),{{type:'line',data:{{labels:trendDates,datasets:[{{label:'净节省(tok)',data:trendNet,borderColor:'#1d9e75',backgroundColor:'rgba(29,158,117,0.15)',fill:true,tension:0.3,pointRadius:2}},{{label:'记忆数',data:trendMems,borderColor:'#7f77dd',backgroundColor:'transparent',borderDash:[4,4],yAxisID:'y1',tension:0.3,pointRadius:2}}]}},options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{display:true,labels:{{color:'#888890',font:{{size:11}}}}}}}},scales:{{x:{{ticks:{{color:'#888890',font:{{size:10}}}},grid:{{color:'rgba(255,255,255,0.05)'}}}},y:{{ticks:{{color:'#1d9e75',font:{{size:10}}}},grid:{{color:'rgba(255,255,255,0.05)'}}}},y1:{{position:'right',ticks:{{color:'#7f77dd',font:{{size:10}}}},grid:{{display:false}}}}}}}});
new Chart(document.getElementById('catChart'),{{type:'bar',data:{{labels:catLabels,datasets:[{{label:'净节省(tok)',data:catValues,backgroundColor:catColors.map(c=>c+'cc'),borderColor:catColors,borderWidth:0.5,borderRadius:4}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:'#888890',font:{{size:11}}}},grid:{{color:'rgba(255,255,255,0.05)'}}}},y:{{ticks:{{color:'#888890',font:{{size:11}},callback:v=>v>=1000?(v/1000).toFixed(0)+'k':v}},grid:{{color:'rgba(255,255,255,0.05)'}}}}}}}});
new Chart(document.getElementById('typeChart'),{{type:'doughnut',data:{{labels:catLabels.map((l,i)=>l+' ('+catCounts[i]+')'),datasets:[{{data:catCounts,backgroundColor:catColors,borderColor:'#18181b',borderWidth:2}}]}},options:{{responsive:true,maintainAspectRatio:false,cutout:'62%',plugins:{{legend:{{display:false}}}}}}}});
new Chart(document.getElementById('topChart'),{{type:'bar',data:{{labels:topLabels,datasets:[{{label:'节省(tok)',data:topValues,backgroundColor:'rgba(55,138,221,0.7)',borderColor:'transparent',borderRadius:3}}]}},options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:'#888890',font:{{size:10}}}},grid:{{color:'rgba(255,255,255,0.05)'}}}},y:{{ticks:{{color:'#e8e8ea',font:{{size:10}}}},grid:{{display:false}}}}}}}});
</script>
</body>
</html>'''

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_path
    except (OSError, IOError) as e:
        print(f"[SB] Dashboard write failed: {e}", file=sys.stderr)
        return None
