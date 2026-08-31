#!/usr/bin/env python3
"""
SuperBrain Forgetting Engine v1.0.0 — 遗忘治理模块
==================================================
遗忘优先级 = 规模因子 S × (1 - 活跃度因子 A) × 记忆衰减因子 D

设计来源：
- 2026-08-11 深度研究「潜意识·Subconscious」后借鉴其遗忘曲线概念，
  但检索算法保持超脑原生（实验 1 证明中文场景不能退回标签匹配）。
- 真实数据校准：某展示型工作空间(174条/39天不活跃)、某业务型工作空间(85条/22天不活跃)
  应落 dormant，规模大但不活跃 = 最高遗忘收益。

三层档位：
- active  (A >= 0.40)：正常衰减，召回权重 1.0
- warm    (0.15 <= A < 0.40)：轻微降权，召回权重 0.8
- dormant (A < 0.15)：整体降权，召回权重 0.5 + gating demote（实验型大项目落此）

软切原则：dormant 记忆仍参与检索（不硬排除），仅降权——实验型项目"突然被想起"
时仍能召回，只是排后面。pinned/身份类记忆永远豁免（权重 1.0）。

纯标准库，零新存储：全部基于记忆已有字段
(last_accessed / access_count / timestamp / gating_override / status)。

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Optional

# ─────────────────────────────────────────────
# 权重系数（可调）
# ─────────────────────────────────────────────
W_LAST_ACCESS = 0.5        # 最后访问时间权重（活跃度的主信号）
W_ACCESS_FREQ = 0.3        # 平均访问频率权重
W_UPDATE_RECENCY = 0.2     # 最后更新时效权重
TAU_ACCESS_DAYS = 30       # 访问时效衰减半衰期（天）
TAU_UPDATE_DAYS = 60       # 更新时效衰减半衰期（天）
K_ACCESS_FREQ = 10         # 访问频率归一化除数

DORMANT_DAYS = 45          # 项目最后访问中位数超过 45 天 → 时间分归零（dormant 界）
                           # 校准依据（2026-08-11 真实数据）：
                           #   某长期未访问工作空间 last_accessed 34-46 天 → warm/dormant 交界
                           #   某高频工作空间 活跃至今 → active
ACTIVE_DAYS = 14           # 项目最后访问中位数 <= 14 天 → 时间分满分

TIER_ACTIVE_MIN = 0.40     # A >= 0.40 → active
TIER_WARM_MIN = 0.15       # 0.15 <= A < 0.40 → warm；A < 0.15 → dormant

WEIGHT_DORMANT = 0.5       # dormant 记忆召回降权系数（软切，不排除）
WEIGHT_WARM = 0.8          # warm 记忆召回降权系数

DECAY_NEVER_ACCESSED = 2.0  # 从未被访问的记忆：遗忘衰减因子
DECAY_RECENTLY_ACCESSED = 1.5  # 30 天内被访问过：次高衰减因子
DECAY_NORMAL = 1.0         # 正常衰减因子

# 候选阈值（scan/apply 用）
CANDIDATE_PRIORITY_MIN = 0.05  # warm 高风险项目进候选的报告阈值

# 豁免实体：身份/护栏类记忆永不衰减（entity 命中即豁免）
EXEMPT_ENTITIES = {
    "砚", "user", "潜进", "super-brain", "超脑", "编码护栏", "工作原则",
}


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────
def _parse_date(ts: Optional[str]) -> Optional[str]:
    """解析时间戳为 YYYY-MM-DD，非法返回 None（不误判）。"""
    if not ts:
        return None
    try:
        return str(ts)[:10]
    except Exception:
        return None


def _days_since(ts: Optional[str]) -> Optional[int]:
    """距今天数；无法解析返回 None。"""
    d = _parse_date(ts)
    if not d:
        return None
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        return None
    today = datetime.now()
    return max(0, (today - dt).days)


def _project_of(mem: dict) -> str:
    """记忆的项目归属：entity 优先，无则 general。"""
    e = (mem.get("entity") or "").strip()
    return e if e else "general"


def _is_exempt(mem: dict) -> bool:
    """是否豁免遗忘：pinned / gating promote / 身份类 entity。"""
    if mem.get("pinned"):
        return True
    if mem.get("gating_override") == "promote":
        return True
    if _project_of(mem) in EXEMPT_ENTITIES:
        return True
    return False


def access_tracking_cutoff_ts(memories: list[dict]):
    """访问统计停止工作的时点，返回该时点前最后一条有访问记录的记忆时间戳。

    v3.11.2: 修一个「把信号缺失当成信号本身」的缺陷。

    背景：v3.9.5 P2-11 起 `sb_memory.search()` 的 `update_access_stats`
    默认关闭（「读路径不带写副作用」），且全仓库无调用方传 True，
    于是**该版本之后创建的记忆，access_count 永远不可能是非零**。

    实测（2026-08-30，548 条 active）：

    | 创建月份 | 有访问记录 | 总数 | 占比 |
    |---|---|---|---|
    | 2026-06 | 21  | 26  | 81% |
    | 2026-07 | 146 | 204 | 72% |
    | 2026-08 | 0   | 318 | **0%** |

    即访问统计在 2026-08 前某个时点停止。原实现不加区分地把
    `access_count == 0` 一律判为「从未被访问」→ `DECAY_NEVER_ACCESSED(2.0)`，
    导致**最新鲜的记忆反而被当作最容易遗忘的**：昨天创建的记忆拿到最高档
    衰减，6 月的老记忆因为有历史访问记录而只拿正常档。

    ⚠️ 我第一版把问题写成「全库 access_count 恒为 0」——**那是错的**，
    实测 30.5% 的记忆有访问记录。真正的形态是「按时点断裂」，不是「全库失效」。
    """
    ts = [m.get("timestamp") for m in memories
          if int(m.get("access_count") or 0) > 0 and m.get("timestamp")]
    return max(ts) if ts else None


def _decay_factor(mem: dict, tracking_cutoff=None) -> float:
    """记忆级衰减因子：从未访问 > 近期访问过 > 正常。

    `tracking_cutoff` 为访问统计停止工作的时点（见 access_tracking_cutoff_ts）。
    创建于该时点**之后**的记忆，其 `access_count == 0` 不代表「从未被访问」，
    只代表「信号缺失」——此时退化为中性值 DECAY_NORMAL，避免让最新鲜的
    记忆背上最重的衰减。
    """
    if _is_exempt(mem):
        return 0.0
    access_count = int(mem.get("access_count") or 0)
    if access_count == 0:
        if tracking_cutoff and (mem.get("timestamp") or "") > tracking_cutoff:
            return DECAY_NORMAL          # 信号缺失，不可判定
        return DECAY_NEVER_ACCESSED      # 可被统计期间内确未访问
    last_days = _days_since(mem.get("last_accessed"))
    if last_days is not None and last_days <= 30:
        return DECAY_RECENTLY_ACCESSED
    return DECAY_NORMAL


# ─────────────────────────────────────────────
# 项目活跃度与档位
# ─────────────────────────────────────────────
def compute_project_activity(project_mems: list[dict]) -> float:
    """
    计算项目活跃度 A (0.0–1.0)。时间主导（median 最后访问天数），访问频率只做放大器。

    校准原则（2026-08-11 真实数据）：
    - "实验型大项目"的特征是"规模大但最近不用"——历史访问次数不能独立抬分，
      只能在时间分 > 0 时放大（最近活跃过的高频项目更活跃）。
    - 项目最后访问中位数 >= 45 天 → 时间分归零 → dormant。
    """
    if not project_mems:
        return 0.0
    last_access_days: list[int] = []
    update_days: list[int] = []
    access_counts: list[int] = []
    for m in project_mems:
        la = _days_since(m.get("last_accessed"))
        if la is not None:
            last_access_days.append(la)
        up = _days_since(m.get("timestamp"))
        if up is not None:
            update_days.append(up)
        access_counts.append(int(m.get("access_count") or 0))

    # 时间信号：优先最后访问，缺失则用更新时间，全缺视为 dormant
    signal = last_access_days or update_days
    if not signal:
        return 0.0
    median_days = sorted(signal)[len(signal) // 2]

    # 时间分：median_days <= ACTIVE_DAYS 满分，>= DORMANT_DAYS 归零，线性过渡
    if median_days <= ACTIVE_DAYS:
        time_component = 1.0
    elif median_days >= DORMANT_DAYS:
        time_component = 0.0
    else:
        span = DORMANT_DAYS - ACTIVE_DAYS
        time_component = max(0.0, 1.0 - (median_days - ACTIVE_DAYS) / span)

    # 访问频率只做放大器（上限 0.3×时间分），不能独立抬分
    avg_access = sum(access_counts) / max(len(access_counts), 1)
    access_boost = min(0.3, avg_access / 20) * time_component

    return round(min(1.0, time_component + access_boost), 4)


def compute_project_median_days(project_mems: list[dict]) -> Optional[int]:
    """项目最后访问天数中位数；无时间信号返回 None（保守视为 dormant）。"""
    if not project_mems:
        return None
    signal = []
    for m in project_mems:
        la = _days_since(m.get("last_accessed"))
        if la is not None:
            signal.append(la)
    if not signal:
        return None
    return sorted(signal)[len(signal) // 2]


def project_tier(median_days: Optional[int]) -> str:
    """
    项目档位（基于最后访问中位数，直观可解释）：
    - median_days <= ACTIVE_DAYS(14) → active
    - median_days <= DORMANT_DAYS(45) → warm
    - 否则 / 无时间信号 → dormant
    """
    if median_days is None:
        return "dormant"
    if median_days <= ACTIVE_DAYS:
        return "active"
    if median_days <= DORMANT_DAYS:
        return "warm"
    return "dormant"


def forgetting_weight(tier: str) -> float:
    """项目档位 → 召回降权系数。active=1.0 / warm=0.8 / dormant=0.5。"""
    if tier == "dormant":
        return WEIGHT_DORMANT
    if tier == "warm":
        return WEIGHT_WARM
    return 1.0


def compute_forget_priority(mem: dict, project_stats: dict,
                            tracking_cutoff=None) -> float:
    """
    计算单条记忆的遗忘优先级 (0.0–1.0)。
    forget_priority = S(项目规模占比) × (1 - A(项目活跃度)) × D(记忆衰减因子)
    豁免记忆 → 0.0（永不遗忘）。

    v3.11.2: 新增 `tracking_cutoff`，透传给 _decay_factor。
    访问统计停止后创建的记忆不再被误判为「从未被访问」。
    """
    if _is_exempt(mem):
        return 0.0
    project = _project_of(mem)
    stat = project_stats.get(project)
    if not stat or stat["count"] == 0:
        return 0.0
    S = stat["count"] / max(stat.get("total", 1), 1)
    A = stat["activity"]
    D = _decay_factor(mem, tracking_cutoff)
    return round(min(1.0, S * (1 - A) * D), 4)


def compute_project_stats(memories: list[dict]) -> dict:
    """
    计算全部项目的统计：
    {project: {count, activity, tier, weight, total}}
    total = 全部记忆条数（用于规模占比）
    """
    total = len(memories)
    groups: dict[str, list[dict]] = {}
    for m in memories:
        p = _project_of(m)
        groups.setdefault(p, []).append(m)

    stats = {}
    for p, mems in groups.items():
        activity = compute_project_activity(mems)
        median_days = compute_project_median_days(mems)
        tier = project_tier(median_days)
        stats[p] = {
            "count": len(mems),
            "activity": activity,
            "median_days": median_days,
            "tier": tier,
            "weight": forgetting_weight(tier),
            "total": total,
        }
    return stats


def get_memory_weight(mem: dict, project_stats: dict) -> float:
    """
    单条记忆的最终召回权重：
    - 豁免记忆 → 1.0（永不降权）
    - 否则 → 项目档位权重（dormant 0.5 / warm 0.8 / active 1.0）
    """
    if _is_exempt(mem):
        return 1.0
    project = _project_of(mem)
    stat = project_stats.get(project)
    if not stat:
        return 1.0
    return stat["weight"]


# ─────────────────────────────────────────────
# 批量治理动作
# ─────────────────────────────────────────────
def scan_forgetting(memories: list[dict]) -> dict:
    """
    dry-run 扫描：返回项目档位统计 + 建议降权/归档的记忆列表（不写库）。
    - dormant 候选：apply 会处理（demote）
    - warm 高风险候选（priority >= CANDIDATE_PRIORITY_MIN）：仅报告，不自动 apply

    v3.11 修复：只统计 active 子集（与 search 降权同源）。archived 记忆已归档，
    不参与检索，也不纳入遗忘治理范围——否则报告口径与检索实际降权不一致
    （同一项目在报告里是 warm，在检索里却是 active）。
    """
    active = [m for m in memories if m.get("status") == "active"]
    stats = compute_project_stats(active)
    # v3.11.2: 算出访问统计停止的时点，透传给优先级计算。
    # 该时点之后创建的记忆，access_count=0 不再被当作「从未被访问」。
    cutoff = access_tracking_cutoff_ts(active)
    dormant_candidates = []
    warm_high_risk = []
    for m in active:
        p = _project_of(m)
        stat = stats.get(p)
        if not stat:
            continue
        priority = compute_forget_priority(m, stats, cutoff)
        if priority <= 0:
            continue
        item = {
            "id": m.get("id"),
            "project": p,
            "priority": priority,
            "entity": m.get("entity"),
            "content": (m.get("content") or "")[:60],
        }
        if stat["tier"] == "dormant":
            dormant_candidates.append(item)
        elif stat["tier"] == "warm" and priority >= CANDIDATE_PRIORITY_MIN:
            warm_high_risk.append(item)
    dormant_candidates.sort(key=lambda x: -x["priority"])
    warm_high_risk.sort(key=lambda x: -x["priority"])
    result = {
        "stats": stats,
        "dormant_candidates": dormant_candidates,
        "warm_high_risk": warm_high_risk,
    }
    # v3.11.2: 把访问统计的断裂时点暴露给调用方与状态报告——
    # 该时点之后创建的记忆无法判定「是否被访问过」，衰减已退化为中性值，
    # 这份数字的口径必须让使用者知道。
    if cutoff:
        untrackable = sum(1 for m in active
                          if (m.get("timestamp") or "") > cutoff)
        result["access_tracking"] = {
            "cutoff_ts": cutoff,
            "untrackable_count": untrackable,
            "untrackable_ratio": round(untrackable / max(len(active), 1), 4),
            "reason": "该时点之后创建的记忆 access_count 恒为 0"
                      "（update_access_stats 默认关闭），衰减因子已退化为"
                      " DECAY_NORMAL，不再套用 DECAY_NEVER_ACCESSED。",
        }
    else:
        result["access_tracking"] = {"cutoff_ts": None, "untrackable_count": 0}
    return result


def apply_forgetting(memories: list[dict]) -> dict:
    """
    执行遗忘治理（软切）：dormant 项目记忆批量打 gating_override=demote。
    幂等：已 demote 的跳过。豁免记忆不动。返回修改条数与修改后列表。

    v3.11 修复：只统计 active 子集（与 search 降权同源），archived 记忆不处理
    （已归档，无需再 demote）。返回完整 memories 列表（含 archived），保证写回不丢。
    """
    active = [m for m in memories if m.get("status") == "active"]
    stats = compute_project_stats(active)
    changed = 0
    for m in memories:
        if m.get("status") != "active":
            continue  # archived 已归档，不纳入治理
        if _is_exempt(m):
            continue
        p = _project_of(m)
        stat = stats.get(p)
        if stat and stat["tier"] == "dormant" and m.get("gating_override") != "demote":
            m["gating_override"] = "demote"
            changed += 1
    return {"changed": changed, "stats": stats, "memories": memories}


def status_forgetting(memories: list[dict]) -> dict:
    """
    状态总览：各项目档位 + 豁免/候选统计。

    v3.11 修复：档位统计只基于 active 子集（与 search 降权同源），
    与检索实际降权行为一致。total 仍报全量，新增 active 计数供对照。
    """
    all_memories = memories
    active = [m for m in memories if m.get("status") == "active"]
    stats = compute_project_stats(active)
    total = len(all_memories)
    active_count = len(active)
    tier_count = {}
    exempt_count = 0
    for m in active:
        if _is_exempt(m):
            exempt_count += 1
        p = _project_of(m)
        st = stats.get(p, {})
        tier = st.get("tier", "?")
        tier_count[tier] = tier_count.get(tier, 0) + 1
    return {
        "total": total,
        "active": active_count,
        "exempt": exempt_count,
        "tier_counts": tier_count,
        "projects": stats,
    }
