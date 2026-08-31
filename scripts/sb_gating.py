#!/usr/bin/env python3
"""
SuperBrain Workspace Gating Layer v3.6.0
=========================================
Implements the "global workspace" selectivity principle inspired by
Anthropic's "A Global Workspace in Language Models" (2026-07-06):

  The active workspace is a PRIVILEGED SUBSET of all stored memories.
  Most processing runs automatically on cold storage; only memories that
  cross a salience threshold get "promoted" into the workspace that
  participates in reasoning and gets injected into context.

This module provides:
  - compute_salience(mem)        : score a memory's promotion worthiness [0,1]
  - get_threshold / set_threshold : per-workspace promotion threshold (default 0.35)
  - is_promoted(mem)              : salience >= threshold AND active
  - chain_ignite(workspace)       : if any node of a reasoning chain is promoted,
                                    the whole chain ignites (paper's Ignition idea)
  - get_active_workspace(...)     : the promoted, capacity-capped workspace
  - promote / demote              : manual override of a single memory
  - calibrate(workspace)          : report promotion ratio at a threshold (tuning aid)

Pure standard library. No external dependencies (consistent with the skill).

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import time
import uuid
import functools
import inspect
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    read_memories, write_memories, read_meta, update_meta, get_timestamp,
    read_json, write_json, get_workspace_dir, generate_id, DEFAULT_DATA_DIR,
    workspace_lock
)


def _write_locked(func):
    """写事务装饰器：gating 写操作整体包进跨进程 workspace 锁。
    与 sb_memory/sb_graph 的 _write_locked 同构（锁在 sb_core.workspace_lock
    层可重入，嵌套已锁调用不死锁）。

    v3.11.2 (P0-L 审阅补遗)：get_active_workspace / promote / demote /
    chain_ignite 都是 memories.json 的 read-modify-write，此前**全部无锁**
    ——sb_memory/sb_graph 写路径上锁后这里成了并发丢写的裸露面（鲸砚并发
    gating status / memory add 时 last-writer-wins）。
    与 sb_graph 版的差异：用 inspect 绑定参数取 workspace，兼容位置传参。
    """
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            bound = sig.bind_partial(*args, **kwargs)
            ws = bound.arguments.get("workspace")
        except TypeError:
            ws = None
        with workspace_lock(ws):
            return func(*args, **kwargs)
    return wrapper

# --- Defaults -------------------------------------------------------------
# v3.11.2 (P0-H，编号顺延：P0-E persona / P0-F CJK 已占用、P0-G 已撤回):
# 默认晋升阈值 0.35 → 0.55。0.35 是形同虚设的值——实测本库
# salience 分布极窄（548 条 active，min 0.362 / 中位 0.500 / max 0.638），
# 0.35 低于全库最低值，晋升比例恒 100%（实测 137 条标志 > cap 50，selfcheck
# 的 gating_flood_protection 持续 CRITICAL）。根因是固定底座就占了 ~0.32：
# 0.30×confidence(≈0.89) + 0.10×(baseline+0.5)，真正能拉开差距的 entanglement
# 信号因图谱空转（627 记忆仅 14 节点）几乎恒为 0；access 项又因访问统计
# 时点断裂（2026-07-16 后创建的记忆恒 0，见基线报告 §20）在 63.7% 记忆上
# 恒零——五个项里 35% 权重是死的。
# 阈值扫描（真实库，2026-08-30 晚，sb_gating.calibrate）：
#     thr   promoted  ratio
#     0.35     548    1.000   ← 旧默认值，全量晋升
#     0.40     515    0.940
#     0.45     437    0.797
#     0.50     273    0.498
#     0.55     107    0.195   ← 唯一落进 GWT 目标带(8~25%)的取值
#     0.60      13    0.024   ← 悬崖：0.55→0.60 之间密度极高
#     0.65       0    0.000
# ⚠️ 定位声明（与基线报告 §17.1 对齐）：这刀是「治理稳定化」的过渡方案，
# 不是终解。§17.1 的诊断成立——调阈值是脆弱的纸糊方案（0.55→0.60 断崖），
# 正解是修公式本身（让 confidence 不再充当偏移量、复活 access/entanglement
# 判别力）。在本库上 0.55 之下选出的主要是「新鲜+常访问」热集，不是「重要」
# 集合。公式修复或图谱复活后，本值必须用 calibrate 重新标定。
#
# v3.11.2 (P0-I) 再标定：P0-I 自动建图落地后（147 节点 / 241 边，458 条
# 记忆回填 related_nodes），entanglement 信号复活，salience 分布整体上移
# 且变宽（中位 0.500→0.612，span 0.28→0.42）——阈值 0.55 之下不再适用，
# 重新扫描：0.60→55.4% / 0.65→37.5% / **0.70→14.6%(80条，带内)** / 0.72→8.4%
# / 0.75→0.9%。取 0.70。与 0.55 时代的本质区别：选出集现在是**结构驱动**的
# ——选出集平均 entanglement 4.84 vs 全库 3.44（68/80 条 ent=5），type 构成
# decision 35 / fact 21 / task 11 / preference 5 / event 8。「纸糊方案」的
# 批判部分失效：第二个信号活了，但 confidence 偏移量问题仍在，公式修复
# 仍是正解。
# ⚠️ 行为变化：新写入记忆 related_nodes=[]（ent=0，salience≈0.57），
# 在下一次 graph build 前不会进入工作空间——GWT 语义上这是「新记忆需经
# 连接性/使用证明后才广播」，但也意味着 graph build 需要成为定期动作。
#
# ⚠️⚠️ 阈值是 per-workspace 机制，不是全局常数（2026-08-30 深夜审阅教训）：
# 0.70 在项目库（有图谱 entanglement）上标定，但 persona 库无图谱、ent 恒 0、
# salience 天花板 ≈0.63——0.70 会让 persona 库结构性死锁（新记忆永远无法
# 晋升，违背 v3.6「身份常驻工作空间」设计底线）。persona 已独立标定 0.35
# （持久化在 persona meta）。**任何异构 workspace 接入门控前必须先 calibrate**。
# v3.11.2 (P0-L)：DEFAULT_THRESHOLD 降级为「手动模式的遗留兜底」——自动模式
# （meta 无显式值）走相对门控，此常数仅在 meta 读取失败时兜底，正常路径不再
# 使用。绝对阈值常数的一天三标（0.35→0.55→0.70）就此终结。
DEFAULT_THRESHOLD = 0.70
# v3.11.2 (P0-L)：相对门控目标比例。GWT 带 8~25%，取中点偏下。
# meta 键 gating_target_ratio 可按 workspace 覆盖。
DEFAULT_TARGET_RATIO = 0.15
DEFAULT_CAP = 50

# Type-level baseline adjustment to salience (added into the [0,1] mapping).
# preference/decision are worth keeping hot; reasoning_intermediate starts
# cooler so it does not flood the workspace unless its chain ignites.
TYPE_BASELINE = {
    "preference": 0.15,
    "decision": 0.12,
    "task": 0.05,
    "event": 0.03,
    "relationship": 0.0,
    "fact": 0.0,
    "context": -0.05,
    "reasoning_intermediate": -0.25,
}


# --- Helpers --------------------------------------------------------------
def _parse_ts(ts):
    """Parse a SuperBrain timestamp into a timezone-aware datetime, or None."""
    if not ts:
        return None
    s = str(ts).replace("Z", "+00:00")
    try:
        if "T" in s:
            dt = datetime.fromisoformat(s)
        else:
            dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _days_since(ts):
    """Days since a timestamp; very large if missing/parseable."""
    dt = _parse_ts(ts)
    if dt is None:
        return 999.0
    now = datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def _target_ratio(workspace=None):
    """晋升目标比例（GWT 带 8~25% 的中点偏下）。meta 可按 workspace 覆盖。"""
    try:
        meta = read_meta(workspace)
        raw = meta.get("gating_target_ratio")
        if raw is not None:
            v = float(raw)
            if 0.0 < v <= 1.0:
                return v
    except Exception:
        pass
    return DEFAULT_TARGET_RATIO


def _dynamic_threshold(workspace=None):
    """
    v3.11.2 (P0-L): 相对门控的核心——阈值从「绝对常数」改为「当前库
    salience 排名的第 k 高值」，k = min(cap, max(1, round(n×目标比例)))。

    为什么这样设计（2026-08-30 一天三标 0.35→0.55→0.70 的教训）：
      - 分布漂移免疫：库增长/建图改变 entanglement/任何结构性变化后，
        阈值随排名自动滑动，**永远不需要重新标定**（scale-free）；
      - confidence 偏移量免疫：绝对阈值下 confidence 的固定底座把全库挤在
        窄带里（§17.1），排名制对常数偏移完全无感——salience 公式的
        「confidence 当偏移量」问题在门控层自动失效；
      - 与 cap 协同：k 被 cap 封顶，flag 集合 ≤ cap，selfcheck 洪水保护
        由构造保证绿色（不再依赖 cap 执行器兜底）；
      - O(n) 成本：每次调用对 active 记忆算一遍 salience——add_memory 本就
        O(n)（simhash 查重），无显著开销。

    ⚠️ 手动模式（meta 显式设置 gating_threshold，如 persona=0.35）优先于
    本函数——小型身份库需要「常驻」语义，不适用比例晋升。
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    # v3.11.2 (P0-L 审阅补遗)：手动钉选（gating_override）不占自动排名位。
    # 实测主库有 328 条历史 demote override（来源无法溯源，审计已滚动），
    # 其中 18 条挤在 top-50 排名里——若不排除，自动晋升被占位（50→32）。
    # 候选池 = 无 override 的记忆；比例也以候选池为基数（GWT 语义：
    # 「未被手动钉选的记忆中，salience 前 k 名进工作空间」）。
    candidates = [m for m in active if not m.get("gating_override")]
    n = len(candidates)
    if n == 0:
        return 0.0  # 全库皆钉选：极端边界，首条新记忆仍应可晋升
    k = min(DEFAULT_CAP, max(1, round(n * _target_ratio(workspace))))
    sals = sorted((compute_salience(m, workspace) for m in candidates), reverse=True)
    return sals[k - 1]


def get_threshold(workspace=None):
    """
    Read the promotion threshold for this workspace.

    v3.11.2 (P0-L) 双模式：
      1. 手动模式——meta 显式存了 gating_threshold（如 persona=0.35），
         直接返回。适合需要「常驻」语义的小型身份库。
      2. 自动模式（默认）——相对门控：阈值 = 当前库 salience 排名第 k 高值
         （见 _dynamic_threshold）。库结构漂移免重标。
    CLI `gating threshold --auto` 可清除手动值回到自动模式。

    历史：v3.11.2 (P0-H) 修过 meta 值为 None 时靠 float(None) 异常兜底的
    脆弱写法；P0-L 将 None 语义从「用全局默认常数」升级为「相对门控」。
    """
    try:
        meta = read_meta(workspace)
        raw = meta.get("gating_threshold")
        if raw is not None:
            return float(raw)
    except Exception:
        pass
    return _dynamic_threshold(workspace)


def set_threshold(value, workspace=None):
    """Persist the promotion threshold for this workspace (switches to manual mode).

    v3.11.2 (P0-L): 传 None 清除手动值、回到相对门控自动模式
    （CLI `gating threshold --auto`）。
    """
    with workspace_lock(workspace):
        if value is None:
            update_meta("gating_threshold", None, workspace)
            return None
        v = float(value)
        if not (0.0 <= v <= 1.0):
            raise ValueError("threshold must be in [0, 1]")
        update_meta("gating_threshold", v, workspace)
        return v


# --- Core salience --------------------------------------------------------
def compute_salience(mem, workspace=None):
    """
    Compute a memory's salience in [0, 1] from multiple signals:

      confidence   : how sure we are of the memory
      recency      : exponential decay (half-life ~30 days) of last_accessed
      access_count : log-saturating usage frequency (cap ~10)
      entanglement : number of related_nodes (graph connectivity)
      type         : baseline adjustment (preference/decision hotter,
                     reasoning_intermediate cooler)

    The final score is a weighted sum mapped into [0, 1].
    """
    mem_type = mem.get("type", "fact")
    confidence = float(mem.get("confidence", 0.5))
    recency_days = _days_since(mem.get("last_accessed") or mem.get("timestamp"))
    access = int(mem.get("access_count", 0))
    entanglement = len(mem.get("related_nodes", []) or [])

    recency = 0.5 ** (recency_days / 30.0)               # 1.0 fresh -> 0.0 old
    access_score = min(1.0, (access ** 0.5) / (10 ** 0.5))
    ent_score = min(1.0, entanglement / 5.0)
    baseline = TYPE_BASELINE.get(mem_type, 0.0)

    # Map baseline (-0.25 .. +0.15) into a 0..1 contribution via (baseline + 0.5).
    sal = (0.30 * confidence
           + 0.25 * recency
           + 0.20 * access_score
           + 0.15 * ent_score
           + 0.10 * (baseline + 0.5))
    sal = max(0.0, min(1.0, sal))
    return round(sal, 4)


def is_promoted(mem, workspace=None):
    """True if the memory is active and its salience crosses the threshold."""
    if mem.get("status") != "active":
        return False
    return compute_salience(mem, workspace) >= get_threshold(workspace)


# --- Ignition & active workspace ------------------------------------------
def _cap_enforce(active, cap, workspace):
    """
    v3.11.x: 容量上限的持久执行器（审阅高位项 gating_flood_protection 加固）。

    旧版 get_active_workspace 只截断返回值、不回写降级，workspace_promoted
    标志随每次调用只增不减（实测 95 > cap 50），晋升洪水保护持续 CRITICAL。
    chain_ignite 单独调用同样绕过了容量约束。本执行器统一两条路径：

      1. 手动 promote override 视为钉选，优先保留（override 语义优先于容量）；
      2. 其余晋升按「链为单位」排序（链内最高 salience 代表整链），整链能放进
         剩余容量则整链保留——推理链不被容量切碎；
      3. 放不下的链按个体 salience 填满剩余槽位（硬上限优先于链原子性）；
      4. 超容部分持久降级：清 workspace_promoted 标志、写可逆审计，
         **不带 gating_override**，下次按 salience 重评可自然回迁。

    Returns:
        int: 本次降级的记忆数（0 = 无需降级）。
    """
    if not cap:
        return 0
    promoted = [m for m in active if m.get("workspace_promoted")]
    if len(promoted) <= cap:
        return 0

    def sal(m):
        return compute_salience(m, workspace)

    manual = [m for m in promoted if m.get("gating_override") == "promote"]
    auto = [m for m in promoted if m.get("gating_override") != "promote"]
    kept = {m["id"] for m in manual}

    units = []  # (代表 salience, 成员列表)；无链记忆各自成单元
    by_chain = {}
    for m in auto:
        cid = m.get("chain_id")
        if cid:
            by_chain.setdefault(cid, []).append(m)
        else:
            units.append((sal(m), [m]))
    for members in by_chain.values():
        units.append((max(sal(m) for m in members), members))
    units.sort(key=lambda t: t[0], reverse=True)

    remaining = cap - len(kept)
    for _, members in units:
        if remaining <= 0:
            break
        if len(members) <= remaining:
            kept.update(m["id"] for m in members)
            remaining -= len(members)
        else:
            members.sort(key=sal, reverse=True)
            kept.update(m["id"] for m in members[:remaining])
            remaining = 0

    demoted = 0
    for m in promoted:
        if m["id"] not in kept:
            before = {"workspace_promoted": True}
            m["workspace_promoted"] = False
            _audit_log("cap_demote", m["id"],
                       f"容量上限 cap={cap}：超容自动降级（可逆，按 salience 重评）",
                       before, {"workspace_promoted": False},
                       reversible=True, workspace=workspace)
            demoted += 1
    return demoted


@_write_locked
def chain_ignite(workspace=None):
    """
    Paper's Ignition: if ANY node of a reasoning chain is promoted (by salience
    or by manual override), the WHOLE chain ignites into the workspace. This
    prevents intermediate reasoning nodes from being starved when only one
    link happens to be retrieved.

    v3.11.x: 点燃后执行 _cap_enforce（DEFAULT_CAP），整链点燃不再能把
    晋升数推过容量上限——洪水保护对独立调用路径同样成立。
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    threshold = get_threshold(workspace)

    chain_promoted = set()
    for m in active:
        cid = m.get("chain_id")
        if not cid:
            continue
        if m.get("workspace_promoted", False) or compute_salience(m, workspace) >= threshold:
            chain_promoted.add(cid)

    changed = 0
    for m in active:
        cid = m.get("chain_id")
        if cid in chain_promoted and not m.get("workspace_promoted", False):
            before = {"workspace_promoted": False}
            m["workspace_promoted"] = True
            after = {"workspace_promoted": True}
            changed += 1
            # v3.7: audit trail — chain ignite is reversible
            _audit_log("chain_ignite", m["id"],
                       f"Chain ignited via chain_id={cid}",
                       before, after, reversible=True, workspace=workspace)

    # v3.11.x: 点燃后统一执行容量上限（与 get_active_workspace 共用执行器）
    cap_demoted = _cap_enforce(active, DEFAULT_CAP, workspace)

    if changed or cap_demoted:
        write_memories(memories, workspace)
    return {"chain_promoted": len(chain_promoted), "changed": changed,
            "cap_demoted": cap_demoted}


@_write_locked
def get_active_workspace(workspace=None, cap=DEFAULT_CAP):
    """
    Return the promoted memories (the 'global workspace' analog).

    **Persists promoted state to disk** (writes memories back).
    Not thread-safe / Not multi-process safe — last-writer-wins on
    concurrent access. Chain ignition applied inline; manual
    gating_override (promote/demote) is respected.

    Promotion rule:
      1. A memory is promoted if salience >= threshold OR manually flagged.
      2. Chain ignition: any promoted chain node promotes its whole chain.
      3. The result is sorted by salience and capped to `cap` (capacity limit),
         mirroring GWT's limited workspace capacity.
    """
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    threshold = get_threshold(workspace)

    # v3.6.1: gating_override 优先（手动 promote/demote 不被 salience 重算覆盖）
    # v3.11.2 (P0-I 审阅补遗)：无 override 的记忆双向重评。旧写法
    # `elif not promoted` 只升不降——已带 flag 但 salience 跌破阈值的记忆
    # 永远不会被重评（实测 persona 库 34 条全部冻死在 0.35 时代的 flag=True，
    # 而按现阈值 0.70 无一达标）。标志必须诚实跟踪 salience。
    for m in active:
        ov = m.get("gating_override")
        if ov == "promote":
            m["workspace_promoted"] = True
        elif ov == "demote":
            m["workspace_promoted"] = False
        else:
            m["workspace_promoted"] = compute_salience(m, workspace) >= threshold

    chain_promoted = set()
    for m in active:
        cid = m.get("chain_id")
        if cid and (m.get("workspace_promoted", False) or compute_salience(m, workspace) >= threshold):
            chain_promoted.add(cid)
    for m in active:
        cid = m.get("chain_id")
        if cid in chain_promoted:
            m["workspace_promoted"] = True

    promoted = [m for m in active if m.get("workspace_promoted")]
    # 手动 promote override 视为钉选，优先保留；其余按 salience 降序
    manual = [m for m in promoted if m.get("gating_override") == "promote"]
    auto = [m for m in promoted if m.get("gating_override") != "promote"]
    auto.sort(key=lambda m: compute_salience(m, workspace), reverse=True)
    ranked = manual + auto
    if cap and len(ranked) > cap:
        # v3.11.x 修复（审阅高位项 gating_flood_protection）：
        # 旧版只截断返回值、不回写降级，workspace_promoted 标志随每次调用
        # 只增不减（实测 95 > cap 50）。现在由 _cap_enforce 持久降级超容
        # 部分（可逆、无 override、链为单位保留），洪水保护不依赖调用方自律。
        _cap_enforce(active, cap, workspace)
        kept_ids = {m["id"] for m in active if m.get("workspace_promoted")}
        promoted = [m for m in ranked if m["id"] in kept_ids]
    else:
        promoted = ranked

    write_memories(memories, workspace)
    return promoted


# --- Manual override ------------------------------------------------------
@_write_locked
def promote(mem_id, workspace=None):
    """Force-promote a single memory into the workspace (manual override)."""
    memories = read_memories(workspace)
    for m in memories:
        if m["id"] == mem_id and m.get("status") == "active":
            before = {"workspace_promoted": m.get("workspace_promoted", False)}
            m["gating_override"] = "promote"
            m["workspace_promoted"] = True
            m["salience"] = max(m.get("salience", 0.0), get_threshold(workspace))
            after = {"workspace_promoted": True, "gating_override": "promote"}
            write_memories(memories, workspace)
            # v3.7: audit trail
            _audit_log("manual_promote", mem_id,
                       f"Manual promote override (salience >= {get_threshold(workspace)})",
                       before, after, reversible=False, workspace=workspace)
            return {"id": mem_id, "promoted": True}
    return {"id": mem_id, "promoted": False, "reason": "not found or inactive"}


@_write_locked
def demote(mem_id, workspace=None):
    """Force-demote a single memory out of the workspace (manual override)."""
    memories = read_memories(workspace)
    for m in memories:
        if m["id"] == mem_id:
            before = {"workspace_promoted": m.get("workspace_promoted", False)}
            m["gating_override"] = "demote"
            m["workspace_promoted"] = False
            after = {"workspace_promoted": False, "gating_override": "demote"}
            write_memories(memories, workspace)
            # v3.7: audit trail
            _audit_log("manual_demote", mem_id,
                       "Manual demote override",
                       before, after, reversible=False, workspace=workspace)
            return {"id": mem_id, "demoted": True}
    return {"id": mem_id, "demoted": False, "reason": "not found"}


# --- v3.7: Audit Log & Rollback (Karpathy Iron Man 套装固化) -----------------
_MAX_AUDIT_ENTRIES = 500


def _audit_log(action, target_id, reason, before, after, reversible=True, workspace=None):
    """
    Record a gating action to the audit trail.
    All auto/manual promote/demote/chain_ignite flow through here.
    """
    ws_dir = get_workspace_dir(workspace)
    log_path = os.path.join(ws_dir, "audit_log.json")
    log = read_json(log_path) or {"entries": []}

    entry = {
        "id": f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}",
        "timestamp": get_timestamp(),
        "action": action,
        "target_id": target_id,
        "target_type": "memory",
        "reason": reason,
        "before_state": before,
        "after_state": after,
        "reversible": reversible,
        "reverted": False
    }
    log["entries"].append(entry)

    # Trim to max entries
    if len(log["entries"]) > _MAX_AUDIT_ENTRIES:
        log["entries"] = log["entries"][-_MAX_AUDIT_ENTRIES:]

    write_json(log_path, log)
    return entry


def _get_audit_entries_for(mem_id, workspace=None):
    """Retrieve all audit entries for a specific memory."""
    ws_dir = get_workspace_dir(workspace)
    log_path = os.path.join(ws_dir, "audit_log.json")
    log = read_json(log_path)
    if not log:
        return []
    return [e for e in log.get("entries", []) if e.get("target_id") == mem_id]


def get_audit_log(limit=20, workspace=None):
    """Retrieve recent audit entries."""
    ws_dir = get_workspace_dir(workspace)
    log_path = os.path.join(ws_dir, "audit_log.json")
    log = read_json(log_path)
    if not log:
        return {"entries": [], "total": 0}
    entries = log.get("entries", [])
    return {"entries": entries[-limit:], "total": len(entries)}


def rollback(n=1, workspace=None):
    """
    Rollback the last N reversible auto-actions.
    Manual overrides (manual_promote/manual_demote) are not auto-rolled back.
    Returns list of rolled-back entry IDs.
    """
    ws_dir = get_workspace_dir(workspace)
    log_path = os.path.join(ws_dir, "audit_log.json")
    log = read_json(log_path)
    if not log:
        return {"rolled_back": 0, "ids": []}

    rolled_back = []
    count = 0
    memories = read_memories(workspace)

    for entry in reversed(log["entries"]):
        if count >= n:
            break
        if not entry.get("reversible", False):
            continue
        if entry.get("reverted", False):
            continue
        # Only auto-rollback non-manual actions
        if entry["action"].startswith("manual_"):
            continue

        target_id = entry["target_id"]
        before = entry.get("before_state", {})

        # Restore before_state
        for m in memories:
            if m["id"] == target_id:
                for key, val in before.items():
                    if key in ("workspace_promoted", "gating_override", "salience"):
                        m[key] = val
                break

        entry["reverted"] = True
        rolled_back.append(entry["id"])
        count += 1

    if rolled_back:
        # v3.8.6: write audit log BEFORE restoring memories. If we crash
        # between the two, the audit says "reverted" (no double-rollback);
        # the residual (memory not yet restored) is detectable via explain().
        write_json(log_path, log)
        write_memories(memories, workspace)

    return {"rolled_back": len(rolled_back), "ids": rolled_back}


def explain(mem_id, workspace=None):
    """
    Return a human-readable explanation of a memory's gating state:
    current salience, why promoted/demoted, full audit trail.
    """
    memories = read_memories(workspace)
    mem = next((m for m in memories if m["id"] == mem_id), None)

    if not mem:
        return {"memory_id": mem_id, "found": False, "reason": "memory not found"}

    audit = _get_audit_entries_for(mem_id, workspace)

    # Build salience breakdown
    mem_type = mem.get("type", "fact")
    confidence = float(mem.get("confidence", 0.5))
    access = int(mem.get("access_count", 0))
    entanglement = len(mem.get("related_nodes", []) or [])
    recency_days = _days_since(mem.get("last_accessed") or mem.get("timestamp"))

    return {
        "memory_id": mem_id,
        "found": True,
        "current_salience": mem.get("salience"),
        "current_promoted": mem.get("workspace_promoted", False),
        "gating_override": mem.get("gating_override"),
        "provenance": mem.get("provenance", "unknown"),
        "salience_breakdown": {
            "confidence": confidence,
            "recency_days": round(recency_days, 1),
            "access_count": access,
            "entanglement": entanglement,
            "type": mem_type,
            "type_baseline": TYPE_BASELINE.get(mem_type, 0.0)
        },
        "audit_trail": audit
    }


# --- Diagnostics ----------------------------------------------------------
def calibrate(workspace=None, threshold=None):
    """
    Report the promotion ratio at a given threshold. Use this to tune the
    threshold toward the GWT-aligned band (~8-25% of active memories promoted).
    """
    # v3.11.2 (P0-L 审阅补遗)：口径统一为候选池（排除 gating_override 记忆），
    # 与 _dynamic_threshold 排名语义一致。旧口径把 override 记入分子（实测
    # 328 条历史 demote 中 18 条越阈值），calibrate 报的比例与实际 flag 数对不上。
    threshold = float(threshold) if threshold is not None else get_threshold(workspace)
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    candidates = [m for m in active if not m.get("gating_override")]
    promoted = [m for m in candidates if compute_salience(m, workspace) >= threshold]
    ratio = len(promoted) / max(len(candidates), 1)

    if ratio > 0.25:
        recommendation = "ratio too high (>25%): raise threshold to shrink the workspace"
    elif ratio < 0.08:
        recommendation = "ratio too low (<8%): lower threshold to grow the workspace"
    else:
        recommendation = "within GWT-aligned 8-25% band"

    return {
        "total_active": len(active),
        "candidates": len(candidates),
        "promoted": len(promoted),
        "promotion_ratio": round(ratio, 3),
        "threshold": threshold,
        "recommendation": recommendation,
    }


def get_status(workspace=None):
    """Compact status snapshot for CLI / diagnostics."""
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    promoted = get_active_workspace(workspace)
    return {
        "threshold": get_threshold(workspace),
        "total_active": len(active),
        "promoted": len(promoted),
        "promotion_ratio": round(len(promoted) / max(len(active), 1), 3),
    }


# ============================================================================
# v3.9.5: 硬步骤门控设施（从 superbrain.py 下沉到领域层）
# 修复审阅 P1-5（门控加固）+ P2-10（策略下沉：门控策略不应在 CLI 层）
# ============================================================================

HARDSTEP_STATE_FILE = os.path.join(DEFAULT_DATA_DIR, ".hardstep.json")
HARDSTEP_WINDOW_SECONDS = 30 * 60
HARDSTEP_OVERRIDES_MAX = 200  # v3.9.5: overrides 环形截断


def _hardstep_load():
    """读取硬步骤状态文件（best-effort）。"""
    try:
        return read_json(HARDSTEP_STATE_FILE) or {}
    except Exception:
        return {}


def _hardstep_save(state):
    """v3.9.5: 改用 sb_core.write_json 原子写，替代裸 json.dump。"""
    return write_json(HARDSTEP_STATE_FILE, state)


def mark_search_done(query=""):
    """记录一次 memory search，解锁后续写入命令。"""
    state = _hardstep_load()
    state["last_search_ts"] = time.time()
    state["last_search_query"] = (query or "")[:200]
    ok = _hardstep_save(state)
    if not ok:
        print("⚠️ [HARD-STEP] mark_search_done 写入失败，后续写入可能被误拦截",
              file=sys.stderr)
    return ok


def enforce_hard_step_guard(force, content="", command=""):
    """拦截未先检索的写入命令。

    v3.9.5 加固：
    - _hardstep_save 改用 write_json 原子写（修复裸 json.dump）
    - last_search_ts 未来时间拒绝（阻止手填绕过，修复审阅安全中危项）
    - overrides 环形截断 200 条（修复 .hardstep.json 无限膨胀）

    v3.9.7 修复跨会话死锁：
    - 跨会话 / 新会话场景（last_search_ts 超时 / None）改为自动重置计时器并放行，
      而非 sys.exit(2) 拦截。保留警告提醒，消除跨会话自动入库静默丢失。
    """
    if force:
        state = _hardstep_load()
        overrides = state.get("overrides") or []
        overrides.append({
            "ts": time.time(),
            "command": command or "unknown",
            "content_preview": (content or "")[:100],
        })
        # v3.9.5: 环形截断——防 .hardstep.json 无限膨胀
        if len(overrides) > HARDSTEP_OVERRIDES_MAX:
            overrides = overrides[-HARDSTEP_OVERRIDES_MAX:]
        state["overrides"] = overrides
        _hardstep_save(state)
        print("⚠️ [HARD-STEP OVERRIDE] 已用 --force 跳过「先检索后入库」强制校验（已写入审计）。",
              file=sys.stderr)
        return

    state = _hardstep_load()
    last = state.get("last_search_ts")

    # v3.9.5: 未来时间拒绝——阻止手填时间戳绕过门控
    if isinstance(last, (int, float)) and last > time.time() + 3600:
        print("⚠️ [HARD-STEP] 检测到未来时间戳（疑为绕过门控），已重置检索状态。", file=sys.stderr)
        state["last_search_ts"] = None
        state.pop("last_search_query", None)
        _hardstep_save(state)
        last = None

    satisfied = last is not None and (time.time() - last) <= HARDSTEP_WINDOW_SECONDS
    if satisfied:
        last_query = state.get("last_search_query", "")
        if content and last_query:
            try:
                from sb_search import ternary_hash, ternary_similarity
                sim = ternary_similarity(ternary_hash(last_query), ternary_hash(content))
                if sim < 0.05:
                    print(f"⚠️ [HARD-STEP 警告] 上次检索「{last_query[:40]}」与入库内容相关性低 (sim={sim:.3f})",
                          file=sys.stderr)
                    print("  建议先检索相关主题再入库；如确属不同主题，加 --force 豁免。",
                          file=sys.stderr)
            except Exception:
                pass
        return

    # 跨会话 / 新会话：自动重置计时器并放行，而非 exit 2 拦截
    if last is None:
        reason = "从未检索（新环境或状态已重置）"
    else:
        elapsed = int(time.time() - last)
        reason = f"上次检索在 {elapsed} 秒前，已超过 {HARDSTEP_WINDOW_SECONDS}s 窗口（跨会话新会话）"

    print(f"\n  ℹ [HARD-STEP] {reason}。已自动重置检索计时器，本次写入已放行。",
          file=sys.stderr)
    print("  ℹ [HARD-STEP] 建议先执行 `SB memory search \"<主题>\"` 检索相关记忆。\n",
          file=sys.stderr)

    state["last_search_ts"] = time.time()
    state["last_search_query"] = ""
    _hardstep_save(state)
    return
