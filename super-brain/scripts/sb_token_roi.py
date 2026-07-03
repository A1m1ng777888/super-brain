#!/usr/bin/env python3
"""
SuperBrain Token ROI Calculator v3.4.0
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
    Returns dict with cost/benefit breakdown.
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
        "roi_positive": net_benefit > 0,
        "confidence": confidence
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
        "breakdown": breakdown
    }


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
