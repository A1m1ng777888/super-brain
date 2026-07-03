#!/usr/bin/env python3
"""
SuperBrain Obsidian Bidirectional Sync v3.1.0
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
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_memories, read_graph, read_meta, get_timestamp, ensure_workspace


# Default Obsidian vault path — use env var or fall back to generic path
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


def _build_wikilinks(memory, graph, vault_notes=None):
    """
    Build [[wikilinks]] from graph edges.
    
    Also auto-links to existing vault notes when entity names match
    known note titles in the vault.
    """
    mem_id = memory.get("id", "")
    links = set()
    
    # 1. Graph edges → wikilinks
    for edge in graph.get("edges", []):
        source = edge.get("source", "")
        target = edge.get("target", "")
        if source == mem_id and target:
            links.add(f"[[{_edge_to_note_title(target, graph)}]]")
        elif target == mem_id and source:
            links.add(f"[[{_edge_to_note_title(source, graph)}]]")
    
    # 2. Entity → existing vault note auto-link
    entity = memory.get("entity", "")
    if entity and entity != "general" and vault_notes:
        for note_name in vault_notes:
            if entity.lower() in note_name.lower():
                links.add(f"[[{note_name}]]")
    
    # 3. Related nodes → wikilinks
    for related_id in memory.get("related_nodes", []):
        link_title = _edge_to_note_title(related_id, graph)
        if link_title:
            links.add(f"[[{link_title}]]")
    
    return sorted(links)


def _edge_to_note_title(node_id, graph):
    """Convert a graph node ID to a note title."""
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return sanitize_filename(node.get("label", node_id), 40)
    return ""


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
        
        # Build wikilinks
        wikilinks = _build_wikilinks(memory, graph, vault_notes)
        
        # Build file content
        lines = [_format_frontmatter(fm), ""]
        lines.append(f"# {content[:80]}")
        lines.append("")
        lines.append(f"> **类型**: {mem_type} | **实体**: `{entity}` | ")
        lines.append(f"> **置信度**: {memory.get('confidence', 0):.2f} | **状态**: {status}")
        lines.append("")
        lines.append(content)
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
        lines.append(f"*由 Super Brain v3.1.0 自动生成 · {now.strftime('%Y-%m-%d %H:%M')}*")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
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
    index_lines.append("*由 Super Brain v3.1.0 自动维护*")
    
    index_path = os.path.join(export_dir, "_INDEX.md")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(index_lines))
    
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
    """Count wikilinks for a memory (helper)."""
    count = 0
    for edge in graph.get("edges", []):
        if edge.get("source") == mem_id or edge.get("target") == mem_id:
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
    wikilinks = _build_wikilinks(memory, graph, vault_notes)
    
    lines = [_format_frontmatter(fm), ""]
    lines.append(f"# {content[:80]}")
    lines.append("")
    lines.append(content)
    
    if wikilinks:
        lines.append("")
        lines.append("## 关联")
        for link in wikilinks:
            lines.append(f"- {link}")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    
    return {
        "exported": True,
        "file": filename,
        "path": filepath,
        "wikilinks": len(wikilinks)
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
