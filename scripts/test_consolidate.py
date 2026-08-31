#!/usr/bin/env python3
"""
v3.12.2 L1 后台整合引擎测试（sb_consolidate）
================================================
覆盖三档动作 + 两段式安全设计：
  T1  A 档词表命中：general 记忆唯一命中既有实体（频次≥3）才提案
  T2  A 档排除：对话碎片前缀 / 黑名单实体 / 多实体歧义 / 低频实体不提案
  T3  B 档近重复合并：同实体 sim≥0.80 提案合并；碎片对跳过
  T4  C 档压缩：>200字 & >30天 & ≥4句 → 提案且压缩比 ≤50%；不足门槛不提案
  T5  apply 两段式：前缀断言失败中止该条；成功后哈希重算 + 审计可回溯
  T6  幂等性：apply 后再生成 proposal，已处理项不再出现
  T7  只读保证：generate_proposals 不写盘（mtime 不变）

隔离方式与 test_relative_gating 相同：独立 workspace 逻辑名，原地清空。

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, write_memories, ensure_workspace, read_json
from sb_consolidate import (
    generate_proposals, apply_proposals,
    ENTITY_BLOCKLIST, FRAGMENT_PREFIXES,
)

WS = "sb_test_consolidate"

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def reset_workspace():
    ensure_workspace(WS)
    write_memories([], WS)


def mk(content, entity="general", days_ago=60, conf=0.9, mid=None):
    """构造测试记忆。days_ago 控制陈旧度（updated_at 回拨）。"""
    from datetime import datetime, timedelta, timezone
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "id": mid or f"mem_test_{int(time.time()*1000)}_{content[:6]}",
        "type": "fact",
        "entity": entity,
        "content": content,
        "confidence": conf,
        "status": "active",
        "timestamp": ts,
        "updated_at": ts,
        "related_nodes": [],
        "simhash": None,
    }


def run():
    print("== T1/T2: A 档词表命中与排除 ==")
    reset_workspace()
    # 词表：实体「超脑」×3 达频次门槛；「用户」黑名单；「ab」单字级长度不足
    vocab_seed = [mk(f"超脑种子记录{i}", entity="超脑") for i in range(3)]
    # 唯一命中：general + 内容含「超脑」
    hit = mk("超脑 v3.6.0 发布并推送 GitHub")
    # 对话碎片：跳过
    frag = mk("用户：我们最近在做什么")
    # 黑名单实体命中（内容含「用户」字样 + 词表有「用户」实体——先造词表）
    blk_seed = [mk(f"用户偏好记录{i}", entity="用户") for i in range(8)]
    blk_hit = mk("用户偏好 TypeScript 严格模式")
    # 多实体歧义：同时命中「超脑」与「求职」（求职需词表在）
    job_seed = [mk(f"求职种子{i}", entity="求职") for i in range(3)]
    amb = mk("超脑与求职双主题混合内容超脑求职")
    write_memories(vocab_seed + [hit, frag] + blk_seed + [blk_hit] + job_seed + [amb], WS)

    prop = generate_proposals(WS, actions="a")
    a_ids = {p["id"] for p in prop["actions"]["entity_reassign"]}
    check("T1 唯一命中实体被提案", hit["id"] in a_ids, str(a_ids))
    check("T2 碎片不提案", frag["id"] not in a_ids)
    check("T2 黑名单实体不提案", blk_hit["id"] not in a_ids)
    check("T2 多实体歧义不提案", amb["id"] not in a_ids)
    check("T2 种子记录不被改", not (a_ids & {m['id'] for m in vocab_seed + job_seed}))

    print("== T3: B 档近重复合并 ==")
    reset_workspace()
    # 长文本对实测 sim≈0.84（短文本 simhash 位翻转噪声大，B 档门槛用长文本验证）
    base_txt = ("超脑 v3.6.0 发布推送 GitHub。包含 12 项新测试全部通过。"
                "修复了门控层的 salience 阈值 bug 已修复。补充分说明内容。")
    sim_a = mk(base_txt, entity="超脑")
    sim_b = mk(base_txt + "补充分说明内容更长一些。修复了门控层的 salience 阈值 bug 已修复完毕。",
               entity="超脑", conf=0.85)
    frag_pair = mk("用户：那个项目叫什么", entity="问答")
    frag_pair2 = mk("用户：那个项目到底叫什么", entity="问答")
    write_memories([sim_a, sim_b, frag_pair, frag_pair2], WS)
    # B 档 simhash 依赖写路径计算——手工补 simhash（生产由 add_memory 计算）
    # ⚠️ 必须写「已哈希的同一批对象」：先 read 再 write 会被重读覆盖回未哈希副本
    from sb_search import simhash
    mems = read_memories(WS)
    for m in mems:
        m["simhash"] = simhash(f"{m['entity']} {m['content']}")
    write_memories(mems, WS)

    prop = generate_proposals(WS, actions="b")
    merges = prop["actions"]["similar_merge"]
    check("T3 近重复对提案 ≥1", len(merges) >= 1, str(merges))
    frag_merged = any(p["deprecated_id"] == frag_pair["id"] for p in merges)
    check("T3 碎片对不合并", not frag_merged)

    print("== T4: C 档压缩门槛与压缩比 ==")
    reset_workspace()
    long_stale = mk("超脑 v3.6.0 发布。包含 12 项新测试。修复门控 bug 已修。"
                    "补充说明内容很长的过程描述。以及更多细节第五句。第六句也是凑长度用的。"
                    "第七句继续凑。第八句凑够字数。" * 3, entity="超脑", days_ago=60)
    fresh_long = mk("超脑最新记录。内容同样很长。数字 42。结论重要。补充说明。凑句。凑句。凑句。" * 3,
                    entity="超脑", days_ago=1)
    short_old = mk("太短不压。", entity="超脑", days_ago=90)
    write_memories([long_stale, fresh_long, short_old], WS)

    prop = generate_proposals(WS, actions="c")
    cs = {p["id"]: p for p in prop["actions"]["verbose_compress"]}
    check("T4 冗长+陈旧被提案", long_stale["id"] in cs)
    check("T4 新鲜长文不提案", fresh_long["id"] not in cs)
    check("T4 短文不提案", short_old["id"] not in cs)
    if long_stale["id"] in cs:
        p = cs[long_stale["id"]]
        check("T4 压缩比 ≤50%", p["new_len"] <= p["old_len"] * 0.5,
              f"{p['new_len']}/{p['old_len']}")

    print("== T7: 生成阶段只读 ==")
    ws_file = None
    from sb_core import get_workspace_dir
    ws_file = os.path.join(get_workspace_dir(WS), "memories.json")
    mtime0 = os.path.getmtime(ws_file)
    generate_proposals(WS, actions="a,b,c")
    check("T7 generate 不写盘", os.path.getmtime(ws_file) == mtime0)

    print("== T5/T6: apply 断言 + 幂等 ==")
    # 用 T4 的 proposal 手工构造断言失败条目混入，验证单条失败不拖垮整批
    prop_file = os.path.join(get_workspace_dir(WS), "consolidation_proposals.json")
    from sb_consolidate import write_json
    prop["actions"]["verbose_compress"].append({
        "id": "mem_test_nonexistent", "action": "verbose_compress",
        "entity": "超脑", "old_len": 100, "new_len": 50,
        "n_sentences": 6, "new_content": "不存在", "content_prefix": "不存在前缀",
    })
    write_json(prop_file, prop)

    out = apply_proposals(WS, proposal_path=prop_file, actions="c")
    check("T5 幂等断言：不存在条目跳过", any("not found" in str(s) for s in out.get("skipped", [])))
    check("T5 有效条目已应用", out.get("applied", 0) >= 1, str(out.get("applied")))

    mems = {m["id"]: m for m in read_memories(WS)}
    if long_stale["id"] in mems:
        m = mems[long_stale["id"]]
        check("T5 压缩内容已写盘", len(m["content"]) <= 0.6 * len(long_stale["content"]))
        check("T5 simhash 已重算", m.get("simhash") is not None)
        check("T5 审计标记存在", (m.get("attributes") or {}).get("consolidation") is not None)

    prop2 = generate_proposals(WS, actions="c")
    ids2 = {p["id"] for p in prop2["actions"]["verbose_compress"]}
    check("T6 幂等：已压缩项不再提案", long_stale["id"] not in ids2,
          f"仍出现: {ids2 & {long_stale['id']}}")

    print("== T8: D 档知识更新链（同句 ID+更正语义） ==")
    reset_workspace()
    from datetime import timedelta
    old_a = mk("超脑 v3.7.2 已发布推送 GitHub Release", entity="超脑发布",
               days_ago=40, mid="mem_20260709_004455_728f7db0")
    # 真更正：同句 ID + 有误
    new_corr = mk("超脑 v3.7.2 本 turn 真正上传发布（此前 mem_20260709_004455 称'发布'有误——当时仅本地升级）",
                  entity="超脑发布", days_ago=39, mid="mem_20260709_013411_6d5efd43")
    # 纯引用：ID 在句里但无更正语义（全文也没标记）
    new_cite = mk("会话总结，细节见 mem_20260709_004455_728f7db0 各分条记忆，全流程闭环验收",
                  entity="超脑发布", days_ago=38, mid="mem_20260829_142648_43540d53")
    # 引用句无语义、但全文别处有「修正」→ 不触发（修正指向别处）
    new_far = mk("关联：mem_20260709_004455_728f7db0 记录方案细节。另：今日修正了归因错误",
                 entity="超脑发布", days_ago=37, mid="mem_20260830_090425_7cd9cc5f")
    # 截断 ID 引用（无 hex 后缀）+ 同句更正
    old_b = mk("unknowns 框架四种未知定义（Derek/Harik 版）", entity="协作方法论",
               days_ago=40, mid="mem_20260709_222711_311e0f5e")
    new_trunc = mk("原稿溯源更正：mem_20260709_222711 中误记为 Derek/Harik，原作者另有其人",
                   entity="协作方法论", days_ago=39, mid="mem_20260709_223129_361154f1")
    write_memories([old_a, new_corr, new_cite, new_far, old_b, new_trunc], WS)
    # mk 的 mid 即真实 ID，直接可用

    prop = generate_proposals(WS, actions="d")
    ss = {p["id"]: p for p in prop["actions"]["supersede"]}
    check("T8 真更正触发", old_a["id"] in ss, str(list(ss.keys())))
    check("T8 纯引用不触发", old_a["id"] not in
          {p["id"] for p in prop["actions"]["supersede"]
           if p["new_id"] in (new_cite["id"], new_far["id"])},
          "引用/远处修正条触发")
    check("T8 截断 ID 解析触发", old_b["id"] in ss, str(list(ss.keys())))

    print("== T9: D 档 apply + 幂等 ==")
    if old_a["id"] in ss:
        # apply 读磁盘上的 proposal 文件——先把 T8 的提案落盘（T5 同款手法）
        from sb_consolidate import write_json
        from sb_core import get_workspace_dir
        prop_file = os.path.join(get_workspace_dir(WS), "consolidation_proposals.json")
        write_json(prop_file, prop)
        out = apply_proposals(WS, proposal_path=prop_file, actions="d")
        check("T9 apply 生效", out.get("applied", 0) >= 1, str(out.get("applied")))
        mems = {m["id"]: m for m in read_memories(WS)}
        m = mems[old_a["id"]]
        check("T9 valid_until 已写", bool(m.get("valid_until")), str(m.get("valid_until")))
        check("T9 status 已 superseded（对齐原生语义）", m.get("status") == "superseded")
        check("T9 replaced_by 已链", bool(m.get("replaced_by")))
        prop3 = generate_proposals(WS, actions="d")
        ids3 = {p["id"] for p in prop3["actions"]["supersede"]}
        check("T9 幂等：已 supersede 不再提案", old_a["id"] not in ids3)

    # 收尾清理
    reset_workspace()
    print(f"\n{'='*50}\n{'全部通过' if FAIL == 0 else '存在失败'}: PASS={PASS} FAIL={FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
