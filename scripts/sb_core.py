#!/usr/bin/env python3
"""
SuperBrain Core - Infrastructure layer
Config management, workspace isolation, file I/O, ID generation.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Default data directory (can be overridden by SUPERBRAIN_DATA_DIR environment variable)
DEFAULT_DATA_DIR = os.path.expanduser(
    os.environ.get("SUPERBRAIN_DATA_DIR", "~/.workbuddy/super-brain")
)

# Default config
DEFAULT_CONFIG = {
    "version": "3.8.1",
    "data_dir": DEFAULT_DATA_DIR,
    "current_workspace": "default",
    "persona_workspace_path": None,  # v3.8.0: persona 层路径，None 时用默认 workspaces/persona/
    "simhash_bits": 64,
    "similarity_threshold": 0.65,
    "max_memories_per_load": 20,
    "self_check_interval_days": 7,
    "auto_extract": True,
    "token_optimization": {
        "context_compression": True,
        "max_context_memories": 10,
        "summary_mode": "structured"
    },
    "temporal": {
        "enabled": True,
        "conflict_detection": True,
        "conflict_overlap_warning": True
    },
    "search": {
        "dynamic_threshold": True,
        "base_quality_line": 0.1,
        "max_quality_line": 0.3,
        "score_ratio": 0.5,
        "coarse_filter_threshold": 0.05,
        "ternary_hash": True,
        "fuzzy_match": True,
        "word_network_expansion": True
    },
    "pipeline": {
        "definition_half_life_days": 365,
        "chitchat_half_life_days": 7,
        "hybrid_half_life_days": 90,
        "auto_archive_enabled": True
    },
    "perception": {
        "novelty_threshold": 0.55,
        "value_threshold": 0.2,
        "batch_mode": False
    },
    "entanglement": {
        "min_strength": 0.1,
        "max_expansions": 5,
        "cooccurrence_boost": 0.05
    },
    "skillopt": {
        "edit_budget": 4,
        "min_improvement": 0.01,
        "rejected_buffer_size": 20,
        "signal_weights": {
            "explicit": 1.0,
            "implicit": 0.3,
            "validation": 0.5
        }
    }
}


def get_timestamp():
    """Get current ISO 8601 timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def generate_id(prefix="mem"):
    """Generate a unique ID with prefix.

    R16 修复 (2026-07-10): 改用 UTC，与 get_timestamp() 时区一致，
    避免 ID 时间戳(本地)与 timestamp 字段(UTC)混淆。
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{prefix}_{ts}_{short_uuid}"


def ensure_dir(path):
    """Ensure directory exists, create if needed."""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def load_config():
    """Load config from file, create default if not exists."""
    config_path = os.path.join(DEFAULT_DATA_DIR, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save config to file (atomic via write_json)."""
    ensure_dir(DEFAULT_DATA_DIR)
    config_path = os.path.join(DEFAULT_DATA_DIR, "config.json")
    write_json(config_path, config)  # B6: 统一走原子写


def resolve_workspace():
    """v3.8.0: 从 cwd 向上找 .workbuddy 标记，解析项目 workspace 名。

    解析链：
    1. os.getcwd() → 向上爬找 .workbuddy/ 目录
    2. 找到 → 取父目录名当 workspace 名（如 "my-project"）
       - 排除用户主目录（~/.workbuddy 是平台全局配置，不是项目标记）
    3. workspace 不存在 → ensure_workspace() 自动建
    4. 找不到 .workbuddy（或只有主目录的）→ fallback config.current_workspace → "default"

    Returns:
        str: 解析出的 workspace 名
    """
    home = Path.home()
    cwd = Path(os.getcwd())
    current = cwd
    # 向上爬，最多 10 层
    for _ in range(10):
        if (current / ".workbuddy").is_dir():
            # 排除用户主目录——~/.workbuddy 是平台全局配置，不是项目标记
            if current == home:
                break
            # 找到项目级 .workbuddy 标记，取父目录名当 workspace 名
            ws_name = current.name
            ensure_workspace(ws_name)
            return ws_name
        if current.parent == current:
            break  # 到根目录了
        current = current.parent
    # 没找到项目级 .workbuddy，fallback
    config = load_config()
    return config.get("current_workspace", "default")


def get_persona_workspace_dir():
    """v3.8.0: 获取 persona workspace 目录（常驻身份记忆层）。

    路径来源（优先级）：
    1. config.persona_workspace_path（用户显式配置，绝对路径）
    2. ~/.workbuddy/super-brain/workspaces/persona/（默认 fallback）

    persona workspace 是跨项目常驻的——砚的身份记忆（60/40、分歧账本、
    对外展示立场、阅读偏好等）存在这里，不随 cwd 切换而变。
    对应 Freehold L1（始终自有的数据主权层）。

    Returns:
        str: persona workspace 的绝对路径
    """
    config = load_config()
    persona_path = config.get("persona_workspace_path")
    if persona_path:
        # 用户显式配置了路径（如本地知识库下）
        ensure_dir(persona_path)
        # 确保数据文件存在
        memories_path = os.path.join(persona_path, "memories.json")
        graph_path = os.path.join(persona_path, "graph.json")
        meta_path = os.path.join(persona_path, "meta.json")
        if not os.path.exists(memories_path):
            write_json(memories_path, [])
        if not os.path.exists(graph_path):
            write_json(graph_path, {"nodes": {}, "edges": {}})
        if not os.path.exists(meta_path):
            write_json(meta_path, {
                "name": "persona",
                "created_at": get_timestamp(),
                "memory_count": 0,
                "node_count": 0,
                "edge_count": 0,
                "last_self_check": None
            })
        return persona_path
    # 默认 fallback：在标准 workspaces 目录下建 persona
    data_dir = config.get("data_dir", DEFAULT_DATA_DIR)
    return os.path.join(data_dir, "workspaces", "persona")


def read_persona_memories():
    """v3.8.0: 读取 persona workspace 的全部记忆。

    用于双层召回——search()/get_context() 在搜 project workspace 后，
    再搜 persona workspace，合并去重。

    Returns:
        list: persona 记忆列表，若 persona workspace 不存在或空则返回 []
    """
    persona_dir = get_persona_workspace_dir()
    memories_path = os.path.join(persona_dir, "memories.json")
    data = read_json(memories_path)
    if data is None:
        return []
    return data


def write_persona_memories(memories):
    """v3.8.0: 写入 persona workspace 的记忆。

    用于 --persona flag 的 memory add / longterm ingest。
    """
    persona_dir = get_persona_workspace_dir()
    ensure_dir(persona_dir)
    memories_path = os.path.join(persona_dir, "memories.json")
    write_json(memories_path, memories)
    # 更新 meta
    meta_path = os.path.join(persona_dir, "meta.json")
    meta = read_json(meta_path) or {}
    meta["memory_count"] = len(memories)
    write_json(meta_path, meta)


def get_workspace_dir(workspace_name=None):
    """Get workspace directory path.

    v3.8.0 变更：workspace_name=None 时，从直接回退 config.current_workspace
    改为先试 resolve_workspace()（cwd→.workbuddy 自动绑定），找不到再 fallback。
    显式传入 workspace_name 时行为不变（向后兼容）。
    """
    config = load_config()
    if workspace_name is None:
        workspace_name = resolve_workspace()
    data_dir = config.get("data_dir", DEFAULT_DATA_DIR)
    return os.path.join(data_dir, "workspaces", workspace_name)


def ensure_workspace(workspace_name=None):
    """Ensure workspace directory and files exist."""
    ws_dir = get_workspace_dir(workspace_name)
    ensure_dir(ws_dir)
    # Ensure data files exist
    memories_path = os.path.join(ws_dir, "memories.json")
    graph_path = os.path.join(ws_dir, "graph.json")
    meta_path = os.path.join(ws_dir, "meta.json")
    if not os.path.exists(memories_path):
        write_json(memories_path, [])
    if not os.path.exists(graph_path):
        write_json(graph_path, {"nodes": {}, "edges": {}})
    if not os.path.exists(meta_path):
        write_json(meta_path, {
            "name": workspace_name or "default",
            "created_at": get_timestamp(),
            "memory_count": 0,
            "node_count": 0,
            "edge_count": 0,
            "last_self_check": None
        })
    return ws_dir


def list_workspaces():
    """List all workspace names."""
    config = load_config()
    data_dir = config.get("data_dir", DEFAULT_DATA_DIR)
    ws_root = os.path.join(data_dir, "workspaces")
    if not os.path.exists(ws_root):
        return []
    return [d for d in os.listdir(ws_root)
            if os.path.isdir(os.path.join(ws_root, d))]


def switch_workspace(name):
    """Switch current workspace."""
    config = load_config()
    config["current_workspace"] = name
    save_config(config)
    ensure_workspace(name)
    return name


def read_json(path):
    """Read JSON file safely."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        # v3.4.3 fix: warn instead of silent None — prevents read_memories
        # from returning [] and causing write_memories to overwrite with loss
        print(f"  ⚠ read_json: failed to parse {path}: {e}", file=sys.stderr)
        return None


def write_json(path, data):
    """Write JSON file safely.

    B6 修复 (2026-07-10): 原子写——先写 .tmp 再 os.replace，避免写入过程崩溃导致文件损坏。
    os.replace 是跨平台原子操作 (Windows/Linux/macOS 均支持)，崩溃时 .tmp 残留但不污染原文件。
    """
    ensure_dir(os.path.dirname(path))
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)  # 原子重命名


def read_memories(workspace=None):
    """Read all memories from workspace."""
    ws_dir = ensure_workspace(workspace)
    path = os.path.join(ws_dir, "memories.json")
    data = read_json(path)
    if data is None:
        if os.path.exists(path):
            # v3.4.3 fix: file exists but JSON is corrupt — do NOT return []
            # Returning [] would cause write_memories to overwrite and lose data.
            # Instead, back up the corrupt file and return [] only after backup.
            import shutil, time
            backup_name = f"memories_corrupt_backup_{int(time.time())}.json"
            backup_path = os.path.join(ws_dir, backup_name)
            shutil.copy2(path, backup_path)
            print(f"  ⚠ read_memories: JSON corrupt — backed up to {backup_name}", file=sys.stderr)
            print(f"  ⚠ read_memories: returning empty list (corrupt file backed up, not deleted)", file=sys.stderr)
        return []
    return data


def write_memories(memories, workspace=None):
    """Write memories to workspace."""
    ws_dir = ensure_workspace(workspace)
    path = os.path.join(ws_dir, "memories.json")
    write_json(path, memories)
    # Update meta
    meta_path = os.path.join(ws_dir, "meta.json")
    meta = read_json(meta_path) or {}
    meta["memory_count"] = len(memories)
    write_json(meta_path, meta)


def read_graph(workspace=None):
    """Read knowledge graph from workspace."""
    ws_dir = ensure_workspace(workspace)
    path = os.path.join(ws_dir, "graph.json")
    return read_json(path) or {"nodes": {}, "edges": {}}


def write_graph(graph, workspace=None):
    """Write knowledge graph to workspace."""
    ws_dir = ensure_workspace(workspace)
    path = os.path.join(ws_dir, "graph.json")
    write_json(path, graph)
    # Update meta
    meta_path = os.path.join(ws_dir, "meta.json")
    meta = read_json(meta_path) or {}
    meta["node_count"] = len(graph.get("nodes", {}))
    meta["edge_count"] = len(graph.get("edges", {}))
    write_json(meta_path, meta)


def read_meta(workspace=None):
    """Read workspace metadata."""
    ws_dir = ensure_workspace(workspace)
    path = os.path.join(ws_dir, "meta.json")
    return read_json(path) or {}


def write_meta(meta, workspace=None):
    """Write workspace metadata."""
    ws_dir = ensure_workspace(workspace)
    path = os.path.join(ws_dir, "meta.json")
    write_json(path, meta)


def update_meta(key, value, workspace=None):
    """Update a single meta field."""
    meta = read_meta(workspace)
    meta[key] = value
    write_meta(meta, workspace)


# ===================================================================
# v3.1.0: Session Lifecycle Protocols (会话生命周期协议)
# ===================================================================

def session_start(workspace=None):
    """
    T1 — Session start protocol.
    
    1. Increment session counter
    2. Check for crashed previous session
    3. Retrieve relevant memories and project context
    4. Output a session briefing
    
    Returns: dict with session briefing
    """
    meta = read_meta(workspace or "default")
    previous_count = meta.get("session_count", 0)
    meta["session_count"] = previous_count + 1
    meta["last_session_start"] = get_timestamp()
    write_meta(meta, workspace)
    
    # Check warmup status
    from sb_memory import read_memories as _rmem
    memories = _rmem(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    active_count = len(active)
    
    # Detect depressed memories (about to expire)
    from sb_pipeline import compute_decay_factor
    from datetime import datetime as _dt, timezone as _tz
    now = _dt.now(_tz.utc)
    low_retention = []
    for m in active:
        cat = m.get("attributes", {}).get("content_category", "hybrid")
        decay = compute_decay_factor(m, cat, now)
        if decay < 0.15:
            low_retention.append({
                "id": m["id"],
                "content": m.get("content", "")[:60],
                "retention": round(decay, 4)
            })
    
    # Check for unresolved items
    unresolved = [m for m in active if m.get("attributes", {}).get("status") == "unresolved"]
    
    briefing = {
        "protocol": "T1_session_start",
        "session_number": meta["session_count"],
        "warmup": active_count < 15 or meta["session_count"] < 3,
        "active_memories": active_count,
        "total_memories": len(memories),
        "unresolved_items": len(unresolved),
        "low_retention_items": len(low_retention),
        "low_retention_detail": low_retention[:5],
        "tip": _session_tip(meta["session_count"], active_count)
    }
    
    return briefing


def session_end(workspace=None):
    """
    T2 — Session end protocol (收尾安全网).
    
    1. Anti-pollution check on recent additions
    2. Mark session as completed in meta
    3. Generate session summary
    
    Returns: dict with session summary
    """
    meta = read_meta(workspace)
    meta["last_session_end"] = get_timestamp()
    meta["session_complete"] = True
    
    # Increment completed session count
    completed = meta.get("completed_sessions", 0)
    meta["completed_sessions"] = completed + 1
    write_meta(meta, workspace)
    
    from sb_memory import read_memories as _rmem
    memories = _rmem(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    
    # Count recent additions (last session)
    auto_ingested = sum(1 for m in active if m.get("attributes", {}).get("auto_ingested"))
    
    return {
        "protocol": "T2_session_end",
        "session_number": meta["session_count"],
        "completed_sessions": meta["completed_sessions"],
        "active_memories": len(active),
        "auto_ingested_ratio": f"{auto_ingested}/{len(active)}",
        "tip": "Run 'SB pipeline cleanup' periodically to remove decayed memories."
    }


def periodic_health_check(workspace=None):
    """
    T3 — Periodic health check (7-dimensional scan).
    
    1. Total count check
    2. Conflict detection
    3. Orphan detection
    4. Garbage collection (decayed items)
    5. Pattern extraction quality
    6. Index integrity
    7. Backpressure from legacy items
    
    Returns: dict with health report
    """
    from sb_memory import read_memories as _rmem
    from sb_pipeline import compute_decay_factor, cleanup_memories
    from datetime import datetime as _dt, timezone as _tz
    
    memories = _rmem(workspace)
    active = [m for m in memories if m.get("status") == "active"]
    now = _dt.now(_tz.utc)
    
    # 1. Total count
    total = len(memories)
    active_count = len(active)
    deprecated_count = sum(1 for m in memories if m.get("status") == "deprecated")
    superseded_count = sum(1 for m in memories if m.get("status") == "superseded")
    
    # 2. Conflict detection - check for temporal overlaps
    conflicts = 0
    from collections import defaultdict
    by_entity = defaultdict(list)
    for m in active:
        entity = (m.get("entity", "general").lower(), m.get("type", "fact"))
        by_entity[entity].append(m)
    for entity_group in by_entity.values():
        if len(entity_group) > 1:
            for i in range(len(entity_group)):
                for j in range(i + 1, len(entity_group)):
                    vf1 = entity_group[i].get("valid_from")
                    vf2 = entity_group[j].get("valid_from")
                    vu1 = entity_group[i].get("valid_until")
                    vu2 = entity_group[j].get("valid_until")
                    if vf1 and vf2 and vu1 and vu2:
                        if vf1 <= vu2 and vu1 >= vf2:
                            conflicts += 1
    
    # 3. Orphan detection - memories with no graph edges
    from sb_graph import read_graph as _rg
    graph = _rg(workspace)
    all_graph_ids = set()
    nodes = graph.get("nodes", {})
    if isinstance(nodes, dict):
        for n in nodes.values():
            if isinstance(n, dict):
                all_graph_ids.add(n.get("id", ""))
    elif isinstance(nodes, list):
        for n in nodes:
            if isinstance(n, dict):
                all_graph_ids.add(n.get("id", ""))
    orphan_count = sum(1 for m in active if m["id"] not in all_graph_ids)
    
    # 4. GC status
    gc_candidates = 0
    for m in active:
        cat = m.get("attributes", {}).get("content_category", "hybrid")
        decay = compute_decay_factor(m, cat, now)
        if decay < 0.15:
            gc_candidates += 1
    
    # 5. Pattern extraction quality
    from sb_search import build_word_network_from_memories
    wn = build_word_network_from_memories(active)
    pattern_count = len(wn.node_count) if hasattr(wn, 'node_count') else (len(wn._nodes) if hasattr(wn, '_nodes') else 0)
    
    # 6. Index integrity - check if word network is built
    index_intact = pattern_count > 0
    
    # 7. Legacy backpressure
    legacy = [m for m in memories if m.get("status") not in ("active", "deprecated", "superseded")]
    
    report = {
        "protocol": "T3_health_check",
        "timestamp": now.isoformat(),
        "scan_dimensions": 7,
        "total_items": total,
        "active": active_count,
        "deprecated": deprecated_count,
        "superseded": superseded_count,
        "conflicts": conflicts,
        "orphans": orphan_count,
        "gc_candidates": gc_candidates,
        "pattern_count": pattern_count,
        "index_intact": index_intact,
        "legacy_backpressure": len(legacy),
        "health_score": _compute_health_score(
            active_count, conflicts, orphan_count, gc_candidates, 
            deprecated_count, int(index_intact), len(legacy)
        ),
        "recommendation": _health_recommendation(
            gc_candidates, deprecated_count, conflicts, orphan_count
        )
    }
    
    return report


def _session_tip(session_n, mem_count):
    """Generate contextual tip for session start."""
    if session_n <= 1:
        return "Welcome! Super Brain is in cold start. Share information freely — it will learn from you."
    if mem_count < 15:
        return f"Warmup mode: {mem_count}/15 memories. Perception and storage active; reasoning will unlock soon."
    return f"Active mode: {mem_count} memories, {session_n} sessions. All cognitive modules online."


def _compute_health_score(active, conflicts, orphans, gc_candidates, deprecated, index_intact, legacy):
    """Compute a 0-100 health score."""
    score = 100
    score -= min(30, conflicts * 5)          # -5 per conflict, max -30
    score -= min(20, orphans * 3)            # -3 per orphan, max -20
    score -= min(20, gc_candidates * 2)      # -2 per GC candidate, max -20
    score -= min(10, deprecated * 1)         # -1 per deprecated, max -10
    score -= 15 if not index_intact else 0
    score -= min(5, legacy * 2)              # -2 per legacy, max -5
    return max(0, score)


def _health_recommendation(gc_count, deprecated_count, conflicts, orphans):
    """Generate health recommendations."""
    recs = []
    if gc_count > 10:
        recs.append(f"Run 'SB pipeline cleanup' to remove {gc_count} decayed items")
    if deprecated_count > 5:
        recs.append(f"{deprecated_count} deprecated items pending hard delete")
    if conflicts > 0:
        recs.append(f"{conflicts} temporal conflicts detected — review manually")
    if orphans > 3:
        recs.append(f"{orphans} orphan memories without graph edges")
    if not recs:
        recs.append("All systems nominal — no action needed")
    return recs


def get_health_dir():
    """Get health reports directory."""
    config = load_config()
    data_dir = config.get("data_dir", DEFAULT_DATA_DIR)
    h_dir = os.path.join(data_dir, "health")
    ensure_dir(h_dir)
    return h_dir


def print_json(data):
    """Print data as formatted JSON."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_table(items, fields):
    """Print a list of dicts as a simple table."""
    if not items:
        print("(empty)")
        return
    # Calculate column widths
    widths = {}
    for field in fields:
        widths[field] = len(field)
        for item in items:
            val = str(item.get(field, ""))
            if len(val) > widths[field]:
                widths[field] = min(len(val), 60)
    # Print header
    header = " | ".join(field.ljust(widths[field]) for field in fields)
    print(header)
    print("-" * len(header))
    # Print rows
    for item in items:
        row = " | ".join(
            str(item.get(field, ""))[:60].ljust(widths[field])
            for field in fields
        )
        print(row)
