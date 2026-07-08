#!/usr/bin/env python3
"""
SuperBrain Obsidian Bidirectional Sync v3.7.3
Exports memory and graph data as Obsidian-compatible .md files with [[wikilinks]].

Design principles:
- Knowledge stays in ~/.workbuddy/super-brain/ (canonical source)
- Exported .md files are read-only views (reverse sync optional)
- [[wikilinks]] between memories mirror graph.json edges
- Auto-links to existing vault notes when entity/project names match

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import json
import re
import math
import random
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, read_graph, read_meta, get_timestamp, ensure_workspace, list_workspaces


class SafeWriteError(Exception):
    """Vault 写操作被安全护栏拦截时抛出。

    结构化异常：message 只描述原因与文件名，**绝不泄露绝对系统路径**，
    避免把 ~/.workbuddy 等敏感目录暴露到日志或 stderr。
    """

    def __init__(self, reason, filename=None):
        self.reason = reason
        self.filename = filename
        super().__init__(f"SafeWrite blocked: {reason}")


def safe_write_file(filepath, content, vault_root=None):
    """受控写文件：路径沙箱 + 越界拦截 + 禁止 shell。

    对齐 Obsidian Vote 的安全文件 API 思想——所有写入 vault 的操作
    走统一封装，禁止任意 Shell、路径越界、写入隐藏系统目录。

    - 目标路径必须落在 `vault_root/超脑记忆` 导出目录内，否则抛 SafeWriteError
    - 拒绝 `..` 路径遍历
    - 拒绝写入 `.obsidian` 等隐藏系统目录
    - 仅用 open() 直写，不调用任何 shell
    - 仅在导出目录内创建父目录

    返回写入的绝对路径。
    """
    vault_root = vault_root or DEFAULT_VAULT_PATH
    export_dir = os.path.join(vault_root, DEFAULT_EXPORT_DIR)
    abs_export = os.path.abspath(export_dir)

    # 拒绝路径遍历序列
    norm = os.path.normpath(filepath).replace("\\", "/")
    if ".." in norm.split("/"):
        raise SafeWriteError("path traversal ('..') not allowed", os.path.basename(filepath))

    abs_target = os.path.abspath(filepath)

    # 必须落在导出目录内（或恰为导出目录本身）
    if abs_target != abs_export and not abs_target.startswith(abs_export + os.sep):
        raise SafeWriteError("target outside Obsidian export directory", os.path.basename(filepath))

    # 拒绝写入隐藏/系统目录
    rel_parts = os.path.relpath(abs_target, abs_export).split(os.sep)
    if any(p.startswith('.') and p not in ('.',) for p in rel_parts):
        raise SafeWriteError("write into hidden/system directory denied", os.path.basename(filepath))

    parent = os.path.dirname(abs_target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(abs_target, 'w', encoding='utf-8') as f:
        f.write(content)
    return abs_target


# Default Obsidian vault path — use env var or fall back to the user's primary vault.
# 主库（"家"）= ~/ObsidianVault；OBSIDIAN_VAULT_PATH 仍可覆盖。
DEFAULT_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", os.path.expanduser("~/ObsidianVault"))
DEFAULT_EXPORT_DIR = "超脑记忆"

# Frontmatter field mapping: memory attributes → Obsidian frontmatter
FRONTMATTER_FIELDS = {
    "type": "sb_type",
    "entity": "sb_entity",
    "confidence": "sb_confidence",
    "source_session": "sb_source",
}

# Memory type → Obsidian tag prefix
TYPE_TAG_MAP = {
    "fact": "超脑/知识",
    "decision": "超脑/决策",
    "preference": "超脑/偏好",
    "event": "超脑/事件",
    "task": "超脑/任务",
    "relationship": "超脑/关联",
    "context": "超脑/上下文",
}


# Memory type → Obsidian callout type (obsidian-markdown 规范：按类型分色)
CALLOUT_TYPE_MAP = {
    "fact": "note",
    "decision": "info",
    "preference": "tip",
    "event": "warning",
    "task": "todo",
    "relationship": "question",
    "context": "quote",
}


def _render_callout(memory):
    """Render an Obsidian callout block for a memory's metadata.

    对齐 obsidian-markdown 规范：元数据用 callout 块（按 type 分色），
    而非裸 `> **类型**:` 纯文本行。callout 可被 Obsidian 原生渲染、
    被其他 agent 安全复用。
    """
    mem_type = memory.get("type", "fact")
    entity = memory.get("entity", "general")
    status = memory.get("status", "active")
    confidence = memory.get("confidence", 0)
    callout_type = CALLOUT_TYPE_MAP.get(mem_type, "note")
    return [
        f"> [!{callout_type}] 元数据",
        f"> **类型**: {mem_type} ｜ **实体**: `{entity}`",
        f"> **置信度**: {confidence:.2f} ｜ **状态**: {status}",
    ]


def get_vault_memory_dir(vault_path=None):
    """Get the export directory inside the Obsidian vault."""
    if vault_path is None:
        vault_path = DEFAULT_VAULT_PATH
    export_dir = os.path.join(vault_path, DEFAULT_EXPORT_DIR)
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


def sanitize_filename(text, max_len=60):
    """Convert a memory title to a safe Obsidian filename."""
    # Remove invalid filename characters
    safe = re.sub(r'[\\/:*?"<>|]', '', text)
    safe = safe.strip().strip('.')
    if not safe:
        safe = "untitled"
    if len(safe) > max_len:
        safe = safe[:max_len-3] + "..."
    return safe


def _build_frontmatter(memory):
    """Build YAML frontmatter for a memory."""
    fm = {"tags": [], "created": memory.get("timestamp", "")}
    
    mem_type = memory.get("type", "fact")
    tag = TYPE_TAG_MAP.get(mem_type, "超脑/其他")
    fm["tags"].append(tag)
    
    # Add category tag
    cat = memory.get("attributes", {}).get("content_category", "")
    if cat:
        fm["tags"].append(f"超脑/分类/{cat}")
    
    # Add custom tags
    custom_tags = memory.get("attributes", {}).get("tags", [])
    for t in custom_tags:
        fm["tags"].append(t)
    
    # Add key fields
    for mem_field, fm_field in FRONTMATTER_FIELDS.items():
        val = memory.get(mem_field, "")
        if val:
            fm[fm_field] = val
    
    # Status and confidence
    fm["sb_status"] = memory.get("status", "active")
    fm["sb_id"] = memory.get("id", "")
    fm["sb_confidence"] = memory.get("confidence", 0)
    fm["sb_access_count"] = memory.get("access_count", 0)
    
    if "valid_from" in memory and memory["valid_from"]:
        fm["sb_valid_from"] = memory["valid_from"]
    if "valid_until" in memory and memory["valid_until"]:
        fm["sb_valid_until"] = memory["valid_until"]
    
    return fm


def _format_frontmatter(fm):
    """Format YAML frontmatter as string."""
    lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            val_str = str(value).replace('"', '\\"')
            lines.append(f'{key}: "{val_str}"')
    lines.append("---")
    return "\n".join(lines)


def _build_wikilinks(memory, graph, vault_notes=None, all_memories=None):
    """
    Build [[wikilinks]] from multiple sources (priority order):

    1. Graph edges → explicit connections
    2. Entity cross-linking → other memories sharing the same entity field
    3. Tag community → memories with overlapping tags
    4. Entity → existing vault note auto-link
    5. Related nodes → explicit related_nodes field

    This ensures even memories without graph edges get connected via
    shared entities and tags (fixes v3.x+ ingest isolation bug).
    """
    mem_id = memory.get("id", "")
    links = set()

    # 1. Graph edges → wikilinks (explicit graph connections)
    for edge in graph.get("edges", {}).values():
        source = edge.get("source", "")
        target = edge.get("target", "")
        if source == mem_id and target:
            links.add(f"[[{_edge_to_note_title(target, graph)}]]")
        elif target == mem_id and source:
            links.add(f"[[{_edge_to_note_title(source, graph)}]]")

    # 2. Entity cross-linking: find other memories with same entity
    if all_memories:
        my_entity = memory.get("entity", "").strip()
        my_tags = set(t.strip() for t in memory.get("tags", []) if t.strip())
        my_type = memory.get("type", "")

        for other in all_memories:
            other_id = other.get("id", "")
            if other_id == mem_id or not other_id:
                continue
            other_entity = other.get("entity", "").strip()
            other_tags = set(t.strip() for t in other.get("tags", []) if t.strip())

            # Same entity → strong link
            if my_entity and other_entity and my_entity != "general":
                if my_entity.lower() == other_entity.lower():
                    other_title = _memory_to_note_title(other)
                    if other_title:
                        links.add(f"[[{other_title}]]")
                        continue  # skip tag check if already linked by entity

            # Overlapping tags → community link (only if no entity match)
            if my_tags and other_tags and not (my_entity and my_entity != "general"
                                                and my_entity.lower() == other_entity.lower()):
                overlap = my_tags & other_tags
                if len(overlap) >= 1 and len(overlap) >= min(len(my_tags), len(other_tags)) * 0.5:
                    other_title = _memory_to_note_title(other)
                    if other_title:
                        links.add(f"[[{other_title}]]")

    # 3. Entity → existing vault note auto-link (vault-level, not memory-level)
    entity = memory.get("entity", "")
    if entity and entity != "general" and vault_notes:
        for note_name in vault_notes:
            if entity.lower() in note_name.lower():
                links.add(f"[[{note_name}]]")

    # 4. Keyword fallback — for general/singleton entity memories
    #    that still share content overlap. Rescues ~70% of remaining orphans.
    if all_memories and len(links) == 0:
        my_kw = _extract_keywords(memory.get("content", ""))
        if my_kw:
            candidates = []
            for other in all_memories:
                other_id = other.get("id", "")
                if other_id == mem_id or not other_id:
                    continue
                other_kw = _extract_keywords(other.get("content", ""))
                if not other_kw:
                    continue
                overlap = my_kw & other_kw
                if overlap:
                    score = len(overlap) / min(len(my_kw), len(other_kw))
                    if score >= 0.3:
                        other_title = _memory_to_note_title(other)
                        if other_title:
                            candidates.append((score, other_title))
            candidates.sort(key=lambda x: -x[0])
            for score, title in candidates[:5]:
                links.add(f"[[{title}]]")

    # 5. Related nodes → wikilinks
    for related_id in memory.get("related_nodes", []):
        link_title = _edge_to_note_title(related_id, graph)
        if link_title:
            links.add(f"[[{link_title}]]")

    return sorted(links)


def _edge_to_note_title(node_id, graph):
    """Convert a graph node ID to a note title. Handles both list and dict node formats."""
    nodes = graph.get("nodes", {})
    if isinstance(nodes, dict):
        node = nodes.get(node_id, {})
    elif isinstance(nodes, list):
        node = next((n for n in nodes if n.get("id") == node_id), {})
    else:
        return ""
    label = node.get("label") or node.get("name", node_id)
    return sanitize_filename(label, 40)


def _memory_to_note_title(memory):
    """Convert a memory dict to its expected .md note filename."""
    date_str = memory.get("timestamp", "")[:10]
    mem_type = memory.get("type", "fact")
    content = memory.get("content", memory.get("title", "untitled"))
    title = sanitize_filename(content, 50)
    return f"{date_str}-{mem_type}-{title}"


def _extract_keywords(text):
    """Extract meaningful keywords for cross-memory matching.

    Uses simple Chinese 2-4 char chunks + English 3-char+ tokens,
    with stopword filtering. No external dependencies.
    """
    if not text:
        return set()
    STOP = {
        "的", "了", "是", "在", "有", "和", "与", "不", "这", "那",
        "我", "你", "他", "她", "它", "们", "个", "都", "会", "要",
        "就", "也", "能", "很", "还", "更", "最", "又", "再", "把",
        "被", "让", "给", "从", "到", "对", "用", "以", "可", "可以",
        "没", "没有", "什么", "怎么", "怎样", "为什么", "如何",
        "因为", "所以", "但是", "虽然", "如果", "只有", "即使",
        "并且", "或", "但", "之", "及", "而", "于", "进行", "一个",
        "这个", "那个", "一些", "通过", "以及", "然后", "已经",
        "the", "and", "for", "with", "this", "that", "from",
        "are", "not", "but", "has", "its", "use", "all", "can",
    }
    words = set()
    text_lower = text.lower()
    # Chinese 2-4 char chunks
    for m in __import__("re").finditer(r"[\u4e00-\u9fff]{2,4}", text):
        w = m.group()
        if w not in STOP and len(w) >= 2:
            words.add(w)
    # English/CJK alphanumeric 3+ char tokens
    for m in __import__("re").finditer(r"[a-z0-9]{3,}", text_lower):
        w = m.group()
        if w not in STOP and len(w) >= 3:
            words.add(w)
    return words


def _scan_vault_notes(vault_path=None):
    """Scan Obsidian vault for existing note titles."""
    if vault_path is None:
        vault_path = DEFAULT_VAULT_PATH
    
    titles = set()
    if not os.path.isdir(vault_path):
        return titles
    
    for root, dirs, files in os.walk(vault_path):
        # Skip .obsidian and hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != DEFAULT_EXPORT_DIR]
        for f in files:
            if f.endswith('.md'):
                # Remove extension for note title
                titles.add(f[:-3])
    
    return titles


def export_to_obsidian(workspace=None, vault_path=None, include_graph=True):
    """
    Export all memories to Obsidian-compatible .md files.
    
    Generates:
    - One .md per memory (with frontmatter + wikilinks)
    - _INDEX.md (summary of all exported memories)
    
    Returns: dict with export statistics
    """
    memories = read_memories(workspace)
    graph = read_graph(workspace) if include_graph else {"nodes": [], "edges": []}
    meta = read_meta(workspace)
    vault_notes = _scan_vault_notes(vault_path)
    
    if not memories:
        return {"exported": 0, "message": "No memories to export"}
    
    active = [m for m in memories if m.get("status") == "active"]
    deprecated = [m for m in memories if m.get("status") == "deprecated"]
    
    export_dir = get_vault_memory_dir(vault_path)
    now = datetime.now(timezone.utc)
    
    exported = 0
    memory_index = []
    
    for memory in memories:
        content = memory.get("content", "No content")
        mem_id = memory.get("id", "")
        mem_type = memory.get("type", "fact")
        entity = memory.get("entity", "general")
        status = memory.get("status", "active")
        
        # Build filename
        date_str = memory.get("timestamp", "")[:10]
        title = sanitize_filename(content, 50)
        filename = f"{date_str}-{mem_type}-{title}.md"
        filepath = os.path.join(export_dir, filename)
        
        # Build frontmatter
        fm = _build_frontmatter(memory)
        
        # Build wikilinks (pass all memories for entity/tag cross-linking)
        wikilinks = _build_wikilinks(memory, graph, vault_notes, all_memories=memories)
        
        # Build file content
        lines = [_format_frontmatter(fm), ""]
        lines.append(f"# {content[:80]}")
        lines.append("")
        # Obsidian callout 元数据块（按 type 分色，obsidian-markdown 规范）
        lines.extend(_render_callout(memory))
        lines.append("")
        # 正文（带 block reference ^sb-content，供 Bases/跨文件引用锚定）
        lines.append(f"{content} ^sb-content")
        lines.append("")
        
        if wikilinks:
            lines.append("## 关联")
            for link in wikilinks:
                lines.append(f"- {link}")
        
        if memory.get("valid_from") or memory.get("valid_until"):
            lines.append("")
            lines.append("## 时效")
            if memory.get("valid_from"):
                lines.append(f"- 生效: {memory['valid_from']}")
            if memory.get("valid_until"):
                lines.append(f"- 失效: {memory['valid_until']}")
        
        lines.append("")
        lines.append(f"*由 Super Brain v3.7.3 自动生成 · {now.strftime('%Y-%m-%d %H:%M')}*")
        
        safe_write_file(filepath, "\n".join(lines), vault_path)
        
        exported += 1
        memory_index.append({
            "id": mem_id,
            "file": filename,
            "type": mem_type,
            "entity": entity,
            "status": status,
            "content_preview": content[:60]
        })
    
    # Write _INDEX.md
    index_lines = ["---", "tags: [超脑/_INDEX]", f"created: {now.isoformat()}", "---", ""]
    index_lines.append("# 超脑记忆索引")
    index_lines.append("")
    index_lines.append(f"> 导出时间: {now.strftime('%Y-%m-%d %H:%M')}")
    index_lines.append(f"> 工作区: {workspace or 'default'}")
    index_lines.append(f"> 记忆总数: {len(memories)} (活跃: {len(active)}, 已弃: {len(deprecated)})")
    index_lines.append("")
    
    # Group by type
    from collections import defaultdict
    by_type = defaultdict(list)
    for m in memory_index:
        by_type[m["type"]].append(m)
    
    for mtype, items in sorted(by_type.items()):
        lines = [f"## {mtype} ({len(items)})", ""]
        for item in items:
            status_mark = "~~" if item["status"] == "deprecated" else ""
            lines.append(f"- {status_mark}[[{item['file'][:-3]}]]{status_mark} — {item['content_preview']}")
        index_lines.extend(lines)
        index_lines.append("")
    
    index_lines.append("---")
    index_lines.append("*由 Super Brain v3.7.3 自动维护*")
    
    index_path = os.path.join(export_dir, "_INDEX.md")
    safe_write_file(index_path, "\n".join(index_lines), vault_path)
    
    # Count total wikilinks
    total_links = sum(wikilinks_per_memory(m.get("id", ""), graph) for m in memory_index)
    
    return {
        "exported": exported,
        "active": len(active),
        "deprecated": len(deprecated),
        "export_dir": export_dir,
        "vault_path": vault_path or DEFAULT_VAULT_PATH,
        "index": "_INDEX.md",
        "auto_linked_notes": total_links,
        "tip": f"Open '{vault_path or DEFAULT_VAULT_PATH}' as Obsidian vault to visualize the knowledge graph."
    }


def wikilinks_per_memory(mem_id, graph):
    """Count wikilinks for a memory (helper). Handles dict and list edge formats."""
    count = 0
    edges = graph.get("edges", {})
    if isinstance(edges, dict):
        for edge in edges.values():
            if edge.get("source") == mem_id or edge.get("target") == mem_id:
                count += 1
    elif isinstance(edges, list):
        for edge in edges:
            if isinstance(edge, dict) and (edge.get("source") == mem_id or edge.get("target") == mem_id):
                count += 1
    return count


def reverse_sync_from_obsidian(workspace=None, vault_path=None, dry_run=True):
    """
    Read .md files from vault and sync changes back to JSON.
    
    Only updates: confidence, status, and tags from frontmatter.
    Content updates require manual confirmation.
    
    Returns: dict with sync changes
    """
    export_dir = get_vault_memory_dir(vault_path)
    
    if not os.path.isdir(export_dir):
        return {"synced": 0, "message": "Export directory not found. Run export first."}
    
    memories = read_memories(workspace)
    id_map = {m["id"]: m for m in memories}
    
    changes = []
    
    for filename in os.listdir(export_dir):
        if not filename.endswith('.md') or filename == "_INDEX.md":
            continue
        
        filepath = os.path.join(export_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract frontmatter
        fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            continue
        
        # Parse frontmatter
        fm = {}
        for line in fm_match.group(1).split('\n'):
            if ':' in line:
                key, _, val = line.partition(':')
                key = key.strip()
                val = val.strip().strip('"')
                fm[key] = val
        
        mem_id = fm.get("sb_id", "")
        if not mem_id or mem_id not in id_map:
            continue
        
        memory = id_map[mem_id]
        changed = {}
        
        # Sync confidence
        new_conf = fm.get("sb_confidence", "")
        if new_conf and float(new_conf) != memory.get("confidence"):
            changed["confidence"] = {"from": memory["confidence"], "to": float(new_conf)}
        
        # Sync status
        new_status = fm.get("sb_status", "")
        if new_status and new_status != memory.get("status"):
            changed["status"] = {"from": memory["status"], "to": new_status}
        
        if changed and not dry_run:
            for field, change in changed.items():
                memory[field] = change["to"]
        
        if changed:
            changes.append({"id": mem_id, "file": filename, "changes": changed})
    
    if changes and not dry_run:
        from sb_core import write_memories
        write_memories(memories, workspace)
    
    return {
        "synced": len(changes),
        "dry_run": dry_run,
        "changes": changes
    }


def export_memory_as_card(memory, vault_path=None):
    """
    Export a single memory as one .md card file.
    Useful for incremental export after auto_store.
    
    Returns: dict with file info
    """
    graph = read_graph()
    vault_notes = _scan_vault_notes(vault_path)
    export_dir = get_vault_memory_dir(vault_path)

    content = memory.get("content", "No content")
    date_str = memory.get("timestamp", "")[:10]
    title = sanitize_filename(content, 50)
    filename = f"{date_str}-{memory.get('type', 'fact')}-{title}.md"
    filepath = os.path.join(export_dir, filename)

    fm = _build_frontmatter(memory)
    # Load all memories for entity/tag cross-linking
    from sb_memory import read_memories
    try:
        all_mems_data = read_memories()
        all_mems = all_mems_data if isinstance(all_mems_data, list) else all_mems_data.get("memories", [])
    except Exception:
        all_mems = []
    wikilinks = _build_wikilinks(memory, graph, vault_notes, all_memories=all_mems)
    
    lines = [_format_frontmatter(fm), ""]
    lines.append(f"# {content[:80]}")
    lines.append("")
    # Obsidian callout 元数据块（与 export_to_obsidian 一致）
    lines.extend(_render_callout(memory))
    lines.append("")
    # 正文（带 block reference ^sb-content）
    lines.append(f"{content} ^sb-content")
    
    if wikilinks:
        lines.append("")
        lines.append("## 关联")
        for link in wikilinks:
            lines.append(f"- {link}")
    
    safe_write_file(filepath, "\n".join(lines), vault_path)
    
    return {
        "exported": True,
        "file": filename,
        "path": filepath,
        "wikilinks": len(wikilinks)
    }


# 节点类别 → Obsidian canvas 预设色（"1".."6"）
CANVAS_NODE_COLOR = {
    "person": "1",
    "project": "2",
    "organization": "3",
    "tool": "4",
    "technology": "4",
    "concept": "5",
    "event": "6",
}

# canvas 图例展示的类别顺序
CANVAS_LEGEND_ORDER = ["person", "project", "organization", "tool", "concept", "technology", "event"]


def _node_size_by_degree(deg):
    """关联数越多，节点框越大（视觉突出枢纽）。"""
    if deg >= 5:
        return (340, 140)
    if deg >= 3:
        return (300, 120)
    if deg >= 1:
        return (260, 104)
    return (220, 90)


def _force_directed_layout(node_ids, edges, seed=42, iterations=400, width=3400.0, height=2400.0):
    """简易力导向布局（Fruchterman-Reingold），确定性（固定 seed）。

    相连的节点自动聚拢，无关节点自然分离——比环形布局更易读。
    返回 {nid: (x, y)}，坐标归一化到 [0, width] x [0, height]。
    """
    rng = random.Random(seed)
    n = max(1, len(node_ids))
    k = width / math.sqrt(n)  # 理想边长
    pos = {}
    for i, nid in enumerate(node_ids):
        ang = 2 * math.pi * i / n
        r = rng.uniform(0.85, 1.15)
        pos[nid] = [r * math.cos(ang) * k, r * math.sin(ang) * k]
    adj_edges = [(e.get("source", ""), e.get("target", "")) for e in edges
                 if e.get("source") in pos and e.get("target") in pos]
    temp = width / 10.0
    cool = temp / (iterations + 1)
    for _ in range(iterations):
        disp = {nid: [0.0, 0.0] for nid in node_ids}
        # 斥力：所有节点两两排斥
        for i in range(n):
            a = node_ids[i]
            for j in range(i + 1, n):
                b = node_ids[j]
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                dist = math.hypot(dx, dy) or 0.01
                rep = (k * k) / dist
                disp[a][0] += dx / dist * rep
                disp[a][1] += dy / dist * rep
                disp[b][0] -= dx / dist * rep
                disp[b][1] -= dy / dist * rep
        # 引力：边两端相互吸引
        for s, t in adj_edges:
            dx = pos[s][0] - pos[t][0]
            dy = pos[s][1] - pos[t][1]
            dist = math.hypot(dx, dy) or 0.01
            att = (dist * dist) / k
            disp[s][0] -= dx / dist * att
            disp[s][1] -= dy / dist * att
            disp[t][0] += dx / dist * att
            disp[t][1] += dy / dist * att
        # 按温度限制位移
        for nid in node_ids:
            d = math.hypot(disp[nid][0], disp[nid][1]) or 0.01
            lim = min(d, temp)
            pos[nid][0] += disp[nid][0] / d * lim
            pos[nid][1] += disp[nid][1] / d * lim
        temp -= cool
    # 归一化到 [0, width] x [0, height]
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    spanx = (maxx - minx) or 1.0
    spany = (maxy - miny) or 1.0
    scale = min(width / spanx, height / spany)
    out = {}
    for nid, (px, py) in pos.items():
        out[nid] = (int(round((px - minx) * scale)), int(round((py - miny) * scale)))
    return out


def _first_nonempty_graph():
    """当前 workspace 图为空时，回退到首个有节点数据的 workspace。"""
    for ws in list_workspaces():
        g = read_graph(ws)
        if g.get("nodes"):
            return g
    return {"nodes": {}, "edges": {}}


def export_graph_as_canvas(workspace=None, vault_path=None):
    """导出知识图谱 → Obsidian .canvas（json-canvas 规范，v3.7.2 记忆级增强版）。

    节点三类：
    1. 实体节点（graph.json）：按「类别」上色（person/project/...），按关联数定大小
    2. 主题节点（记忆 entity 去重）：每个主题一个文本节点，记忆环绕其聚成星系
    3. 记忆节点（每条记忆一个 file 节点，链对应 .md）：按记忆 type 上色

    边两类：
    - 实体间关系（uses/created/part_of/...，显示标签）
    - 记忆→主题（归属关系，每记忆连到自己的 entity 主题节点）

    布局：实体组件与记忆组件各自力导向后并排（双组件，避免大图交织）。
    左上角附标题 + 图例。
    """
    graph = read_graph(workspace)
    if not graph.get("nodes"):
        graph = _first_nonempty_graph()
    memories = read_memories(workspace)
    export_dir = get_vault_memory_dir(vault_path)

    # 记忆 type → canvas 预设色（1-6），与实体配色区分
    MEM_CANVAS_COLOR = {
        "fact": "4", "decision": "1", "preference": "3",
        "event": "2", "task": "5", "relationship": "4", "context": "4",
    }
    TOPIC_COLOR = "6"  # 记忆主题节点

    # --- 实体节点（graph.json）---
    raw_nodes = graph.get("nodes", {})
    if isinstance(raw_nodes, dict):
        entity_map = raw_nodes
    elif isinstance(raw_nodes, list):
        entity_map = {n.get("id", f"n{i}"): n for i, n in enumerate(raw_nodes)}
    else:
        entity_map = {}
    entity_ids = list(entity_map.keys())

    # --- 记忆节点 + 主题节点（按 entity 聚类）---
    mem_file_map = {}   # mid -> .md 文件名
    mem_type = {}       # mid -> type
    topic_nodes = {}    # tkey -> tid
    topic_orig = {}     # tkey -> 原始 entity 名
    mem_to_topic = []   # (mid, tid)
    for i, m in enumerate(memories):
        mid = m.get("id") or f"mem_{i}"
        mem_file_map[mid] = _memory_to_note_title(m) + ".md"
        mem_type[mid] = m.get("type", "fact")
        ent = (m.get("entity") or "未分类").strip() or "未分类"
        tkey = ent.lower()
        if tkey not in topic_nodes:
            topic_nodes[tkey] = f"topic_{len(topic_nodes)}"
            topic_orig[tkey] = ent
        mem_to_topic.append((mid, topic_nodes[tkey]))
    topic_ids = list(topic_nodes.values())

    # --- 边 ---
    raw_edges = graph.get("edges", {})
    if isinstance(raw_edges, dict):
        ent_edge_list = list(raw_edges.values())
    elif isinstance(raw_edges, list):
        ent_edge_list = raw_edges
    else:
        ent_edge_list = []
    ent_valid = [e for e in ent_edge_list
                 if e.get("source") in set(entity_ids) and e.get("target") in set(entity_ids)]
    mem_valid = [{"source": s, "target": t, "type": "about"} for s, t in mem_to_topic]
    all_edges = ent_valid + mem_valid

    # 度数（覆盖所有节点：实体 + 主题 + 记忆）
    deg = Counter()
    for e in all_edges:
        deg[e["source"]] += 1
        deg[e["target"]] += 1

    # --- 双组件布局（各自力导向后并排，避免交织）---
    layout_ent = _force_directed_layout(entity_ids, ent_valid, iterations=250)
    mem_comp_ids = topic_ids + list(mem_file_map.keys())
    layout_mem = _force_directed_layout(mem_comp_ids, mem_valid, iterations=250)
    ent_max_x = max((layout_ent[i][0] for i in entity_ids), default=0)
    MEM_OFF_X = ent_max_x + 760
    OFF_X, OFF_Y = 540, 280

    canvas_nodes = []
    # 实体节点
    for nid in entity_ids:
        n = entity_map[nid]
        name = n.get("name") or n.get("label") or nid
        ntype = n.get("type", "concept")
        color = CANVAS_NODE_COLOR.get(ntype, "6")
        w, h = _node_size_by_degree(deg[nid])
        canvas_nodes.append({
            "id": nid, "type": "text",
            "text": f"**{name}**\n_{ntype}_",
            "color": color,
            "x": layout_ent[nid][0] + OFF_X, "y": layout_ent[nid][1] + OFF_Y,
            "width": w, "height": h,
        })
    # 主题节点
    for tkey, tid in topic_nodes.items():
        w, h = _node_size_by_degree(deg[tid])
        canvas_nodes.append({
            "id": tid, "type": "text",
            "text": f"# {topic_orig.get(tkey, tkey)}",
            "color": TOPIC_COLOR,
            "x": layout_mem[tid][0] + MEM_OFF_X, "y": layout_mem[tid][1] + OFF_Y,
            "width": max(160, int(w * 0.7)), "height": max(56, int(h * 0.55)),
        })
    # 记忆节点（file，链 .md）
    for mid in mem_file_map:
        mtype = mem_type.get(mid, "fact")
        canvas_nodes.append({
            "id": mid, "type": "file", "file": mem_file_map[mid],
            "color": MEM_CANVAS_COLOR.get(mtype, "4"),
            "x": layout_mem[mid][0] + MEM_OFF_X, "y": layout_mem[mid][1] + OFF_Y,
            "width": 200, "height": 70,
        })

    # 边
    canvas_edges = []
    for i, e in enumerate(ent_valid):
        src, tgt = e["source"], e["target"]
        dx = layout_ent[tgt][0] - layout_ent[src][0]
        fs, ts = ("right", "left") if dx >= 0 else ("left", "right")
        label = e.get("type", "") or e.get("label", "") or ""
        canvas_edges.append({
            "id": f"eent-{i}", "fromNode": src, "toNode": tgt,
            "label": label, "fromSide": fs, "toSide": ts,
        })
    for i, (s, t) in enumerate(mem_to_topic):
        canvas_edges.append({
            "id": f"emem-{i}", "fromNode": s, "toNode": t,
            "label": "", "fromSide": "right", "toSide": "left",
        })

    # 标题 + 图例（左上角，避免与图重叠）
    canvas_nodes.append({
        "id": "legend_title", "type": "text",
        "text": (f"# 超脑记忆知识图谱\n{len(entity_ids)} 实体 · {len(topic_nodes)} 主题 · "
                 f"{len(mem_file_map)} 记忆\n\n色块=类别 · 框大=关联多 · 连线=关系/归属"),
        "x": 60, "y": 60, "width": 470, "height": 200, "color": "6",
    })
    ly = 300
    for ntype in CANVAS_LEGEND_ORDER:
        if any(n.get("type") == ntype for n in entity_map.values()):
            canvas_nodes.append({
                "id": f"legend_{ntype}", "type": "text",
                "text": f"**{ntype}**", "color": CANVAS_NODE_COLOR.get(ntype, "6"),
                "x": 60, "y": ly, "width": 220, "height": 54,
            })
            ly += 70
    canvas_nodes.append({"id": "legend_mem", "type": "text", "text": "■ 记忆(file)",
                         "color": "4", "x": 60, "y": ly, "width": 220, "height": 54}); ly += 70
    canvas_nodes.append({"id": "legend_topic", "type": "text", "text": "# 主题(记忆聚类)",
                         "color": TOPIC_COLOR, "x": 60, "y": ly, "width": 220, "height": 54})

    canvas = {"nodes": canvas_nodes, "edges": canvas_edges}
    canvas_path = os.path.join(export_dir, "知识图谱.canvas")
    safe_write_file(canvas_path, json.dumps(canvas, ensure_ascii=False, indent=2), vault_path)

    return {
        "exported": True,
        "canvas": "知识图谱.canvas",
        "path": canvas_path,
        "nodes": len(entity_ids) + len(topic_nodes) + len(mem_file_map),
        "edges": len(all_edges),
        "vault_path": vault_path or DEFAULT_VAULT_PATH,
    }


def get_obsidian_stats(workspace=None, vault_path=None):
    """Get Obsidian sync statistics."""
    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    export_dir = get_vault_memory_dir(vault_path)
    
    exported_files = []
    if os.path.isdir(export_dir):
        exported_files = [f for f in os.listdir(export_dir) if f.endswith('.md')]
    
    graph = read_graph(workspace)
    
    return {
        "total_memories": len(memories),
        "active_memories": len(active),
        "exported_files": len(exported_files),
        "graph_nodes": len(graph.get("nodes", [])),
        "graph_edges": len(graph.get("edges", [])),
        "vault_path": vault_path or DEFAULT_VAULT_PATH,
        "export_dir": export_dir,
        "synced": len(exported_files) >= len(memories)
    }
