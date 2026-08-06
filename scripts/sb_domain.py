#!/usr/bin/env python3
"""
SuperBrain Domain Glossary — 项目术语表（v3.9.8）

借鉴 mattpocock/skills 的 CONTEXT.md 共享语言模式：
  "CONTEXT.md should be totally devoid of implementation details.
   It is a glossary and nothing else."

核心设计：
  - 术语表只存「词汇 + 定义」，严禁混入实现细节/spec/草稿
  - 术语可标记歧义（flagged_ambiguities），记录同义词避用（avoid）
  - 支持当刻即写（capture as they happen）——术语一经确定立即落盘，不批量
  - 可导出为 CONTEXT.md（人读/agent 共享），或作为上下文注入
  - workspace 级隔离，随 workspace 存储

数据文件：<workspace>/glossary.json
  {
    "terms": { "term": {"definition": str, "status": str, "avoid": list[str], "updated_at": str} },
    "ambiguities": [ {"term": str, "conflict": str, "resolution": str, "resolved_at": str} ],
    "updated_at": str
  }

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import os
import sys

from sb_core import (
    get_timestamp, ensure_workspace, get_workspace_dir,
    read_json, write_json, generate_id
)

GLOSSARY_FILE = "glossary.json"

# 术语状态机
VALID_STATUS = {"proposed", "accepted", "deprecated"}


# ─── 存储层 ───────────────────────────────────────────────────────────────

def glossary_path(workspace=None):
    """返回 glossary.json 路径。"""
    ws_dir = ensure_workspace(workspace)
    return os.path.join(ws_dir, GLOSSARY_FILE)


def read_glossary(workspace=None):
    """读取术语表；不存在时返回空结构。"""
    data = read_json(glossary_path(workspace))
    if not isinstance(data, dict):
        data = {}
    data.setdefault("terms", {})
    data.setdefault("ambiguities", [])
    data.setdefault("updated_at", None)
    return data


def write_glossary(data, workspace=None):
    """原子写术语表。"""
    data["updated_at"] = get_timestamp()
    write_json(glossary_path(workspace), data)
    return data


# ─── 术语操作 ─────────────────────────────────────────────────────────────

def add_term(term, definition, status="accepted", avoid=None, workspace=None):
    """新增/更新术语。

    纪律（mattpocock CONTEXT.md）：
      - definition 只写领域含义，禁止实现细节
      - avoid: 同义词/被弃用说法列表（agent 应避免使用）
    """
    term = term.strip()
    if not term:
        raise ValueError("术语不能为空")
    if status not in VALID_STATUS:
        raise ValueError(f"status 必须是 {sorted(VALID_STATUS)} 之一，收到 {status!r}")
    data = read_glossary(workspace)
    data["terms"][term] = {
        "definition": definition.strip(),
        "status": status,
        "avoid": [a.strip() for a in (avoid or []) if a.strip()],
        "updated_at": get_timestamp(),
    }
    write_glossary(data, workspace)
    return data["terms"][term]


def get_term(term, workspace=None):
    """查询单个术语。"""
    data = read_glossary(workspace)
    return data["terms"].get(term)


def list_terms(status=None, workspace=None):
    """列出术语；可按状态过滤，按名称排序。"""
    data = read_glossary(workspace)
    terms = data["terms"]
    if status:
        terms = {k: v for k, v in terms.items() if v.get("status") == status}
    return dict(sorted(terms.items()))


def remove_term(term, workspace=None):
    """删除术语。返回是否删除成功。"""
    data = read_glossary(workspace)
    existed = term in data["terms"]
    if existed:
        del data["terms"][term]
        write_glossary(data, workspace)
    return existed


# ─── 歧义标记 ─────────────────────────────────────────────────────────────

def flag_ambiguity(term, conflict, resolution, workspace=None):
    """记录术语歧义与消解方案。

    对应 mattpocock CONTEXT.md 的 Flagged ambiguities 段：
      - conflict: 术语被两种含义混用的描述
      - resolution: 最终裁定（保留哪个含义 / 拆分术语）
    """
    data = read_glossary(workspace)
    entry = {
        "id": generate_id("amb"),
        "term": term,
        "conflict": conflict,
        "resolution": resolution,
        "resolved_at": get_timestamp(),
    }
    data["ambiguities"].append(entry)
    write_glossary(data, workspace)
    return entry


def list_ambiguities(workspace=None):
    """列出所有歧义记录。"""
    data = read_glossary(workspace)
    return data.get("ambiguities", [])


# ─── 导出 ─────────────────────────────────────────────────────────────────

def export_context_md(workspace=None, include_ambiguities=True):
    """导出 CONTEXT.md 文本（人读/agent 共享格式）。

    结构镜像 mattpocock CONTEXT.md：
      1. 一句话项目定位（若有）
      2. Language — 术语表（术语 + 定义 + 避用词）
      3. Relationships — 术语间关系（若有）
      4. Flagged ambiguities — 歧义消解记录
    """
    data = read_glossary(workspace)
    lines = ["# CONTEXT", ""]
    if data["terms"]:
        lines.append("## Language")
        for term, info in data["terms"].items():
            defn = info.get("definition", "")
            status = info.get("status", "accepted")
            avoid = info.get("avoid", [])
            if status == "deprecated":
                lines.append(f"~~{term}~~ (deprecated): {defn}")
            else:
                lines.append(f"**{term}**: {defn}")
            if avoid:
                lines.append(f"_Avoid_: {', '.join(avoid)}")
            lines.append("")
    if include_ambiguities and data.get("ambiguities"):
        lines.append("## Flagged ambiguities")
        for a in data["ambiguities"]:
            lines.append(f"- {a.get('term')} — {a.get('conflict')} → resolved: {a.get('resolution')}")
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    return text


def export_to_file(workspace=None, path=None):
    """导出 CONTEXT.md 到指定路径（默认 workspace 目录下）。"""
    text = export_context_md(workspace)
    if not path:
        ws_dir = ensure_workspace(workspace)
        path = os.path.join(ws_dir, "CONTEXT.md")
    write_json_like_text(path, text)
    return path


def write_json_like_text(path, text):
    """写文本文件（原子写，复用 write_json 的目录保障）。"""
    from sb_core import ensure_dir
    ensure_dir(os.path.dirname(path))
    tmp_path = f"{path}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp_path, path)
    return True


def get_glossary_stats(workspace=None):
    """术语表统计。"""
    data = read_glossary(workspace)
    terms = data.get("terms", {})
    status_counts = {}
    for info in terms.values():
        s = info.get("status", "accepted")
        status_counts[s] = status_counts.get(s, 0) + 1
    return {
        "term_count": len(terms),
        "status_counts": status_counts,
        "ambiguity_count": len(data.get("ambiguities", [])),
        "updated_at": data.get("updated_at"),
    }


# ─── CLI 入口（由 superbrain.py 调用）───────────────────────────────────

def cmd_domain(args):
    """分发 domain 子命令。"""
    sub = getattr(args, "domain_command", None)
    workspace = getattr(args, "workspace", None)

    if sub == "add":
        term = args.term
        definition = args.definition
        status = getattr(args, "status", "accepted") or "accepted"
        avoid = getattr(args, "avoid", None)
        avoid_list = avoid.split(",") if avoid else None
        result = add_term(term, definition, status=status, avoid=avoid_list, workspace=workspace)
        print(json_dumps({"status": "added", "term": term, "entry": result}))
    elif sub == "get":
        result = get_term(args.term, workspace=workspace)
        if result is None:
            print(json_dumps({"status": "not_found", "term": args.term}))
        else:
            print(json_dumps({"status": "ok", "term": args.term, "entry": result}))
    elif sub == "list":
        status = getattr(args, "status", None)
        result = list_terms(status=status, workspace=workspace)
        print(json_dumps({"status": "ok", "terms": result}))
    elif sub == "remove":
        removed = remove_term(args.term, workspace=workspace)
        print(json_dumps({"status": "removed" if removed else "not_found", "term": args.term}))
    elif sub == "ambiguity":
        entry = flag_ambiguity(args.term, args.conflict, args.resolution, workspace=workspace)
        print(json_dumps({"status": "flagged", "entry": entry}))
    elif sub == "ambiguities":
        result = list_ambiguities(workspace=workspace)
        print(json_dumps({"status": "ok", "ambiguities": result}))
    elif sub == "export":
        path = getattr(args, "path", None)
        out_path = export_to_file(workspace=workspace, path=path)
        print(json_dumps({"status": "exported", "path": out_path}))
    elif sub == "stats":
        print(json_dumps(get_glossary_stats(workspace=workspace)))
    else:
        print("Usage: SB domain {add|get|list|remove|ambiguity|ambiguities|export|stats}", file=sys.stderr)
        sys.exit(1)


def json_dumps(obj):
    """统一 JSON 输出（与 superbrain.py print_json 风格一致）。"""
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)
