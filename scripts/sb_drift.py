#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sb_drift.py — 超脑记忆漂移四态检测（只读）

【设计定位 · 必读】
本模块严格遵循「程序管治理，模型管语义」分工（借自 AOCI-CODE）：
  - **程序只报告客观事实的存在**：某个路径在磁盘上不存在、某个实体在 graph 里没有节点、
    某个记忆没有 provenance 基线。这些都是 os.path.exists / 集合差集能给出确定答案的事。
  - **程序绝不判断语义对错**：不猜「这条记忆是不是过时了」「这个结论是否还成立」。
    判定口径一律输出为「待人工确认」，最终裁决权在人。
  - **只读**：本脚本不写 memories.json / graph.json / index.json，一个字节都不改。

【四态映射（对话记忆版）】
AOCI 原四态 → 超脑口径：

  1) STALE（过期风险）
     - stale_path  : 记忆正文引用的仓库内文件路径，在磁盘上不存在
     - stale_ref   : 记忆的 replaced_by / replaces 指向已非 active 或不存在的一方
     - stale_valid : valid_until 已早于今天
     注意：路径不存在可能是①真的删了/移动了 ②写法错（双斜杠、占位符如 X.Y.Z）
           ③历史快照记忆（当时存在，现在归档）。故一律标「待人工确认」。

  2) ORPHAN（孤儿）
     - orphan_entity : 记忆的 entity 在 graph.json 中无对应节点（name/aliases 均不匹配）
     - orphan_node   : graph 节点无任何 related_memories（空挂节点）
     - orphan_edge   : 边的 source/target 指向不存在的节点

  3) MISSING（应有未有）
     - missing_entity : 与 orphan_entity 同一事实的反向表述——高频实体（≥阈值条记忆）
                        却没有图谱节点，意味着「该建节点而未建」
     - missing_file   : 记忆正文提到「产出/报告已落地 <路径>」但文件不存在
                        （只对含“落地/产出/归档/已写入”等产出动词的记忆检查，降低误报）

  4) UNBASELINED（未基线化）
     - unbaselined_no_provenance : provenance 字段缺失
     - unbaselined_inferred      : provenance == "inferred"（系统推断，非用户陈述/非核实）

【重要发现（2026-10-20 首次实测）】
  confidence 字段无区分度：992 条 active 中 median=0.9、min=0.6、仅 1 条 <0.7。
  它不承载可信度信息 → 判断记忆可信度必须看 provenance，不看 confidence。

用法：
  python sb_drift.py                          # 人读报告（当前工作空间）
  python sb_drift.py --json                   # JSON 输出
  python sb_drift.py --workspace "my-workspace"
  python sb_drift.py --limit 20               # 每态最多列 20 条
  python sb_drift.py --out report.md          # 同时写 markdown 报告
  python sb_drift.py --repo-root /path/to/your/repo   # 路径存在性检查基准

退出码：0=无漂移 / 1=存在漂移（供 cron/守护消费）；--no-fail 恒退出 0。
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date

# 允许被当作脚本直接跑，复用 sb_core 的路径与读写工具
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sb_core import get_workspace_dir, read_json, load_config
except Exception as exc:  # pragma: no cover - 环境缺失时给出明确提示
    sys.stderr.write(f"[sb_drift] 无法导入 sb_core: {exc}\n")
    raise

# ---------------------------------------------------------------------------
# 常量与口径
# ---------------------------------------------------------------------------

# 记忆正文里可能出现的仓库内顶级目录（用于限制正则范围，避免把网址/系统路径当仓库路径）
REPO_TOP_DIRS = [
    "本地知识库v1", "工具与产物", "超脑历史版本", "砚之身", "人格补全计划",
    "Kindle改造项目", "super-brain-remotion", "TencentDB-Agent-Memory",
    "鸿蒙开发工具", "超脑-Codex集成", "superbrain-mcp", "emilkowalski-skills",
    "goutoujunshi", "备份", "书籍译制", "外部协助", "AAA考试专用", "AAA旅行专用",
]

# 路径提取：形如 本地知识库v1/项目档案/xxx.md
PATH_RE = re.compile(
    r"((?:" + "|".join(map(re.escape, REPO_TOP_DIRS)) + r")"
    r"[A-Za-z0-9_\u4e00-\u9fff\.\-/]*)"
    r"\.(?:md|py|json|html|zip|txt|js|ts|css|pdf|png|jpg|bat|ps1|sh)"
)

# 占位符/明显非真实文件名（判为写法问题，不算真过期）
PLACEHOLDER_RE = re.compile(r"(X\.Y\.Z|<[^>]+>|\{[^}]+\}|\*|xxx|XXX)")

# 产出类动词：只有当记忆声称「文件已落地」时，文件缺失才算 MISSING
DELIVERY_RE = re.compile(r"(已落地|已写入|已归档|已生成|已产出|产出[:：]|报告在|详见|输出到)")

LOW_VOLUME_ENTITY = 2  # missing_entity 的最小记忆条数阈值


def _load(workspace=None):
    """读取三项数据：memories / graph / index。全部只读。"""
    ws_dir = get_workspace_dir(workspace)
    mem_path = os.path.join(ws_dir, "memories.json")
    graph_path = os.path.join(ws_dir, "graph.json")
    index_path = os.path.join(ws_dir, "index.json")

    # sb_core.read_json(path) 在文件缺失/解析失败时返回 None，故统一做 None 兜底
    raw_mem = read_json(mem_path) or []
    if isinstance(raw_mem, dict):
        raw_mem = raw_mem.get("memories") or raw_mem.get("items") or []
    graph = read_json(graph_path) or {"nodes": {}, "edges": {}}
    index = read_json(index_path) or {}
    return ws_dir, raw_mem, graph, index, index_path


def _node_name_map(nodes):
    """node name/alias → node id 的反查表。"""
    name_map = {}
    for nid, node in nodes.items():
        name = node.get("name")
        if name:
            name_map.setdefault(name, nid)
        for alias in node.get("aliases") or []:
            if alias:
                name_map.setdefault(alias, nid)
    return name_map


def _resolve_candidates(raw_path, repo_root):
    """把记忆里的相对路径还原为「多个候选绝对路径」。

    超脑记忆的路径基准并不统一，实测存在三种写法（2026-10-20 实证）：
      A. 仓库根基准：    tools/README.md        → <repo>/tools/README.md
      B. vault 基准：    vault/docs/x.md        → <repo>/vault/docs/x.md
      C. 混合错写：      vault/tools/x             → 根下不存在，vault 下也不存在

    因此绝不能只用单一基准判定「文件不存在」——那是测量工具的错误，不是被测对象的错误。
    这里返回候选列表，任一命中即视为存在，并回报命中的基准名，便于分析口径漂移。
    """
    p = raw_path.replace("\\", "/")
    p = re.sub(r"/{2,}", "/", p).strip().strip("/")

    candidates = []
    # 基准 1：仓库根，原样拼接
    candidates.append(("repo_root", os.path.join(repo_root, p.replace("/", os.sep))))
    # 基准 2：仓库根 + vault 子目录（处理「本地知识库v1/xxx」被误当 vault 内路径的情况）
    vault = os.path.join(repo_root, "本地知识库v1")
    if os.path.isdir(vault):
        candidates.append(("vault_as_root", os.path.join(vault, p.replace("/", os.sep))))
    # 基准 3：剥掉重复的「本地知识库v1/」前缀后，在仓库根下解析
    stripped = re.sub(r"^(本地知识库v1/)+", "", p)
    if stripped != p:
        candidates.append(("repo_root_stripped", os.path.join(repo_root, stripped.replace("/", os.sep))))
        if os.path.isdir(vault):
            candidates.append(("vault_stripped", os.path.join(vault, stripped.replace("/", os.sep))))
    return candidates


def _first_existing(raw_path, repo_root):
    """返回 (是否存在, 命中基准名, 命中的绝对路径)。"""
    for basis, abs_path in _resolve_candidates(raw_path, repo_root):
        if os.path.exists(abs_path):
            return True, basis, abs_path
    return False, None, None


def detect(workspace=None, repo_root=None, limit=10):
    """执行四态检测，返回结构化结果。纯读，无副作用。"""
    ws_dir, all_mem, graph, index, index_path = _load(workspace)
    nodes = graph.get("nodes") or {}
    edges = graph.get("edges") or {}

    if repo_root is None:
        # 默认基准优先级（不硬编码任何作者路径——发布物必须 path-free）：
        #   1) 环境变量 SUPERBRAIN_REPO_ROOT
        #   2) config.obsidian_vault_path 的父目录（vault 的上一层即仓库根）
        #   3) 当前工作目录
        # ⚠️ 第 2 条是必需的：sb_healthlite 调 detect() 时不传 repo_root，
        #    若退化为 cwd，守护在任意目录被触发都会把路径检查基准指错，
        #    实测 STALE 从 8 暴涨到 100（92 条假阳性，2026-10-20 v3.15.1 修复）。
        env_root = os.environ.get("SUPERBRAIN_REPO_ROOT")
        if env_root and os.path.isdir(env_root):
            repo_root = env_root
        else:
            vault = (load_config() or {}).get("obsidian_vault_path")
            derived = os.path.dirname(os.path.abspath(vault)) if vault else None
            repo_root = derived if (derived and os.path.isdir(derived)) else os.getcwd()

    active = [m for m in all_mem if m.get("status", "active") == "active"]
    active_ids = {m["id"] for m in active}
    all_ids = {m["id"] for m in all_mem}
    name_map = _node_name_map(nodes)

    state = {
        "meta": {
            "workspace": workspace or "(current)",
            "workspace_dir": ws_dir,
            "repo_root": repo_root,
            "generated_at": date.today().isoformat(),
            "memories_total": len(all_mem),
            "memories_active": len(active),
            "graph_nodes": len(nodes),
            "graph_edges": len(edges),
            "index_built_at": index.get("built_at"),
            "index_memory_count": index.get("memory_count"),
            "readonly": True,
        },
        "stale": {"stale_path": [], "stale_ref": [], "stale_valid": []},
        "orphan": {"orphan_entity": [], "orphan_node": [], "orphan_edge": []},
        "missing": {"missing_entity": [], "missing_file": []},
        "unbaselined": {"unbaselined_no_provenance": [], "unbaselined_inferred": []},
    }

    # ---- 索引新鲜度（不是四态之一，但同属漂移，必须报）----
    idx_count = index.get("memory_count")
    state["meta"]["index_lag"] = (len(active) - idx_count) if isinstance(idx_count, int) else None

    # ---- 1) STALE ----
    basis_counter = Counter()   # 命中基准统计：用于识别「路径口径漂移」
    basis_drift = []            # 命中非 repo_root 基准的条目（口径问题，非内容过期）
    for m in active:
        content = m.get("content") or ""
        for match in PATH_RE.finditer(content):
            raw = match.group(0)
            if PLACEHOLDER_RE.search(raw):
                # 占位符不算过期，但计入「写法异常」，交由人判断
                state["stale"]["stale_path"].append({
                    "memory_id": m["id"], "path": raw, "reason": "placeholder",
                    "verdict": "写法含占位符，非真实路径",
                })
                continue
            exists, basis, abs_path = _first_existing(raw, repo_root)
            if exists:
                basis_counter[basis] += 1
                if basis != "repo_root":
                    basis_drift.append({
                        "memory_id": m["id"], "path": raw, "matched_basis": basis,
                        "verdict": f"文件存在，但路径记法以「{basis}」为基准（与仓库根口径不一致）",
                    })
                continue
            reason = "not_found"
            if "//" in raw or re.search(r"^(本地知识库v1/)+本地知识库v1/", raw):
                reason = "malformed_path"
            state["stale"]["stale_path"].append({
                "memory_id": m["id"], "path": raw, "reason": reason,
                "verdict": "待人工确认（可能已删除/移动/写法错/历史快照；四种基准均未命中）",
            })

        # 替换链断裂
        for field in ("replaced_by", "replaces"):
            ref = m.get(field)
            if ref and ref not in all_ids:
                state["stale"]["stale_ref"].append({
                    "memory_id": m["id"], "field": field, "ref": ref,
                    "verdict": "引用了不存在的记忆 id",
                })
        rb = m.get("replaced_by")
        if rb and rb in all_ids:
            target = next((x for x in all_mem if x["id"] == rb), None)
            if target and target.get("status") != "active":
                state["stale"]["stale_ref"].append({
                    "memory_id": m["id"], "field": "replaced_by", "ref": rb,
                    "verdict": f"替代记忆状态为 {target.get('status')}，本条的继任者未生效",
                })

        # 有效期已过
        vu = m.get("valid_until")
        if vu and str(vu) < date.today().isoformat():
            state["stale"]["stale_valid"].append({
                "memory_id": m["id"], "valid_until": vu,
                "verdict": "有效期已过，应按时间语义复核",
            })

    # ---- 2) ORPHAN ----
    entity_counter = Counter(
        m.get("entity") for m in active if m.get("entity")
    )
    for ent, cnt in entity_counter.items():
        if ent not in name_map:
            state["orphan"]["orphan_entity"].append({
                "entity": ent, "memory_count": cnt,
                "verdict": "实体在 graph 中无节点（name/aliases 均未命中）",
            })

    for nid, node in nodes.items():
        if not node.get("related_memories"):
            state["orphan"]["orphan_node"].append({
                "node_id": nid, "name": node.get("name"),
                "verdict": "节点无任何关联记忆（空挂）",
            })

    node_ids = set(nodes.keys())
    for eid, edge in edges.items():
        bad = []
        if edge.get("source") not in node_ids:
            bad.append("source")
        if edge.get("target") not in node_ids:
            bad.append("target")
        if bad:
            state["orphan"]["orphan_edge"].append({
                "edge_id": eid, "broken": bad,
                "verdict": "边端点不存在",
            })

    # ---- 3) MISSING ----
    for ent, cnt in entity_counter.items():
        if ent not in name_map and cnt >= LOW_VOLUME_ENTITY:
            state["missing"]["missing_entity"].append({
                "entity": ent, "memory_count": cnt,
                "verdict": f"高频实体（≥{LOW_VOLUME_ENTITY} 条记忆）但图谱无节点，应建而未建",
            })
    state["missing"]["missing_entity"].sort(key=lambda x: -x["memory_count"])

    for m in active:
        content = m.get("content") or ""
        if not DELIVERY_RE.search(content):
            continue
        for match in PATH_RE.finditer(content):
            raw = match.group(0)
            if PLACEHOLDER_RE.search(raw):
                continue
            exists, _basis, _abs = _first_existing(raw, repo_root)
            if not exists:
                state["missing"]["missing_file"].append({
                    "memory_id": m["id"], "path": raw,
                    "verdict": "记忆声称已产出/归档，但四种基准下均无此文件",
                })

    # ---- 路径口径漂移（不是四态之一，但属治理事实，单独成项）----
    state["path_basis"] = {
        "matched_by_basis": dict(basis_counter),
        "basis_drift": basis_drift[: limit or None],
        "basis_drift_total": len(basis_drift),
    }

    # ---- 4) UNBASELINED ----
    for m in active:
        prov = m.get("provenance")
        if not prov:
            state["unbaselined"]["unbaselined_no_provenance"].append({
                "memory_id": m["id"],
                "type": m.get("type"), "entity": m.get("entity"),
                "verdict": "无 provenance 字段，来源不可考",
            })
        elif prov == "inferred":
            state["unbaselined"]["unbaselined_inferred"].append({
                "memory_id": m["id"],
                "type": m.get("type"), "entity": m.get("entity"),
                "verdict": "系统推断（非用户陈述、未核实）",
            })

    # ---- 汇总计数 ----
    # path_basis 是「治理事实」而非四态之一，结构也不同（含 dict），汇总时单独跳过
    DRIFT_GROUPS = ("stale", "orphan", "missing", "unbaselined")
    summary = {}
    for group in DRIFT_GROUPS:
        buckets = state[group]
        summary[group] = {k: len(v) for k, v in buckets.items()}
        summary[group]["total"] = sum(len(v) for v in buckets.values())
    state["summary"] = summary
    state["has_drift"] = any(summary[g]["total"] > 0 for g in DRIFT_GROUPS)

    # ---- 截断展示（完整数据仍保留在 JSON 里由 --limit 0 控制）----
    if limit and limit > 0:
        for group in DRIFT_GROUPS:
            buckets = state[group]
            # 先固化 key 列表，避免边迭代边插入 *_truncated 触发 RuntimeError
            for key in [k for k in buckets.keys() if not k.endswith("_truncated")]:
                rows = buckets.get(key)
                if isinstance(rows, list) and len(rows) > limit:
                    buckets[key] = rows[:limit]
                    buckets[f"{key}_truncated"] = True

    return state


STATE_LABEL = {
    "stale": "① STALE 过期风险",
    "orphan": "② ORPHAN 孤儿",
    "missing": "③ MISSING 应有未有",
    "unbaselined": "④ UNBASELINED 未基线化",
}


def render_markdown(state):
    """人读报告。刻意把「口径」和「结论边界」写在最前面。"""
    meta = state["meta"]
    s = state["summary"]
    lines = []
    lines.append("# 超脑记忆漂移检测报告（read-only）")
    lines.append("")
    lines.append(f"- 生成时间：{meta['generated_at']}")
    lines.append(f"- 工作空间：`{meta['workspace_dir']}`")
    lines.append(f"- 路径检查基准：`{meta['repo_root']}`")
    lines.append(f"- 规模：memories {meta['memories_total']} 条（active {meta['memories_active']}）/ "
                 f"graph {meta['graph_nodes']} 节点 {meta['graph_edges']} 边")
    lines.append(f"- 索引：built_at `{meta['index_built_at']}`，memory_count `{meta['index_memory_count']}`"
                 + (f"，**滞后 {meta['index_lag']} 条**" if meta.get("index_lag") else "，已对齐"))
    lines.append("")
    lines.append("> **本报告只报事实，不判语义。** 每条都标「待人工确认」，"
                 "程序不替人裁决某条记忆是否真的过时。绿灯/红灯都不等于语义正确。")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 态 | 子类 | 数量 |")
    lines.append("|---|---|---|")
    for group in ("stale", "orphan", "missing", "unbaselined"):
        for key, val in s[group].items():
            if key == "total":
                continue
            lines.append(f"| {STATE_LABEL[group]} | {key} | {val} |")
        lines.append(f"| **{STATE_LABEL[group]}** | **小计** | **{s[group]['total']}** |")
    lines.append("")

    # 明细（展示条数受 --limit 限制，标题里的数字始终是真实总数）
    for group in ("stale", "orphan", "missing", "unbaselined"):
        lines.append(f"## {STATE_LABEL[group]}")
        lines.append("")
        for key, rows in state[group].items():
            if key == "total" or key.endswith("_truncated") or not rows:
                continue
            real_total = s[group].get(key, len(rows))
            shown = len(rows)
            lines.append(f"### {key}（真实 {real_total}，展示 {shown}）")
            lines.append("")
            for row in rows:
                parts = []
                for k, v in row.items():
                    if k == "verdict":
                        continue
                    parts.append(f"{k}=`{v}`")
                lines.append(f"- {row.get('verdict','')} — " + " · ".join(parts))
            if real_total > shown:
                lines.append(f"- …另有 {real_total - shown} 条（`--limit 0` 或 `--json` 取全量）")
            lines.append("")

    # ---- 路径口径漂移（治理事实，单独成节）----
    pb = state.get("path_basis") or {}
    if pb:
        lines.append("## ⚠ 路径口径漂移（非四态，但同属治理问题）")
        lines.append("")
        lines.append("记忆里的路径写法与仓库实际目录基准不一致。**文件没丢，是记法乱了。**")
        lines.append("")
        lines.append(f"- 各基准命中数：`{pb.get('matched_by_basis')}`")
        lines.append(f"- 口径漂移条目：**{pb.get('basis_drift_total', 0)}** 条")
        lines.append("")
        for row in (pb.get("basis_drift") or [])[:10]:
            lines.append(f"- {row['verdict']} — memory_id=`{row['memory_id']}` · path=`{row['path']}`")
        lines.append("")

    lines.append("## 口径说明")
    lines.append("")
    lines.append("- **confidence 不可用于判可信度**：实测 992 条 active 中 median=0.9，仅 1 条 <0.7，"
                 "该字段无区分度；真正承载来源的是 `provenance`（verified / inferred / 缺失）。")
    lines.append("- **路径存在性用四个基准交叉判定**（repo_root / vault_as_root / repo_root_stripped / "
                 "vault_stripped），任一命中即视为存在。只用单一基准会把「记法不统一」误报成「文件丢失」"
                 "——那是测量工具的错误，不是被测对象的错误。")
    lines.append("- **路径不存在 ≠ 记忆错误**：可能是真删除、真移动、写法错（双斜杠/占位符）、"
                 "或该记忆本就是「当时的事实快照」。")
    lines.append("- **实体未建节点 ≠ 必须建**：低价值实体（如 general）不值得建节点，"
                 "故 missing_entity 只对 ≥2 条记忆的实体报警。")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="超脑记忆漂移四态检测（只读）")
    ap.add_argument("--workspace", default=None, help="工作空间名，默认当前")
    ap.add_argument("--repo-root", default=None, help="路径存在性检查基准目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--limit", type=int, default=10, help="每子类最多保留条数（0=不限）")
    ap.add_argument("--out", default=None, help="同时写 markdown 报告到文件")
    ap.add_argument("--no-fail", action="store_true", help="恒退出 0（供交互使用）")
    args = ap.parse_args()

    state = detect(workspace=args.workspace, repo_root=args.repo_root, limit=args.limit)

    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        md = render_markdown(state)
        print(md)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(md)
            sys.stderr.write(f"[sb_drift] 报告已写入 {args.out}\n")

    if args.no_fail:
        return 0
    return 1 if state["has_drift"] else 0


if __name__ == "__main__":
    sys.exit(main())
