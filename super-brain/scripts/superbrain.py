#!/usr/bin/env python3
"""
SuperBrain CLI - Unified entry point for the Super Brain skill.
Provides subcommands for memory, graph, search, selfcheck, workspace, and stats management.

Usage:
    python superbrain.py init
    python superbrain.py memory add --type fact --content "..." --entity "..."
    python superbrain.py memory list [--type TYPE] [--entity ENTITY] [--limit N]
    python superbrain.py memory search QUERY [--limit N]
    python superbrain.py memory update --id ID [--content TEXT] [--confidence FLOAT]
    python superbrain.py memory delete --id ID
    python superbrain.py memory merge --id1 ID --id2 ID
    python superbrain.py memory context QUERY [--limit N]
    python superbrain.py memory stats
    python superbrain.py graph add-node --name NAME --type TYPE [--aliases ...]
    python superbrain.py graph add-edge --source NAME --target NAME --type TYPE
    python superbrain.py graph query NAME [--depth N]
    python superbrain.py graph list [--type TYPE]
    python superbrain.py graph stats
    python superbrain.py graph delete --name NAME
    python superbrain.py selfcheck [--fix]
    python superbrain.py health
    python superbrain.py workspace list
    python superbrain.py workspace create --name NAME
    python superbrain.py workspace switch --name NAME
    python superbrain.py stats
    python superbrain.py version
"""

import sys
import os
import json
import argparse

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    load_config, save_config, ensure_workspace, list_workspaces,
    switch_workspace, print_json, print_table, get_timestamp,
    DEFAULT_DATA_DIR
)
from sb_memory import (
    add_memory, get_memory, list_memories, update_memory, delete_memory,
    merge_memories, search, get_context, get_stats as get_mem_stats,
    MEMORY_TYPES
)
from sb_graph import (
    add_node, add_edge, find_node, list_nodes, list_edges, query_graph,
    delete_node, get_stats as get_graph_stats, NODE_TYPES, EDGE_TYPES
)
from sb_selfcheck import (
    run_full_check, get_health_report, get_health_score
)


def cmd_init(args):
    """Initialize SuperBrain data directory and default workspace."""
    ensure_workspace("default")
    config = load_config()
    print("SuperBrain initialized successfully.")
    print(f"  Data directory: {config.get('data_dir', DEFAULT_DATA_DIR)}")
    print(f"  Current workspace: {config.get('current_workspace', 'default')}")
    print(f"  Version: {config.get('version', '1.0.0')}")
    print("\nWorkspace 'default' is ready. Use 'workspace create' to add more.")


def cmd_memory_add(args):
    """Add a new memory."""
    attrs = {}
    if args.category:
        attrs["category"] = args.category
    if args.scope:
        attrs["scope"] = args.scope
    if args.tags:
        attrs["tags"] = args.tags.split(",") if isinstance(args.tags, str) else args.tags

    memory = add_memory(
        content=args.content,
        mem_type=args.type,
        entity=args.entity,
        confidence=args.confidence,
        source=args.source,
        attributes=attrs if attrs else None,
        tags=args.tags.split(",") if args.tags else None
    )
    print(f"Memory added: {memory['id']}")
    print_json(memory)


def cmd_memory_list(args):
    """List memories with filters."""
    memories = list_memories(
        mem_type=args.type,
        entity=args.entity,
        status=args.status,
        limit=args.limit,
        sort=args.sort
    )
    if args.json:
        print_json(memories)
    else:
        print(f"Found {len(memories)} memories:")
        print_table(memories, ["id", "type", "entity", "content", "confidence", "timestamp"])


def cmd_memory_get(args):
    """Get a single memory by ID."""
    memory = get_memory(args.id)
    if memory:
        print_json(memory)
    else:
        print(f"Memory not found: {args.id}")
        sys.exit(1)


def cmd_memory_search(args):
    """Search memories."""
    results = search(args.query, limit=args.limit)
    if not results:
        print("No matching memories found.")
        return

    print(f"Found {len(results)} matching memories:")
    for mem, score, match_type in results:
        print(f"\n  [{match_type}] Score: {score:.3f} | ID: {mem['id']}")
        print(f"  Type: {mem['type']} | Entity: {mem['entity']} | Confidence: {mem['confidence']}")
        print(f"  Content: {mem['content']}")
        print(f"  Timestamp: {mem.get('timestamp', 'N/A')}")


def cmd_memory_update(args):
    """Update a memory."""
    attrs = None
    if args.category:
        attrs = {"category": args.category}

    updated = update_memory(
        args.id,
        content=args.content,
        confidence=args.confidence,
        status=args.status,
        attributes=attrs
    )
    if updated:
        print(f"Memory updated: {updated['id']}")
        print_json(updated)
    else:
        print(f"Memory not found: {args.id}")
        sys.exit(1)


def cmd_memory_delete(args):
    """Delete a memory."""
    if delete_memory(args.id):
        print(f"Memory deleted: {args.id}")
    else:
        print(f"Memory not found: {args.id}")
        sys.exit(1)


def cmd_memory_merge(args):
    """Merge two memories."""
    result = merge_memories(args.id1, args.id2)
    if result:
        print(f"Memories merged. Keeper: {result['id']}")
        print_json(result)
    else:
        print("Failed to merge memories. Check that both IDs exist.")
        sys.exit(1)


def cmd_memory_context(args):
    """Get context for injection."""
    ctx = get_context(args.query, limit=args.limit)
    print_json(ctx)


def cmd_memory_stats(args):
    """Show memory statistics."""
    stats = get_mem_stats()
    print_json(stats)


def cmd_graph_add_node(args):
    """Add a graph node."""
    aliases = args.aliases.split(",") if args.aliases else None
    node = add_node(
        name=args.name,
        node_type=args.type,
        aliases=aliases,
        attributes={"description": args.description} if args.description else None
    )
    print(f"Node added: {node['id']}")
    print_json(node)


def cmd_graph_add_edge(args):
    """Add a graph edge."""
    edge = add_edge(
        source_name_or_id=args.source,
        target_name_or_id=args.target,
        edge_type=args.type,
        weight=args.weight
    )
    print(f"Edge added: {edge['id']}")
    print_json(edge)


def cmd_graph_query(args):
    """Query the graph."""
    result = query_graph(args.name, depth=args.depth)
    print_json(result)


def cmd_graph_list(args):
    """List graph nodes or edges."""
    if args.edges:
        edges = list_edges(edge_type=args.type, limit=args.limit)
        print(f"Found {len(edges)} edges:")
        print_table(edges, ["id", "source", "target", "type", "weight"])
    else:
        nodes = list_nodes(node_type=args.type, limit=args.limit)
        print(f"Found {len(nodes)} nodes:")
        print_table(nodes, ["id", "name", "type", "updated_at"])


def cmd_graph_delete(args):
    """Delete a graph node."""
    if delete_node(args.name):
        print(f"Node deleted: {args.name}")
    else:
        print(f"Node not found: {args.name}")
        sys.exit(1)


def cmd_graph_stats(args):
    """Show graph statistics."""
    stats = get_graph_stats()
    print_json(stats)


def cmd_selfcheck(args):
    """Run self-check."""
    result = run_full_check(auto_fix=args.fix)
    print(f"\n=== SuperBrain Health Check ===")
    print(f"Overall Status: {result['overall_status'].upper()}")
    print(f"Total Issues: {result['total_issues']}")
    if args.fix:
        print(f"Auto-Fixed: {result['auto_fixed']}")
    print(f"Timestamp: {result['timestamp']}")
    print()
    for check_name, check in result["checks"].items():
        status_icon = "[OK]" if check["status"] == "healthy" else "[!]"
        print(f"  {status_icon} {check_name}: {check['issues_found']} issues")
        if check["status"] != "healthy" and check.get("details"):
            for detail in check["details"][:3]:
                print(f"      - {json.dumps(detail, ensure_ascii=False)[:120]}")
            if len(check["details"]) > 3:
                print(f"      ... and {len(check['details']) - 3} more")
    print(f"\n  Recommendation: {result['checks'].get('duplicates', {}).get('recommendation', '')}")


def cmd_health(args):
    """Show health score and latest report."""
    score = get_health_score()
    report = get_health_report()
    print(f"Health Score: {score}/100")
    print(f"Last Check: {report.get('timestamp', 'N/A')}")
    print(f"Status: {report.get('overall_status', 'unknown')}")
    print(f"Total Issues: {report.get('total_issues', 0)}")
    print()
    for check_name, check in report.get("checks", {}).items():
        status_icon = "[OK]" if check["status"] == "healthy" else "[!]"
        print(f"  {status_icon} {check_name}: {check['issues_found']} issues")


def cmd_workspace_list(args):
    """List workspaces."""
    config = load_config()
    current = config.get("current_workspace", "default")
    workspaces = list_workspaces()
    if not workspaces:
        print("No workspaces found. Run 'init' to create the default workspace.")
        return
    print(f"Current workspace: {current}")
    print(f"\nAll workspaces ({len(workspaces)}):")
    for ws in workspaces:
        marker = " *" if ws == current else ""
        print(f"  - {ws}{marker}")


def cmd_workspace_create(args):
    """Create a new workspace."""
    ensure_workspace(args.name)
    print(f"Workspace created: {args.name}")
    print(f"Switch to it with: workspace switch --name {args.name}")


def cmd_workspace_switch(args):
    """Switch workspace."""
    switch_workspace(args.name)
    print(f"Switched to workspace: {args.name}")


def cmd_stats(args):
    """Show overall statistics."""
    mem_stats = get_mem_stats()
    graph_stats = get_graph_stats()
    config = load_config()

    print("=== SuperBrain Statistics ===")
    print(f"Workspace: {config.get('current_workspace', 'default')}")
    print(f"Version: {config.get('version', '1.0.0')}")
    print()
    print(f"Memory:")
    print(f"  Total: {mem_stats['total']} | Active: {mem_stats['active']} | Archived: {mem_stats['archived']}")
    print(f"  Average Confidence: {mem_stats['avg_confidence']}")
    print(f"  Type Distribution: {json.dumps(mem_stats['type_distribution'], ensure_ascii=False)}")
    print(f"  Top Entities: {json.dumps(mem_stats.get('top_entities', {}), ensure_ascii=False)}")
    print()
    print(f"Knowledge Graph:")
    print(f"  Nodes: {graph_stats['total_nodes']} | Edges: {graph_stats['total_edges']}")
    print(f"  Orphan Nodes: {graph_stats['orphan_nodes']}")
    print(f"  Node Types: {json.dumps(graph_stats['node_types'], ensure_ascii=False)}")
    print(f"  Edge Types: {json.dumps(graph_stats['edge_types'], ensure_ascii=False)}")


def cmd_version(args):
    """Show version information."""
    config = load_config()
    print(f"SuperBrain version {config.get('version', '1.0.0')}")
    print(f"Release date: 2026-06-26")
    print(f"Data directory: {config.get('data_dir', DEFAULT_DATA_DIR)}")
    print(f"Current workspace: {config.get('current_workspace', 'default')}")


def build_parser():
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="SuperBrain - Cognitive enhancement system for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    sp = subparsers.add_parser("init", help="Initialize SuperBrain")
    sp.set_defaults(func=cmd_init)

    # memory
    sp_mem = subparsers.add_parser("memory", help="Memory engine operations")
    mem_sub = sp_mem.add_subparsers(dest="memory_command")

    # memory add
    sp = mem_sub.add_parser("add", help="Add a memory")
    sp.add_argument("--type", default="fact", choices=MEMORY_TYPES, help="Memory type")
    sp.add_argument("--content", required=True, help="Memory content")
    sp.add_argument("--entity", help="Primary entity name")
    sp.add_argument("--confidence", type=float, default=0.8, help="Confidence score (0-1)")
    sp.add_argument("--source", help="Source session identifier")
    sp.add_argument("--category", help="Category attribute")
    sp.add_argument("--scope", help="Scope attribute (global/project/workspace)")
    sp.add_argument("--tags", help="Comma-separated tags")
    sp.set_defaults(func=cmd_memory_add)

    # memory list
    sp = mem_sub.add_parser("list", help="List memories")
    sp.add_argument("--type", choices=MEMORY_TYPES, help="Filter by type")
    sp.add_argument("--entity", help="Filter by entity")
    sp.add_argument("--status", default="active", help="Filter by status")
    sp.add_argument("--limit", type=int, default=20, help="Max results")
    sp.add_argument("--sort", default="time", choices=["time", "confidence", "access"])
    sp.add_argument("--json", action="store_true", help="Output as JSON")
    sp.set_defaults(func=cmd_memory_list)

    # memory get
    sp = mem_sub.add_parser("get", help="Get a memory by ID")
    sp.add_argument("--id", required=True, help="Memory ID")
    sp.set_defaults(func=cmd_memory_get)

    # memory search
    sp = mem_sub.add_parser("search", help="Search memories")
    sp.add_argument("query", help="Search query")
    sp.add_argument("--limit", type=int, default=10, help="Max results")
    sp.set_defaults(func=cmd_memory_search)

    # memory update
    sp = mem_sub.add_parser("update", help="Update a memory")
    sp.add_argument("--id", required=True, help="Memory ID")
    sp.add_argument("--content", help="New content")
    sp.add_argument("--confidence", type=float, help="New confidence score")
    sp.add_argument("--status", choices=["active", "archived", "deprecated"], help="New status")
    sp.add_argument("--category", help="New category")
    sp.set_defaults(func=cmd_memory_update)

    # memory delete
    sp = mem_sub.add_parser("delete", help="Delete a memory")
    sp.add_argument("--id", required=True, help="Memory ID")
    sp.set_defaults(func=cmd_memory_delete)

    # memory merge
    sp = mem_sub.add_parser("merge", help="Merge two memories")
    sp.add_argument("--id1", required=True, help="First memory ID (keeper if higher confidence)")
    sp.add_argument("--id2", required=True, help="Second memory ID")
    sp.set_defaults(func=cmd_memory_merge)

    # memory context
    sp = mem_sub.add_parser("context", help="Get context for injection (token-optimized)")
    sp.add_argument("query", help="Context query")
    sp.add_argument("--limit", type=int, default=5, help="Max memories in context")
    sp.set_defaults(func=cmd_memory_context)

    # memory stats
    sp = mem_sub.add_parser("stats", help="Show memory statistics")
    sp.set_defaults(func=cmd_memory_stats)

    # graph
    sp_graph = subparsers.add_parser("graph", help="Knowledge graph operations")
    graph_sub = sp_graph.add_subparsers(dest="graph_command")

    # graph add-node
    sp = graph_sub.add_parser("add-node", help="Add a graph node")
    sp.add_argument("--name", required=True, help="Node name")
    sp.add_argument("--type", default="concept", choices=NODE_TYPES, help="Node type")
    sp.add_argument("--aliases", help="Comma-separated aliases")
    sp.add_argument("--description", help="Node description")
    sp.set_defaults(func=cmd_graph_add_node)

    # graph add-edge
    sp = graph_sub.add_parser("add-edge", help="Add a graph edge")
    sp.add_argument("--source", required=True, help="Source node name or ID")
    sp.add_argument("--target", required=True, help="Target node name or ID")
    sp.add_argument("--type", default="related_to", choices=EDGE_TYPES, help="Edge type")
    sp.add_argument("--weight", type=float, default=1.0, help="Edge weight")
    sp.set_defaults(func=cmd_graph_add_edge)

    # graph query
    sp = graph_sub.add_parser("query", help="Query graph from a node")
    sp.add_argument("name", help="Starting node name or ID")
    sp.add_argument("--depth", type=int, default=2, help="Traversal depth")
    sp.set_defaults(func=cmd_graph_query)

    # graph list
    sp = graph_sub.add_parser("list", help="List graph nodes or edges")
    sp.add_argument("--type", help="Filter by type")
    sp.add_argument("--limit", type=int, default=20, help="Max results")
    sp.add_argument("--edges", action="store_true", help="List edges instead of nodes")
    sp.set_defaults(func=cmd_graph_list)

    # graph delete
    sp = graph_sub.add_parser("delete", help="Delete a graph node")
    sp.add_argument("--name", required=True, help="Node name or ID")
    sp.set_defaults(func=cmd_graph_delete)

    # graph stats
    sp = graph_sub.add_parser("stats", help="Show graph statistics")
    sp.set_defaults(func=cmd_graph_stats)

    # selfcheck
    sp = subparsers.add_parser("selfcheck", help="Run self-diagnostics")
    sp.add_argument("--fix", action="store_true", help="Auto-fix safe issues")
    sp.set_defaults(func=cmd_selfcheck)

    # health
    sp = subparsers.add_parser("health", help="Show health score")
    sp.set_defaults(func=cmd_health)

    # workspace
    sp_ws = subparsers.add_parser("workspace", help="Workspace management")
    ws_sub = sp_ws.add_subparsers(dest="workspace_command")

    sp = ws_sub.add_parser("list", help="List workspaces")
    sp.set_defaults(func=cmd_workspace_list)

    sp = ws_sub.add_parser("create", help="Create a workspace")
    sp.add_argument("--name", required=True, help="Workspace name")
    sp.set_defaults(func=cmd_workspace_create)

    sp = ws_sub.add_parser("switch", help="Switch workspace")
    sp.add_argument("--name", required=True, help="Workspace name")
    sp.set_defaults(func=cmd_workspace_switch)

    # stats
    sp = subparsers.add_parser("stats", help="Show overall statistics")
    sp.set_defaults(func=cmd_stats)

    # version
    sp = subparsers.add_parser("version", help="Show version information")
    sp.set_defaults(func=cmd_version)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
