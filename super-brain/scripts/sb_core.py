#!/usr/bin/env python3
"""
SuperBrain Core - Infrastructure layer
Config management, workspace isolation, file I/O, ID generation.
"""

import json
import os
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
    "version": "3.0.0",
    "data_dir": DEFAULT_DATA_DIR,
    "current_workspace": "default",
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
    """Generate a unique ID with prefix."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
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
    """Save config to file."""
    ensure_dir(DEFAULT_DATA_DIR)
    config_path = os.path.join(DEFAULT_DATA_DIR, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_workspace_dir(workspace_name=None):
    """Get workspace directory path."""
    config = load_config()
    if workspace_name is None:
        workspace_name = config.get("current_workspace", "default")
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
    except (json.JSONDecodeError, IOError):
        return None


def write_json(path, data):
    """Write JSON file safely."""
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_memories(workspace=None):
    """Read all memories from workspace."""
    ws_dir = ensure_workspace(workspace)
    path = os.path.join(ws_dir, "memories.json")
    return read_json(path) or []


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
