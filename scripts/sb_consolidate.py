#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sb_consolidate — L1 后台记忆整合引擎（零 token，proposal→apply 两段式）
=========================================================================

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888

阶段2「补差距」核心产物（2026-08-31 启动）：后台自动整合是 Mem0 Dream /
Zep 抽取管线 / LangMem Background / Letta sleep-time / A-Mem evolution
五家全有的能力，超脑独缺。本引擎以**零 LLM、零 token、纯规则**实现，
作为 sb_healthlite（L0 守护）之上的可选 L1 阶段。

设计铁律（全部来自实测教训，2026-08-30 整合负结果 + P0-J 人工裁决）：
  1. **两段式**：先生成 proposal 清单（可审、可 dry-run），确认后才 apply。
     后台无人值守模式**只生成 proposal，永不自动 apply**。
  2. **避开已证伪路径**：对话碎片整合（Δ0 且有损）、纯去重（空间近零）
     不做。A/B/C/D 四档动作各有独立判定门槛，D 档只信「同句 ID 引用
     + 更正标记」硬证据（相似带触发路径已实测证伪删除，见 gen_supersede）。
  3. **尊重人工裁决**（P0-J）：「砚：/用户：」对话碎片保留 general——
     entity 词表匹配不会命中它们（无既有实体名）；只指派到**已存在且
     频次 ≥3** 的实体，绝不新建实体。
  4. **可回滚**：apply 前自动备份 memories.json；每条动作写审计日志
     （reversible=True）；内容哈希随修改同步重算（simhash + ternary）。

四档动作：
  A  gen_entity_reassign   general 实体增量归一（词表唯一命中才提案）
  B  gen_similar_merge     同实体近重复对合并（simhash ≥ 0.80，贪心不重叠）
  C  gen_verbose_compress  冗长陈旧记录抽取式压缩（>200字 & >30天，
                            抽句规则确定性，压缩比不达标则不提案）
  D  gen_supersede         知识更新链提案（阶段2-B 时态启用）：更正型新记忆
                            → 旧事实 superseded+replaced_by+valid_until 三件套
                            （对齐原生 replaces 语义，可回滚）

用法：
  python sb_consolidate.py --workspace X                # 生成 proposal（dry-run）
  python sb_consolidate.py --workspace X --apply        # 应用全部提案
  python sb_consolidate.py --workspace X --actions a    # 只跑 A 档
  python sb_consolidate.py --workspace X --apply --actions a,c

输出：
  proposal → <workspace>/consolidation_proposals.json
  apply    → 备份 memories.json.bak_<日期>_consolidate + 审计日志
"""

import argparse
import io
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

from sb_core import (                                   # noqa: E402
    read_memories, write_memories, read_meta, read_json, write_json,
    get_workspace_dir, get_timestamp, workspace_lock, load_config,
)
from sb_search import simhash, simhash_similarity, ternary_hash   # noqa: E402
from sb_gating import _audit_log, _parse_ts             # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# --- 阈值常量（改这里必须同步 SKILL.md 与验收报告口径） --------------------
ENTITY_MIN_FREQ = 3          # A：实体词表入库最低频次（P0-J「不值得新建」语义）
ENTITY_MIN_LEN = 2           # A：实体名最短长度（滤掉「砚」等单字歧义名）
MERGE_SIM_THRESHOLD = 0.80   # B：同实体近重复合并门槛（selfcheck 重复=0.85+）
COMPRESS_MIN_CHARS = 200     # C：冗长判定
COMPRESS_STALE_DAYS = 30     # C：陈旧判定（未更新超 30 天）
COMPRESS_MIN_SENTENCES = 4   # C：句子数不足 4 不压（压了不成话）
COMPRESS_MAX_RATIO = 0.5     # C：压缩结果必须 ≤ 原文一半，否则不值得压
# D 档：知识更新链（阶段2-B）。唯一可信触发=「同句 mem_id 引用 + 更正
# 标记词」。同实体相似带路径已在生产实测中证伪删除（精确率 ~7%，
# 详见 gen_supersede docstring 的教训记录）。
CORRECTION_MARKERS = ("更正", "修正", "有误", "误记", "并非", "实际是",
                      "改为", "已改", "不再是", "推翻", "实为", "更正为",
                      "supersedes", "已失效", "过时")
# 对话碎片前缀（P0-J 裁决保留 general，A/C 两档一并跳过）
FRAGMENT_PREFIXES = ("砚：", "用户：", "砚:", "用户:")
# A 档实体黑名单：过于泛化/垃圾的实体名（多为早期系统 demo 数据的兜底实体）。
# 把 general 贴到这些实体上不是归一化是污染（2026-08-31 复核发现「用户」
# 频次 8 /「API」频次 3 /「GitHub」频次 4 全来自 demo 残留簇——P0-J 裁决
# 「demo 残留保留 general 留待用户决定是否清理」在此以黑名单形式落地）。
ENTITY_BLOCKLIST = {"用户", "API", "GitHub", "系统", "项目", "数据", "测试", "工具"}


# --- 通用工具 ---------------------------------------------------------------
def _prefix12(m):
    """content 前 12 字，proposal 断言用（P0-J 同款防索引错位）。"""
    return (m.get("content", "") or "")[:12]


def _days_stale(m):
    """距上次更新（updated_at 优先）天数。"""
    dt = _parse_ts(m.get("updated_at") or m.get("timestamp"))
    if dt is None:
        return 999.0
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)


def _entity_vocab(active):
    """A 档词表：active 记忆中出现频次 ≥ ENTITY_MIN_FREQ 的实体名。

    「已存在 + 有存量支撑」是 P0-J 的裁决语义——绝不新建实体，
    滇西北旅行/demo 残留因此天然不命中（词表里没有）。
    """
    from collections import Counter
    freq = Counter((m.get("entity") or "").strip() for m in active)
    vocab = {}
    for name, n in freq.items():
        if (not name or name.lower() == "general"
                or name in ENTITY_BLOCKLIST
                or len(name) < ENTITY_MIN_LEN):
            continue
        if n >= ENTITY_MIN_FREQ:
            vocab[name] = n
    return vocab


def _recompute_hashes(m, bits):
    """内容/实体变更后同步重算 simhash + ternary（防查重与 selfcheck 失真）。"""
    full_text = f"{m.get('entity', '')} {m.get('content', '')}"
    m["simhash"] = simhash(full_text, bits)
    m["ternary_hash"] = ternary_hash(full_text, bits)


# --- A 档：general 实体增量归一 ----------------------------------------------
def gen_entity_reassign(active, vocab):
    """对 entity=general 的 active 记忆做词表匹配，**唯一命中**才提案。

    唯一性要求：内容中只出现一个词表实体——同时命中两个以上实体说明
    归属不明，留给人工。对话碎片按 P0-J 裁决直接跳过。
    """
    proposals = []
    for m in active:
        if (m.get("entity") or "").strip().lower() != "general":
            continue
        content = m.get("content", "") or ""
        if content.startswith(FRAGMENT_PREFIXES):
            continue
        hits = sorted(name for name in vocab
                      if name.lower() in content.lower())
        if len(hits) == 1:
            proposals.append({
                "id": m["id"],
                "action": "entity_reassign",
                "from": "general",
                "to": hits[0],
                "reason": f"词表唯一命中（实体频次 {vocab[hits[0]]}）",
                "content_prefix": _prefix12(m),
            })
    return proposals


# --- B 档：同实体近重复对合并 -------------------------------------------------
def gen_similar_merge(active):
    """同 entity 的 active 记忆两两 simhash ≥ 0.80 → 合并提案（贪心不重叠）。

    与 selfcheck duplicates（0.85 完全重复带）错开：本档吃的是
    「同主题反复记录」的近重复带。合并语义沿用 merge_memories：
    高置信方吸收，低置信方归档 + replaced_by，内容拼接不丢信息。
    对话碎片（砚：/用户：前缀）不整合（8-30 负结果铁律）。
    """
    by_entity = {}
    for m in active:
        ent = (m.get("entity") or "").strip().lower()
        by_entity.setdefault(ent, []).append(m)

    pairs = []
    for ent, group in by_entity.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                # 对话碎片不整合：任一方是碎片则跳过该对
                if ((a.get("content") or "").startswith(FRAGMENT_PREFIXES)
                        or (b.get("content") or "").startswith(FRAGMENT_PREFIXES)):
                    continue
                ha, hb = a.get("simhash"), b.get("simhash")
                if ha is None or hb is None:
                    continue
                sim = simhash_similarity(ha, hb)
                if sim >= MERGE_SIM_THRESHOLD:
                    pairs.append((sim, a, b))
    pairs.sort(key=lambda t: t[0], reverse=True)

    used, proposals = set(), []
    for sim, a, b in pairs:
        if a["id"] in used or b["id"] in used:
            continue
        used.add(a["id"])
        used.add(b["id"])
        keeper, deprecated = (a, b) if a.get("confidence", 0) >= b.get("confidence", 0) else (b, a)
        proposals.append({
            "action": "similar_merge",
            "keeper_id": keeper["id"],
            "deprecated_id": deprecated["id"],
            "entity": (keeper.get("entity") or ""),
            "similarity": round(sim, 3),
            "keeper_prefix": _prefix12(keeper),
            "deprecated_prefix": _prefix12(deprecated),
        })
    return proposals


# --- C 档：冗长陈旧记录抽取式压缩 ---------------------------------------------
_SENT_SPLIT = re.compile(r"[。；！？\n]+")
_COMPRESS_MARKERS = ("结论", "决定", "拍板", "关键", "必须", "注意",
                     "教训", "坑", "验收", "已修", "已做", "新增")


def _extractive_compress(content, entity):
    """确定性抽句：实体句/数字句/结论标记句优先，保原顺序取 top3。

    返回 (compressed, n_sentences)；不满足压缩比由调用方判定放弃。
    """
    sentences = [s.strip() for s in _SENT_SPLIT.split(content) if len(s.strip()) >= 6]
    if len(sentences) < COMPRESS_MIN_SENTENCES:
        return None, len(sentences)

    def score(s):
        sc = 0
        if entity and entity.lower() not in ("general",) and entity.lower() in s.lower():
            sc += 2
        if re.search(r"\d", s):
            sc += 2
        if any(mk in s for mk in _COMPRESS_MARKERS):
            sc += 1
        if 15 <= len(s) <= 60:
            sc += 1
        return sc

    ranked = sorted(range(len(sentences)), key=lambda i: score(sentences[i]),
                    reverse=True)[:3]
    chosen = sorted(ranked)  # 恢复原顺序，保叙事线
    compressed = "；".join(sentences[i] for i in chosen)
    return compressed, len(sentences)


def gen_verbose_compress(active):
    """>200字 & >30天未更新 → 抽取式压缩提案。

    有损但可回滚（备份 + 审计 before_state 存原长度，原文在备份文件）。
    压缩结果长度不在 [20, 原文一半] 区间则不提案——压不动不如不压。
    """
    proposals = []
    for m in active:
        content = m.get("content", "") or ""
        if content.startswith(FRAGMENT_PREFIXES):
            continue
        if len(content) <= COMPRESS_MIN_CHARS:
            continue
        if _days_stale(m) < COMPRESS_STALE_DAYS:
            continue
        if m.get("replaced_by"):
            continue
        entity = m.get("entity") or "general"
        compressed, n_sent = _extractive_compress(content, entity)
        if compressed is None:
            continue
        if not (20 <= len(compressed) <= int(len(content) * COMPRESS_MAX_RATIO)):
            continue
        proposals.append({
            "id": m["id"],
            "action": "verbose_compress",
            "entity": entity,
            "old_len": len(content),
            "new_len": len(compressed),
            "n_sentences": n_sent,
            "new_content": compressed,
            "content_prefix": _prefix12(m),
        })
    return proposals


# --- D 档：知识更新链提案（阶段2-B 时态启用） ---------------------------------
# ID 正则同时接「全 ID」与「无 hex 后缀的截断引用」（生产实锤：
# 「此前 mem_20260709_004455 称'发布'有误」写的就是截断 ID）。
# 截断引用经 gen_supersede 里的唯一前缀匹配兜底解析。
_MEM_ID_RE = re.compile(r"mem_\d{8}_\d{6}(?:_[0-9a-f]{4,})?")


def gen_supersede(active):
    """更正型新记忆 → 旧事实打 valid_until 的提案（软失效，不删不改 status）。

    触发条件（全部满足，2026-08-31 生产实测校准）：
      - 新记忆 content 显式引用旧记忆的 mem_* ID（硬链接）
      - **引用 ID 的那个句子里含更正标记词**（更正/有误/supersedes/误记…）
      - 旧记忆更早（timestamp 更小）、双方 active、旧记忆尚无 valid_until

    动作语义（v2，对齐原生 replaces 流）：old 三件套 status=superseded +
    replaced_by=新记忆 + valid_until=新记忆创建日期——检索池天然排除，
    审计可逆。初版「软失效」（active+valid_until 走 ×0.85 降权）被
    selfcheck temporal_validity 打回：检查器视「active+已过期」为卫生
    问题，且 valid_until 本义是用户声明的有效期，不该承载「被更正」语义。

    ⚠️ 已证伪并删除的触发路径（保留教训）：
      1. 「同句无标记的纯显式引用」——生产 54 条提案里「细节见同日各分条
         记忆」类**会话汇总**与「关联：mem_xxx」类**纯关联**全部误报；
      2. 「同实体 sim∈[0.45,0.80) 相似带 + 全文任意位置含更正词」——
         精确率仅 ~7%：长中文同实体文本 sim 0.45-0.65 是常态噪声，且
         「修正权协议」「修正今日早先归因」的「修正」指向别处（最荒唐
         误报：修正权协议条被当成对人格补全场所条的更正）。
      结论：自动 supersede 只信「同句 ID+更正语义」这一种硬证据。
    """
    by_id = {m["id"]: m for m in active}
    proposals = []
    used_old = set()
    for m in active:
        content = m.get("content", "") or ""
        # 按句切分，逐句找「引用 ID + 同句更正标记」
        segments = _SENT_SPLIT.split(content)
        for seg in segments:
            refs = set(_MEM_ID_RE.findall(seg))
            if not refs:
                continue
            if not any(mk in seg for mk in CORRECTION_MARKERS):
                continue  # 引用句无更正语义=纯引用/关联，跳过
            for ref in refs:
                old = by_id.get(ref)
                if old is None:
                    # 引用的 ID 可能被截断（前缀）——唯一前缀匹配兜底
                    cands = [x for x in active
                             if x["id"].startswith(ref) and x["id"] != m["id"]]
                    old = cands[0] if len(cands) == 1 else None
                if (old is None or old["id"] == m["id"] or old["id"] in used_old
                        or old.get("valid_until")):
                    continue
                if (old.get("timestamp") or "") >= (m.get("timestamp") or ""):
                    continue  # 被引用方必须更早
                used_old.add(old["id"])
                proposals.append({
                    "id": old["id"],
                    "action": "supersede",
                    "new_id": m["id"],
                    "trigger": "explicit_ref_correction",
                    "valid_until": (m.get("timestamp") or "")[:10],
                    "reason": f"新记忆同句引用并更正（{m['id']}）",
                    "content_prefix": _prefix12(old),
                    "new_prefix": _prefix12(m),
                })
    return proposals


# --- 汇总：生成 proposal ------------------------------------------------------
def generate_proposals(workspace=None, actions="a,b,c,d"):
    """读库 → 四档提案。只读，不写 memories.json。"""
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    vocab = _entity_vocab(active)
    want = {a.strip().lower() for a in actions.split(",") if a.strip()}

    result = {
        "engine": "sb_consolidate",
        "version": 1,
        "workspace": workspace or "default",
        "timestamp": get_timestamp(),
        "config": {
            "entity_min_freq": ENTITY_MIN_FREQ,
            "merge_sim_threshold": MERGE_SIM_THRESHOLD,
            "compress_min_chars": COMPRESS_MIN_CHARS,
            "compress_stale_days": COMPRESS_STALE_DAYS,
        },
        "actions": {},
        "stats": {
            "n_active": len(active),
            "n_general": sum(1 for m in active
                             if (m.get("entity") or "").lower() == "general"),
            "vocab_size": len(vocab),
        },
    }
    if "a" in want:
        result["actions"]["entity_reassign"] = gen_entity_reassign(active, vocab)
    if "b" in want:
        result["actions"]["similar_merge"] = gen_similar_merge(active)
    if "c" in want:
        result["actions"]["verbose_compress"] = gen_verbose_compress(active)
    if "d" in want:
        result["actions"]["supersede"] = gen_supersede(active)
    return result


# --- 应用（写路径：锁内单次 read-modify-write） -------------------------------
def apply_proposals(workspace=None, proposal_path=None, actions="a,b,c"):
    """应用 proposal：前缀断言 → 备份 → 锁内写盘 → 审计 → 哈希重算。"""
    ws_dir = get_workspace_dir(workspace)
    if proposal_path is None:
        proposal_path = os.path.join(ws_dir, "consolidation_proposals.json")
    prop = read_json(proposal_path)
    if not prop or not prop.get("actions"):
        print("无 proposal 可应用（先运行生成步骤）。")
        return {"applied": 0}

    want = {a.strip().lower() for a in actions.split(",") if a.strip()}
    bits = load_config().get("simhash_bits", 64)
    now = get_timestamp()
    # v3.12.2：备份名带 %H%M 防同日多次 apply 互相覆盖（踩坑实录：
    # 同日 A/C 档与 D 档先后 apply，日期级 stamp 让第二次备份覆盖了
    # 第一次。最早状态尚存于更早备份，但中间态丢失——时间戳必须到分钟）。
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    applied, skipped = [], []

    with workspace_lock(workspace):
        memories = read_memories(workspace)
        by_id = {m["id"]: m for m in memories}
        src = os.path.join(ws_dir, "memories.json")
        bak = f"{src}.bak_{stamp}_consolidate"

        # ---- A：实体重指派（前缀断言兜底防索引错位）----
        for p in prop["actions"].get("entity_reassign", []):
            if "a" not in want:
                continue
            m = by_id.get(p["id"])
            if not m or m.get("status") != "active":
                skipped.append((p["id"], "not found / inactive")); continue
            if not (m.get("content", "") or "").startswith(p["content_prefix"][:8]):
                skipped.append((p["id"], "prefix assert fail")); continue
            if (m.get("entity") or "").lower() != "general":
                skipped.append((p["id"], "entity no longer general")); continue
            before = {"entity": m.get("entity")}
            m["entity"] = p["to"]
            m["updated_at"] = now
            _recompute_hashes(m, bits)
            _audit_log("consolidate_entity", m["id"],
                       f"A 档：general → {p['to']}（{p['reason']}）",
                       before, {"entity": p["to"]},
                       reversible=True, workspace=workspace)
            applied.append(("entity_reassign", m["id"], p["to"]))

        # ---- B：近重复合并（吸收方内容拼接，被并方归档）----
        for p in prop["actions"].get("similar_merge", []):
            if "b" not in want:
                continue
            keeper = by_id.get(p["keeper_id"])
            deprecated = by_id.get(p["deprecated_id"])
            if not keeper or not deprecated:
                skipped.append((p.get("keeper_id"), "pair not found")); continue
            if deprecated.get("status") != "active":
                skipped.append((p["deprecated_id"], "already merged")); continue
            if not (deprecated.get("content", "") or "").startswith(p["deprecated_prefix"][:8]):
                skipped.append((p["deprecated_id"], "prefix assert fail")); continue
            before = {"status": "active", "content_len": len(deprecated.get("content", ""))}
            # merge_memories 语义（v3.8.7）：内容拼接不丢信息 + 置信度增信
            if deprecated["content"] not in keeper["content"]:
                keeper["content"] = keeper["content"] + " [merged: " + deprecated["content"] + "]"
            keeper["confidence"] = min(1.0, float(keeper.get("confidence", 0.8)) + 0.05)
            keeper["related_nodes"] = list(set(
                (keeper.get("related_nodes") or []) + (deprecated.get("related_nodes") or [])))
            keeper["updated_at"] = now
            deprecated["status"] = "archived"
            deprecated["replaced_by"] = keeper["id"]
            deprecated["updated_at"] = now
            _recompute_hashes(keeper, bits)
            _recompute_hashes(deprecated, bits)
            _audit_log("consolidate_merge", keeper["id"],
                       f"B 档：合并 {deprecated['id']}（sim={p['similarity']}）",
                       before, {"merged_from": deprecated["id"]},
                       reversible=True, workspace=workspace)
            applied.append(("similar_merge", deprecated["id"], keeper["id"]))

        # ---- C：冗长压缩（原内容留在备份，审计存长度）----
        for p in prop["actions"].get("verbose_compress", []):
            if "c" not in want:
                continue
            m = by_id.get(p["id"])
            if not m or m.get("status") != "active":
                skipped.append((p["id"], "not found / inactive")); continue
            if not (m.get("content", "") or "").startswith(p["content_prefix"][:8]):
                skipped.append((p["id"], "prefix assert fail")); continue
            before = {"content_len": p["old_len"],
                      "note": "原文完整存于备份 " + os.path.basename(bak)}
            m["content"] = p["new_content"]
            m["updated_at"] = now
            attrs = m.get("attributes") or {}
            attrs["consolidation"] = {
                "compressed_at": now, "original_len": p["old_len"],
            }
            m["attributes"] = attrs
            _recompute_hashes(m, bits)
            _audit_log("consolidate_compress", m["id"],
                       f"C 档：{p['old_len']} → {p['new_len']} 字（{p['n_sentences']} 句抽 3）",
                       before, {"content_len": p["new_len"]},
                       reversible=True, workspace=workspace)
            applied.append(("verbose_compress", m["id"], f"{p['old_len']}→{p['new_len']}"))

        # ---- D：知识更新链（旧事实硬失效，对齐原生 replaces 语义）----
        # v2（2026-08-31 校准）：初版设计「软失效」（status 保持 active +
        # valid_until 过期降权 ×0.85）被 selfcheck temporal_validity 打回——
        # 检查器把「active + valid_until 已过期」视为卫生问题，且系统原生
        # --replaces 流就是 status=superseded + replaced_by。语义冲突根源：
        # valid_until 本义是「用户声明的有效期」（如优惠到某日），D 档的
        # 「被更正」语义应走 superseded 硬失效通道。三件套齐写：
        # status=superseded + replaced_by=更正条 + valid_until=更正日。
        for p in prop["actions"].get("supersede", []):
            if "d" not in want:
                continue
            m = by_id.get(p["id"])
            if not m or m.get("status") != "active":
                skipped.append((p["id"], "not found / inactive")); continue
            if not (m.get("content", "") or "").startswith(p["content_prefix"][:8]):
                skipped.append((p["id"], "prefix assert fail")); continue
            if m.get("valid_until") or m.get("replaced_by"):
                skipped.append((p["id"], "already superseded")); continue
            before = {"valid_until": None, "status": "active", "replaced_by": None}
            m["valid_until"] = p["valid_until"]
            m["status"] = "superseded"
            m["replaced_by"] = p["new_id"]
            m["updated_at"] = now
            _audit_log("consolidate_supersede", m["id"],
                       f"D 档：知识更新（{p['reason']}，superseded by {p['new_id']}）",
                       before, {"status": "superseded", "replaced_by": p["new_id"],
                                "valid_until": p["valid_until"]},
                       reversible=True, workspace=workspace)
            applied.append(("supersede", m["id"], f"→{p['new_id'][:22]} valid_until={p['valid_until']}"))

        if not applied:
            print("零条提案通过断言，未写盘。")
            if skipped:
                for sid, why in skipped:
                    print(f"  跳过 {sid}: {why}")
            return {"applied": 0, "skipped": skipped}

        shutil.copy2(src, bak)
        write_memories(memories, workspace)
        print(f"备份: {bak}")
        print(f"已写盘: {len(applied)} 条动作。")
        for kind, mid, extra in applied:
            print(f"  [{kind}] {mid} → {extra}")
        if skipped:
            print(f"跳过 {len(skipped)} 条（断言失败/状态变化）：")
            for sid, why in skipped:
                print(f"  跳过 {sid}: {why}")

        # v3.12.2（M2 工作台踩坑）：apply 后重生成 proposal 文件——
        # 否则工作台面板会显示已应用的陈旧提案（实测 supersede:2 挂了一天）。
        # 重生成走全档默认（a,b,c,d），反映「还剩什么待处理」。
        fresh = generate_proposals(workspace)
        fresh_path = os.path.join(get_workspace_dir(workspace),
                                  "consolidation_proposals.json")
        write_json(fresh_path, fresh)

    return {"applied": len(applied), "skipped": skipped}


# --- CLI --------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="超脑 L1 后台整合引擎（proposal → apply 两段式，默认 dry-run）")
    ap.add_argument("--workspace", default=os.environ.get("SUPERBRAIN_WORKSPACE", "default"))
    ap.add_argument("--actions", default="a,b,c,d",
                    help="动作档位：a=实体归一 b=近重复合并 c=冗长压缩 d=知识更新链（逗号分隔）")
    ap.add_argument("--apply", action="store_true",
                    help="应用 consolidation_proposals.json（默认只生成 proposal）")
    args = ap.parse_args()

    if args.apply:
        out = apply_proposals(args.workspace, actions=args.actions)
        return 0 if out.get("applied", 0) >= 0 else 1

    prop = generate_proposals(args.workspace, actions=args.actions)
    ws_dir = get_workspace_dir(args.workspace)
    out_path = os.path.join(ws_dir, "consolidation_proposals.json")
    write_json(out_path, prop)

    acts = prop["actions"]
    print(f"[sb_consolidate] proposal 已生成 → {out_path}")
    print(f"  active {prop['stats']['n_active']} | general {prop['stats']['n_general']}"
          f" | 词表 {prop['stats']['vocab_size']} 实体")
    for name, items in acts.items():
        print(f"  {name}: {len(items)} 条提案")
        for p in items[:5]:
            if p["action"] == "entity_reassign":
                print(f"    {p['id']} general → {p['to']} | {p['content_prefix']}")
            elif p["action"] == "similar_merge":
                print(f"    {p['deprecated_id']} → {p['keeper_id']} (sim={p['similarity']})")
            elif p["action"] == "supersede":
                print(f"    {p['id']} valid_until={p['valid_until']} ← {p['new_id']} | {p['reason'][:30]}")
            else:
                print(f"    {p['id']} {p['old_len']}→{p['new_len']}字 | {p['content_prefix']}")
        if len(items) > 5:
            print(f"    … 其余 {len(items) - 5} 条见 JSON")
    return 0


if __name__ == "__main__":
    sys.exit(main())
