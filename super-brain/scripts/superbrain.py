#!/usr/bin/env python3
"""
SuperBrain CLI - Unified entry point for the Super Brain skill.
Provides subcommands for memory, graph, search, selfcheck, workspace, stats,
skillopt (self-evolution), and trace (execution recording) management.

Usage:
    # Core commands
    python superbrain.py init
    python superbrain.py version
    python superbrain.py stats

    # Memory engine
    python superbrain.py memory add --type fact --content "..." --entity "..."
    python superbrain.py memory list [--type TYPE] [--entity ENTITY] [--limit N]
    python superbrain.py memory search QUERY [--limit N]
    python superbrain.py memory update --id ID [--content TEXT] [--confidence FLOAT]
    python superbrain.py memory delete --id ID
    python superbrain.py memory merge --id1 ID --id2 ID
    python superbrain.py memory context QUERY [--limit N]
    python superbrain.py memory stats

    # Knowledge graph
    python superbrain.py graph add-node --name NAME --type TYPE [--aliases ...]
    python superbrain.py graph add-edge --source NAME --target NAME --type TYPE
    python superbrain.py graph query NAME [--depth N]
    python superbrain.py graph list [--type TYPE]
    python superbrain.py graph stats
    python superbrain.py graph delete --name NAME

    # Self-check and health
    python superbrain.py selfcheck [--fix]
    python superbrain.py health

    # Workspace management
    python superbrain.py workspace list
    python superbrain.py workspace create --name NAME
    python superbrain.py workspace switch --name NAME

    # SkillOpt self-evolution (v2.0.0+)
    python superbrain.py skillopt status
    python superbrain.py skillopt self-evolve --epochs 3
    python superbrain.py skillopt optimize --skill-path PATH --epochs 3
    python superbrain.py skillopt history
    python superbrain.py skillopt rejected

    # Execution trace recording (v2.0.0+)
    python superbrain.py trace record --command "memory add" --input '{"content": "..."}'
    python superbrain.py trace feedback --trace-id ID --rating satisfied
    python superbrain.py trace list [--limit N]
    python superbrain.py trace stats
    python superbrain.py trace export [--output PATH]
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
from sb_trace import (
    record_trace, add_explicit_feedback, get_traces, get_trace_stats,
    export_traces_for_skillopt
)
from sb_skillopt import (
    optimize_external_skill, self_evolve, get_optimization_history,
    get_rejected_buffer, rollback_skillopt, skillopt_status,
    get_default_validation_tasks
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
    print(f"Release date: 2026-06-27")
    print(f"Data directory: {config.get('data_dir', DEFAULT_DATA_DIR)}")
    print(f"Current workspace: {config.get('current_workspace', 'default')}")


# === SkillOpt Commands ===

def cmd_skillopt_optimize(args):
    """Optimize an external skill using SkillOpt."""
    import json as json_mod
    
    # Load validation tasks
    validation_tasks = None
    if args.validation_tasks:
        with open(args.validation_tasks, "r", encoding="utf-8") as f:
            validation_tasks = json_mod.load(f)
    
    result = optimize_external_skill(
        skill_path=args.skill_path,
        traces=[],  # TODO: load traces from file if provided
        validation_tasks=validation_tasks,
        epochs=args.epochs,
        workspace=args.workspace
    )
    
    print(f"\n=== SkillOpt Optimization ===")
    print(f"Skill: {args.skill_path}")
    print(f"Epochs completed: {result['epochs_completed']}")
    print(f"Final status: {result['final_status']}")
    print()
    for r in result["results"]:
        status_icon = "[OK]" if r["accepted"] else "[X]"
        print(f"  Epoch {r['epoch']}: {status_icon} {r['message']}")


def cmd_skillopt_self_evolve(args):
    """Run self-evolution on super-brain's own SKILL.md."""
    import json as json_mod
    
    # Load validation tasks if provided
    validation_tasks = None
    if args.validation_tasks:
        with open(args.validation_tasks, "r", encoding="utf-8") as f:
            validation_tasks = json_mod.load(f)
    
    result = self_evolve(
        epochs=args.epochs,
        validation_tasks=validation_tasks,
        workspace=args.workspace
    )
    
    if result["status"] == "error":
        print(f"Error: {result['message']}")
        sys.exit(1)
    
    print(f"\n=== SuperBrain Self-Evolution ===")
    print(f"Epochs completed: {result['epochs_completed']}")
    print(f"Final status: {result['final_status']}")
    print()
    for r in result["results"]:
        status_icon = "[OK]" if r.get("accepted") else "[X]"
        print(f"  Epoch {r['epoch']}: {status_icon} {r['message']}")


def cmd_skillopt_history(args):
    """Show optimization history."""
    history = get_optimization_history(args.workspace, limit=args.limit)
    
    if not history:
        print("No optimization history found.")
        return
    
    print(f"Optimization History ({len(history)} epochs):")
    for h in history:
        status_icon = "[OK]" if h["accepted"] else "[X]"
        print(f"  {status_icon} Epoch {h['epoch']}: {h['status']}")
        print(f"      Score: {h['current_score']:.3f} -> {h['candidate_score']:.3f}")
        print(f"      Edits: {len(h['applied_edits'])} applied")
        print(f"      Time: {h['timestamp']}")


def cmd_skillopt_rejected(args):
    """Show rejected edit buffer."""
    buffer = get_rejected_buffer(args.workspace)
    
    if not buffer:
        print("Rejected edit buffer is empty.")
        return
    
    print(f"Rejected Edit Buffer ({len(buffer)} entries):")
    for entry in buffer[-args.limit:]:
        print(f"  Epoch {entry['epoch']}: {entry['message']}")
        print(f"    Proposed edits: {len(entry['proposed_edits'])}")


def cmd_skillopt_status(args):
    """Show SkillOpt status."""
    status = skillopt_status(args.workspace)
    
    print("=== SkillOpt Status ===")
    print(f"Optimization epochs: {status['optimization_epochs']}")
    if status['last_epoch']:
        print(f"Last epoch: {status['last_epoch']} ({status['last_epoch_status']})")
    print(f"Rejected edits in buffer: {status['rejected_edits']}")
    print()
    
    trace_stats = status['trace_stats']
    if trace_stats['total'] > 0:
        print(f"Traces: {trace_stats['total']} total")
        print(f"  Avg score: {trace_stats.get('avg_score', 'N/A')}")
        print(f"  Explicit feedback: {trace_stats.get('satisfied_count', 0)} satisfied / {trace_stats.get('dissatisfied_count', 0)} dissatisfied")
    else:
        print("Traces: No execution traces recorded yet.")
    print()
    print(f"Default validation tasks: {status['default_validation_tasks']}")


def cmd_skillopt_rollback(args):
    """Rollback to a previous epoch."""
    # Find skill path
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skill_path = os.path.join(skill_dir, "SKILL.md")
    
    result = rollback_skillopt(args.epoch, skill_path, args.workspace)
    print(f"Rollback result: {result['status']}")
    print(f"  {result['message']}")


# === Trace Commands ===

def cmd_trace_record(args):
    """Record an execution trace (usually called programmatically)."""
    import json as json_mod
    
    input_data = json_mod.loads(args.input) if args.input else {}
    output_data = json_mod.loads(args.output) if args.output else {}
    
    trace = record_trace(
        command=args.command,
        input_data=input_data,
        output_data=output_data,
        workspace=args.workspace,
        explicit_rating=args.rating,
        implicit_signals={"completed": True, "error": False, "timeout": False} if not args.error else {"completed": False, "error": True, "timeout": False},
        validation_score=args.validation_score
    )
    
    print(f"Trace recorded: {trace['trace_id']}")
    print(f"  Weighted score: {trace['weighted_score']}")


def cmd_trace_feedback(args):
    """Add explicit feedback to a trace."""
    trace = add_explicit_feedback(args.trace_id, args.rating, args.workspace)
    if trace:
        print(f"Feedback added to trace {args.trace_id}")
        print(f"  New weighted score: {trace['weighted_score']}")
    else:
        print(f"Trace not found: {args.trace_id}")
        sys.exit(1)


def cmd_trace_list(args):
    """List execution traces."""
    traces = get_traces(args.workspace, limit=args.limit)
    
    if not traces:
        print("No traces found.")
        return
    
    print(f"Execution Traces ({len(traces)} shown):")
    for t in traces:
        rating = t["signals"]["explicit"]["rating"] if t["signals"]["explicit"] else "none"
        print(f"  {t['trace_id']} | {t['command']} | score: {t['weighted_score']:.2f} | rating: {rating}")
        print(f"    Time: {t['timestamp']}")


def cmd_trace_stats(args):
    """Show trace statistics."""
    stats = get_trace_stats(args.workspace)
    import json as json_mod
    print_json(stats)


def cmd_trace_export(args):
    """Export traces for SkillOpt."""
    output_path = export_traces_for_skillopt(args.workspace, args.output)
    print(f"Traces exported to: {output_path}")


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

    # === SkillOpt subparser ===
    sp_skillopt = subparsers.add_parser("skillopt", help="SkillOpt self-evolution engine")
    skillopt_sub = sp_skillopt.add_subparsers(dest="skillopt_command")

    # skillopt optimize
    sp = skillopt_sub.add_parser("optimize", help="Optimize an external skill")
    sp.add_argument("--skill-path", required=True, help="Path to SKILL.md to optimize")
    sp.add_argument("--validation-tasks", help="Path to validation tasks JSON file")
    sp.add_argument("--epochs", type=int, default=3, help="Number of optimization epochs")
    sp.add_argument("--workspace", help="Workspace for optimization state")
    sp.set_defaults(func=cmd_skillopt_optimize)

    # skillopt self-evolve
    sp = skillopt_sub.add_parser("self-evolve", help="Self-evolve super-brain's own SKILL.md")
    sp.add_argument("--epochs", type=int, default=3, help="Number of optimization epochs")
    sp.add_argument("--validation-tasks", help="Path to validation tasks JSON file")
    sp.add_argument("--workspace", help="Workspace for optimization state")
    sp.set_defaults(func=cmd_skillopt_self_evolve)

    # skillopt history
    sp = skillopt_sub.add_parser("history", help="Show optimization history")
    sp.add_argument("--limit", type=int, default=10, help="Max entries to show")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_skillopt_history)

    # skillopt rejected
    sp = skillopt_sub.add_parser("rejected", help="Show rejected edit buffer")
    sp.add_argument("--limit", type=int, default=10, help="Max entries to show")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_skillopt_rejected)

    # skillopt status
    sp = skillopt_sub.add_parser("status", help="Show SkillOpt status")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_skillopt_status)

    # skillopt rollback
    sp = skillopt_sub.add_parser("rollback", help="Rollback to a previous epoch")
    sp.add_argument("--epoch", type=int, required=True, help="Epoch number to rollback to")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_skillopt_rollback)

    # === Trace subparser ===
    sp_trace = subparsers.add_parser("trace", help="Execution trace recording")
    trace_sub = sp_trace.add_subparsers(dest="trace_command")

    # trace record
    sp = trace_sub.add_parser("record", help="Record an execution trace")
    sp.add_argument("--command", required=True, help="Subcommand executed")
    sp.add_argument("--input", help="Input arguments as JSON")
    sp.add_argument("--output", help="Output result as JSON")
    sp.add_argument("--rating", choices=["satisfied", "dissatisfied"], help="Explicit user rating")
    sp.add_argument("--error", action="store_true", help="Execution had an error")
    sp.add_argument("--validation-score", type=float, help="Validation score (0-1)")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_trace_record)

    # trace feedback
    sp = trace_sub.add_parser("feedback", help="Add explicit feedback to a trace")
    sp.add_argument("--trace-id", required=True, help="Trace ID")
    sp.add_argument("--rating", required=True, choices=["satisfied", "dissatisfied"], help="User rating")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_trace_feedback)

    # trace list
    sp = trace_sub.add_parser("list", help="List execution traces")
    sp.add_argument("--limit", type=int, default=20, help="Max traces to show")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_trace_list)

    # trace stats
    sp = trace_sub.add_parser("stats", help="Show trace statistics")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_trace_stats)

    # trace export
    sp = trace_sub.add_parser("export", help="Export traces for SkillOpt")
    sp.add_argument("--output", help="Output file path")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_trace_export)

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
