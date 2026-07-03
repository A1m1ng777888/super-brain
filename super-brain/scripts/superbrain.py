#!/usr/bin/env python3
"""
SuperBrain CLI v3.2.2 — Unified entry point for the Super Brain skill.
Provides subcommands for memory, graph, search, selfcheck, workspace, stats,
skillopt (self-evolution), trace, orchestration, and Obsidian sync management.

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

    # SkillOpt self-evolution & trace recording (v2.0.0+)
    python superbrain.py skillopt status
    python superbrain.py skillopt self-evolve --epochs 3
    python superbrain.py skillopt optimize --skill-path PATH --epochs 3
    python superbrain.py skillopt history
    python superbrain.py skillopt rejected

    # Temporal memory (v2.1.0)
    python superbrain.py memory add --type fact --content "..." --valid-from 2023-01-01 --valid-until 2025-12-31
    python superbrain.py memory add --type fact --content "new fact" --replaces mem_xxx
    python superbrain.py memory search "query" --min-score 0.3
    python superbrain.py trace record --command "memory add" --input '{"content": "..."}'
    python superbrain.py trace feedback --trace-id ID --rating satisfied
    python superbrain.py trace list [--limit N]
    python superbrain.py trace stats
    python superbrain.py trace export [--output PATH]

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
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
    MEMORY_TYPES, auto_store, fuzzy_correct_query, learn_expression,
    get_expression_profile, search_with_correction
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
# v3.0.0 imports
from sb_perception import (
    should_learn_or_query, information_value_assessment, get_perception_stats,
    batch_perceive
)
from sb_pipeline import (
    classify_content, compute_decay_factor, should_archive, get_pipeline_stats,
    cleanup_memories
)
from sb_reasoning import (
    extract_key_points, analyze_logic, derive_conclusion, assist_decision,
    get_reasoning_stats
)
from sb_entanglement import (
    mine_entanglement, reinforce_links, build_entanglement_field,
    query_entanglement, get_entanglement_stats
)
from sb_context import (
    topic_cluster, trace_thread, cross_session_recall, get_topic_context,
    get_context_stats
)
from sb_longterm import (
    auto_ingest, cross_session_associate, zero_cost_retrieve, build_index,
    get_longterm_stats
)

# v3.2.0 imports
from sb_orchestrator import (
    should_orchestrate, decompose_task, generate_sub_agent_specs,
    get_orchestration_stats, reset_circuit_breaker, orchestrate,
    select_minimal_tools, TOOL_PROFILES, record_spawn, record_complete,
    record_failure, run_tests as run_orch_tests,
    # v3.3.0
    evaluate_goal_completion, should_continue_goal, record_continuation,
    reset_continuation_state, get_goal_status, orchestrate_continue,
    _hash_results, MAX_CONTINUATIONS
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
    """Add a new memory. v2.1.0: supports --valid-from/--valid-until/--replaces."""
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
        tags=args.tags.split(",") if args.tags else None,
        valid_from=args.valid_from,      # v2.1.0
        valid_until=args.valid_until,    # v2.1.0
        replaces=args.replaces           # v2.1.0
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
        attributes=attrs,
        valid_from=args.valid_from,      # v2.1.0
        valid_until=args.valid_until     # v2.1.0
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
    """Get context for injection. v2.1.0: supports --min-score."""
    ctx = get_context(args.query, limit=args.limit, min_score=args.min_score)
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


def cmd_token_roi(args):
    """v3.4.0: Show Token ROI quantification."""
    from sb_token_roi import get_token_roi_summary, calc_token_roi, get_roi_quickline
    if args.quickline:
        print(get_roi_quickline(recent_days=args.days))
    elif args.json:
        data = calc_token_roi(recent_days=args.days)
        print_json(data)
    else:
        print(get_token_roi_summary(recent_days=args.days))


def cmd_version(args):
    """Show version information."""
    config = load_config()
    print(f"SuperBrain version {config.get('version', '3.2.2')}")
    print(f"Release date: 2026-07-02")
    print(f"Features: memory (v3.1 anti-pollution), search (v3.0 ternary hash+fuzzy), "
          f"perception (v3.0), pipeline (v3.1 cleanup), reasoning (v3.1 warmup), "
          f"entanglement (v3.1 warmup), context (v3.0), longterm (v3.0), "
          f"obsidian (v3.1 export+sync), session (v3.1 T1+T2+T3), "
          f"orchestrator (v3.2 sub-agent decomposition, "
          f"v3.2.1 implicit scope detection, v3.2.2 ambient via SOUL.md), "
          f"self-check (v2.1 temporal), SkillOpt, traces, workspace isolation")
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


# === v3.0.0 Commands ===

def cmd_memory_auto_store(args):
    """Auto-store important information from text."""
    result = auto_store(args.text, source_session=args.source, workspace=args.workspace)
    print_json(result)


def cmd_memory_correct(args):
    """Fuzzy-correct a query for typos and wording."""
    result = fuzzy_correct_query(args.query, workspace=args.workspace)
    print_json(result)


def cmd_memory_learn_expr(args):
    """Learn a user expression pattern."""
    result = learn_expression(args.input, args.standard, workspace=args.workspace)
    print_json(result)


def cmd_memory_search_corrected(args):
    """Search with automatic typo correction."""
    results = search_with_correction(args.query, limit=args.limit, workspace=args.workspace)
    if not results:
        print("No matching memories found.")
        return
    print(f"Found {len(results)} matching memories:")
    for mem, score, match_type in results:
        print(f"\n  [{match_type}] Score: {score:.3f} | ID: {mem['id']}")
        print(f"  Type: {mem['type']} | Entity: {mem['entity']}")
        print(f"  Content: {mem['content']}")


def cmd_perceive(args):
    """Perception: determine learn vs query."""
    result = should_learn_or_query(args.text, workspace=args.workspace)
    print_json(result)


def cmd_perceive_batch(args):
    """Batch perception analysis."""
    import json as json_mod
    messages = json_mod.loads(args.messages) if args.messages else []
    result = batch_perceive(messages, workspace=args.workspace)
    print_json(result)


def cmd_perceive_stats(args):
    """Perception statistics."""
    print_json(get_perception_stats(args.workspace))


def cmd_pipeline_classify(args):
    """Classify content as definition/chitchat."""
    result = classify_content(args.text)
    print_json(result)


def cmd_pipeline_stats(args):
    """Pipeline statistics."""
    print_json(get_pipeline_stats(args.workspace))


def cmd_pipeline_cleanup(args):
    """Clean up decayed memories."""
    result = cleanup_memories(args.workspace, dry_run=args.dry_run, force=args.force)
    print_json(result)


def cmd_reason_extract(args):
    """Extract key points from text."""
    result = extract_key_points(args.text, max_points=args.max_points)
    print_json(result)


def cmd_reason_analyze(args):
    """Analyze logical structure of text."""
    result = analyze_logic(args.text)
    print_json(result)


def cmd_reason_conclude(args):
    """Derive conclusion from memories."""
    result = derive_conclusion(args.query, workspace=args.workspace, max_premises=args.max_premises)
    print_json(result)


def cmd_reason_decide(args):
    """Assist decision-making."""
    import json as json_mod
    options = json_mod.loads(args.options) if args.options else []
    result = assist_decision(options, workspace=args.workspace)
    print_json(result)


def cmd_entangle_mine(args):
    """Mine entanglement for a concept."""
    result = mine_entanglement(args.concept, workspace=args.workspace, min_strength=args.min_strength)
    print_json(result)


def cmd_entangle_build(args):
    """Build the entanglement field."""
    result = build_entanglement_field(workspace=args.workspace, min_strength=args.min_strength)
    print_json(result)


def cmd_entangle_query(args):
    """Query entanglement for a search query."""
    result = query_entanglement(args.query, workspace=args.workspace, max_results=args.max_results)
    print_json(result)


def cmd_entangle_reinforce(args):
    """Reinforce a link between two tokens."""
    result = reinforce_links(args.token1, args.token2, strength=args.strength, workspace=args.workspace)
    print_json(result)


def cmd_entangle_stats(args):
    """Entanglement field statistics."""
    print_json(get_entanglement_stats(args.workspace))


def cmd_context_cluster(args):
    """Cluster memories by topic."""
    result = topic_cluster(workspace=args.workspace, min_similarity=args.min_similarity)
    print_json(result)


def cmd_context_trace(args):
    """Trace a conversation thread."""
    result = trace_thread(args.topic, workspace=args.workspace)
    print_json(result)


def cmd_context_recall(args):
    """Cross-session recall."""
    result = cross_session_recall(args.query, workspace=args.workspace, days_back=args.days_back)
    print_json(result)


def cmd_context_topic(args):
    """Get topic context."""
    result = get_topic_context(args.topic, workspace=args.workspace, limit=args.limit)
    print_json(result)


def cmd_context_stats(args):
    """Context memory statistics."""
    print_json(get_context_stats(args.workspace))


def cmd_longterm_ingest(args):
    """Auto-ingest: dialogue as storage."""
    result = auto_ingest(args.text, source_session=args.source, workspace=args.workspace)
    print_json(result)


def cmd_longterm_index(args):
    """Build retrieval index."""
    result = build_index(workspace=args.workspace)
    print_json(result)


def cmd_longterm_retrieve(args):
    """Zero-cost retrieval."""
    result = zero_cost_retrieve(args.query, workspace=args.workspace, limit=args.limit)
    print_json(result)


def cmd_longterm_associate(args):
    """Cross-session association."""
    result = cross_session_associate(args.memory_id, workspace=args.workspace)
    print_json(result)


def cmd_longterm_stats(args):
    """Long-term memory statistics."""
    print_json(get_longterm_stats(args.workspace))


# v3.1.0: Session lifecycle handlers
def cmd_session_start(args):
    """T1: Session start briefing."""
    from sb_core import session_start
    print_json(session_start(args.workspace))


def cmd_session_end(args):
    """T2: Session end wrap-up."""
    from sb_core import session_end
    print_json(session_end(args.workspace))


def cmd_session_health(args):
    """T3: Periodic 7-dimension health scan."""
    from sb_core import periodic_health_check
    print_json(periodic_health_check(args.workspace))


# v3.1.0: Obsidian sync handlers
def cmd_obsidian_export(args):
    """Export memories to Obsidian .md + [[wikilinks]]."""
    from sb_obsidian import export_to_obsidian
    result = export_to_obsidian(
        workspace=args.workspace,
        vault_path=getattr(args, 'vault_path', None),
        include_graph=not getattr(args, 'no_graph', False)
    )
    print_json(result)


def cmd_obsidian_sync(args):
    """Reverse sync .md changes back to JSON."""
    from sb_obsidian import reverse_sync_from_obsidian
    result = reverse_sync_from_obsidian(
        workspace=args.workspace,
        vault_path=getattr(args, 'vault_path', None),
        dry_run=not getattr(args, 'apply', False)
    )
    print_json(result)


def cmd_obsidian_stats(args):
    """Obsidian sync statistics."""
    from sb_obsidian import get_obsidian_stats
    print_json(get_obsidian_stats(args.workspace, getattr(args, 'vault_path', None)))


# v3.2.0: Orchestrator handlers
def cmd_orch_assess(args):
    """Assess task complexity and need for orchestration."""
    result = should_orchestrate(
        args.task,
        current_context_size=getattr(args, 'context_size', 0) or 0,
        workspace=args.workspace
    )
    print_json(result)


def cmd_orch_decompose(args):
    """Decompose a task into independent sub-tasks."""
    result = decompose_task(args.task, workspace=args.workspace)
    print_json(result)


def cmd_orch_spec(args):
    """Generate complete sub-agent specs for a task."""
    result = generate_sub_agent_specs(
        args.task,
        current_context_size=getattr(args, 'context_size', 0) or 0,
        workspace=args.workspace
    )
    print_json(result)


def cmd_orch_spawn(args):
    """Record spawn of a sub-agent."""
    result = record_spawn(
        args.orchestration_id or generate_id("orch"),
        args.sub_count,
        args.profiles.split(",") if getattr(args, 'profiles', None) else [],
        args.task,
        workspace=args.workspace
    )
    print_json(result)


def cmd_orch_complete(args):
    """Record completion of an orchestration."""
    import json as json_mod
    results = json_mod.loads(args.results) if args.results else []
    result = record_complete(args.orchestration_id, results, workspace=args.workspace)
    print_json({"status": "recorded", "orchestration_id": args.orchestration_id})


def cmd_orch_stats(args):
    """Orchestrator statistics."""
    print_json(get_orchestration_stats(args.workspace))


def cmd_orch_reset(args):
    """Reset the circuit breaker."""
    print_json(reset_circuit_breaker(args.workspace))


def cmd_orch_profiles(args):
    """List available tool profiles."""
    profiles = {
        name: {
            "description": p["description"],
            "subagent_type": p["subagent_type"],
            "tools": p["tools"],
            "skills": p.get("skills", [])
        }
        for name, p in TOOL_PROFILES.items()
    }
    print_json(profiles)


# ─── v3.3.0: Goal Continuation CLI handlers ──────────────────────────────

def cmd_orch_evaluate(args):
    """Evaluate goal completion from sub-results."""
    import json
    try:
        results = json.loads(args.results)
    except json.JSONDecodeError:
        print_json({"error": "Invalid JSON for --results"})
        sys.exit(1)
    result = evaluate_goal_completion(results, args.workspace)
    print_json(result)


def cmd_orch_continue(args):
    """Attempt continuation for an incomplete orchestration."""
    import json
    try:
        results = json.loads(args.results)
    except json.JSONDecodeError:
        print_json({"error": "Invalid JSON for --results"})
        sys.exit(1)

    result = orchestrate_continue(
        args.orchestration_id,
        args.task,
        results,
        current_context_size=args.context_size,
        workspace=args.workspace
    )
    print_json(result)


def cmd_orch_goal_status(args):
    """Get goal continuation status for an orchestration."""
    result = get_goal_status(args.orchestration_id, args.workspace)
    print_json(result)


def cmd_orch_continuation_reset(args):
    """Reset continuation state."""
    print_json(reset_continuation_state(args.workspace))


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
    sp.add_argument("--valid-from", help="Temporal: when this fact became true (ISO date, e.g. 2023-01-01) (v2.1.0)")
    sp.add_argument("--valid-until", help="Temporal: when this fact ceased to be true (ISO date) (v2.1.0)")
    sp.add_argument("--replaces", help="Memory ID this one supersedes (v2.1.0)")
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
    sp.add_argument("--min-score", type=float, help="Minimum score filter (v2.1.0)")
    sp.set_defaults(func=cmd_memory_search)

    # memory update
    sp = mem_sub.add_parser("update", help="Update a memory")
    sp.add_argument("--id", required=True, help="Memory ID")
    sp.add_argument("--content", help="New content")
    sp.add_argument("--confidence", type=float, help="New confidence score")
    sp.add_argument("--status", choices=["active", "archived", "deprecated", "superseded"], help="New status")
    sp.add_argument("--category", help="New category")
    sp.add_argument("--valid-from", help="Update temporal valid_from (v2.1.0)")
    sp.add_argument("--valid-until", help="Update temporal valid_until (v2.1.0)")
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
    sp.add_argument("--min-score", type=float, help="Minimum score filter (v2.1.0)")
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

    # v3.4.0: token-roi
    sp_roi = subparsers.add_parser("token-roi", help="Quantify token savings ROI")
    sp_roi.add_argument("--summary", action="store_true", default=True, help="Show human-readable summary")
    sp_roi.add_argument("--json", action="store_true", help="Output full JSON data")
    sp_roi.add_argument("--days", type=int, default=None, help="Only count recent N days")
    sp_roi.add_argument("--quickline", action="store_true", help="One-line summary for dialog injection")
    sp_roi.set_defaults(func=cmd_token_roi)

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

    # === v3.0.0 Subparsers ===

    # memory auto-store
    sp = mem_sub.add_parser("auto-store", help="Auto-store important info from text (v3.0.0)")
    sp.add_argument("--text", required=True, help="Text to extract and store")
    sp.add_argument("--source", help="Source session identifier")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_memory_auto_store)

    # memory correct
    sp = mem_sub.add_parser("correct", help="Fuzzy-correct a query (v3.0.0)")
    sp.add_argument("query", help="Query to correct")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_memory_correct)

    # memory learn-expr
    sp = mem_sub.add_parser("learn-expr", help="Learn user expression pattern (v3.0.0)")
    sp.add_argument("--input", required=True, help="User's actual phrasing")
    sp.add_argument("--standard", help="Standard/canonical form (optional)")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_memory_learn_expr)

    # memory search-corrected
    sp = mem_sub.add_parser("search-corrected", help="Search with typo correction (v3.0.0)")
    sp.add_argument("query", help="Search query")
    sp.add_argument("--limit", type=int, default=10, help="Max results")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_memory_search_corrected)

    # perceive
    sp_perceive = subparsers.add_parser("perceive", help="Perception: learn vs query (v3.0.0)")
    perceive_sub = sp_perceive.add_subparsers(dest="perceive_command")

    sp = perceive_sub.add_parser("check", help="Check if text should be learned or queried")
    sp.add_argument("--text", required=True, help="Text to analyze")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_perceive)

    sp = perceive_sub.add_parser("batch", help="Batch perception analysis")
    sp.add_argument("--messages", help="JSON array of messages")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_perceive_batch)

    sp = perceive_sub.add_parser("stats", help="Perception statistics")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_perceive_stats)

    # pipeline
    sp_pipeline = subparsers.add_parser("pipeline", help="Classification pipeline (v3.0.0)")
    pipeline_sub = sp_pipeline.add_subparsers(dest="pipeline_command")

    sp = pipeline_sub.add_parser("classify", help="Classify content")
    sp.add_argument("--text", required=True, help="Text to classify")
    sp.set_defaults(func=cmd_pipeline_classify)

    sp = pipeline_sub.add_parser("stats", help="Pipeline statistics")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_pipeline_stats)

    sp = pipeline_sub.add_parser("cleanup", help="Clean up decayed memories (v3.1.0)")
    sp.add_argument("--workspace", help="Workspace name")
    sp.add_argument("--dry-run", action="store_true", help="Report only, no changes")
    sp.add_argument("--force", action="store_true", help="Skip confirmation")
    sp.set_defaults(func=cmd_pipeline_cleanup)

    # reason
    sp_reason = subparsers.add_parser("reason", help="Reasoning engine (v3.0.0)")
    reason_sub = sp_reason.add_subparsers(dest="reason_command")

    sp = reason_sub.add_parser("extract", help="Extract key points from text")
    sp.add_argument("--text", required=True, help="Text to analyze")
    sp.add_argument("--max-points", type=int, default=5, help="Max key points")
    sp.set_defaults(func=cmd_reason_extract)

    sp = reason_sub.add_parser("analyze", help="Analyze logical structure")
    sp.add_argument("--text", required=True, help="Text to analyze")
    sp.set_defaults(func=cmd_reason_analyze)

    sp = reason_sub.add_parser("conclude", help="Derive conclusion from memories")
    sp.add_argument("query", help="Query to derive conclusion for")
    sp.add_argument("--max-premises", type=int, default=5, help="Max premises")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_reason_conclude)

    sp = reason_sub.add_parser("decide", help="Assist decision-making")
    sp.add_argument("--options", help="JSON array of options")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_reason_decide)

    # entangle
    sp_entangle = subparsers.add_parser("entangle", help="Entanglement field (v3.0.0)")
    entangle_sub = sp_entangle.add_subparsers(dest="entangle_command")

    sp = entangle_sub.add_parser("mine", help="Mine entanglement for a concept")
    sp.add_argument("concept", help="Concept to mine")
    sp.add_argument("--min-strength", type=float, default=0.1, help="Minimum strength")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_entangle_mine)

    sp = entangle_sub.add_parser("build", help="Build the entanglement field")
    sp.add_argument("--min-strength", type=float, default=0.1, help="Minimum strength")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_entangle_build)

    sp = entangle_sub.add_parser("query", help="Query entanglement")
    sp.add_argument("query", help="Search query")
    sp.add_argument("--max-results", type=int, default=10, help="Max results")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_entangle_query)

    sp = entangle_sub.add_parser("reinforce", help="Reinforce a link")
    sp.add_argument("--token1", required=True, help="First token")
    sp.add_argument("--token2", required=True, help="Second token")
    sp.add_argument("--strength", type=float, default=0.1, help="Reinforcement strength")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_entangle_reinforce)

    sp = entangle_sub.add_parser("stats", help="Entanglement statistics")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_entangle_stats)

    # context
    sp_context = subparsers.add_parser("context-mem", help="Context memory (v3.0.0)")
    context_sub = sp_context.add_subparsers(dest="context_command")

    sp = context_sub.add_parser("cluster", help="Cluster memories by topic")
    sp.add_argument("--min-similarity", type=float, default=0.3, help="Min similarity for clustering")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_context_cluster)

    sp = context_sub.add_parser("trace", help="Trace a conversation thread")
    sp.add_argument("topic", help="Topic or memory ID to trace")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_context_trace)

    sp = context_sub.add_parser("recall", help="Cross-session recall")
    sp.add_argument("query", help="Query for recall")
    sp.add_argument("--days-back", type=int, help="How many days to look back")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_context_recall)

    sp = context_sub.add_parser("topic", help="Get topic context")
    sp.add_argument("topic", help="Topic to get context for")
    sp.add_argument("--limit", type=int, default=10, help="Max memories")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_context_topic)

    sp = context_sub.add_parser("stats", help="Context memory statistics")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_context_stats)

    # longterm
    sp_longterm = subparsers.add_parser("longterm", help="Long-term memory (v3.0.0)")
    longterm_sub = sp_longterm.add_subparsers(dest="longterm_command")

    sp = longterm_sub.add_parser("ingest", help="Auto-ingest: dialogue as storage")
    sp.add_argument("--text", required=True, help="Text to ingest")
    sp.add_argument("--source", help="Source session identifier")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_longterm_ingest)

    sp = longterm_sub.add_parser("index", help="Build retrieval index")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_longterm_index)

    sp = longterm_sub.add_parser("retrieve", help="Zero-cost retrieval")
    sp.add_argument("query", help="Query to retrieve")
    sp.add_argument("--limit", type=int, default=5, help="Max results")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_longterm_retrieve)

    sp = longterm_sub.add_parser("associate", help="Cross-session association")
    sp.add_argument("--memory-id", required=True, help="Memory ID to associate")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_longterm_associate)

    sp = longterm_sub.add_parser("stats", help="Long-term memory statistics")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_longterm_stats)

    # v3.1.0: Session lifecycle protocols
    sp_session = subparsers.add_parser("session", help="Session lifecycle (v3.1.0)")
    session_sub = sp_session.add_subparsers(dest="session_command")

    sp = session_sub.add_parser("start", help="T1: Session start briefing")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_session_start)

    sp = session_sub.add_parser("end", help="T2: Session end wrap-up")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_session_end)

    sp = session_sub.add_parser("health", help="T3: Periodic 7-dimension health scan")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_session_health)

    # v3.1.0: Obsidian bidirectional sync
    sp_obsidian = subparsers.add_parser("obsidian", help="Obsidian sync (v3.1.0)")
    obsidian_sub = sp_obsidian.add_subparsers(dest="obsidian_command")

    sp = obsidian_sub.add_parser("export", help="Export all memories to .md + [[wikilinks]]")
    sp.add_argument("--workspace", help="Workspace name")
    sp.add_argument("--vault-path", help="Obsidian vault path (set OBSIDIAN_VAULT_PATH env var or defaults to ~/ObsidianVault)")
    sp.add_argument("--no-graph", action="store_true", help="Skip graph edges")
    sp.set_defaults(func=cmd_obsidian_export)

    sp = obsidian_sub.add_parser("sync", help="Reverse sync .md changes back to JSON")
    sp.add_argument("--workspace", help="Workspace name")
    sp.add_argument("--vault-path", help="Obsidian vault path")
    sp.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    sp.set_defaults(func=cmd_obsidian_sync)

    sp = obsidian_sub.add_parser("stats", help="Obsidian sync statistics")
    sp.add_argument("--workspace", help="Workspace name")
    sp.add_argument("--vault-path", help="Obsidian vault path")
    sp.set_defaults(func=cmd_obsidian_stats)

    # v3.2.0: Sub-Agent Orchestrator
    sp_orch = subparsers.add_parser("orchestrate", help="Sub-agent orchestrator (v3.2.0)")
    orch_sub = sp_orch.add_subparsers(dest="orchestrate_command")

    sp = orch_sub.add_parser("assess", help="Assess task complexity and orchestration need")
    sp.add_argument("task", help="Task description")
    sp.add_argument("--context-size", type=int, default=0, help="Estimated current context tokens")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_assess)

    sp = orch_sub.add_parser("decompose", help="Decompose task into sub-tasks")
    sp.add_argument("task", help="Task description")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_decompose)

    sp = orch_sub.add_parser("spec", help="Generate complete sub-agent specifications")
    sp.add_argument("task", help="Task description")
    sp.add_argument("--context-size", type=int, default=0, help="Estimated current context tokens")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_spec)

    sp = orch_sub.add_parser("spawn", help="Record sub-agent spawn")
    sp.add_argument("--orchestration-id", help="Orchestration ID")
    sp.add_argument("--sub-count", type=int, required=True, help="Number of sub-agents")
    sp.add_argument("--profiles", help="Comma-separated profile names")
    sp.add_argument("--task", required=True, help="Task summary")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_spawn)

    sp = orch_sub.add_parser("complete", help="Record orchestration completion")
    sp.add_argument("--orchestration-id", required=True, help="Orchestration ID")
    sp.add_argument("--results", help="JSON array of sub-results")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_complete)

    sp = orch_sub.add_parser("stats", help="Orchestrator statistics")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_stats)

    sp = orch_sub.add_parser("reset", help="Reset circuit breaker")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_reset)

    sp = orch_sub.add_parser("profiles", help="List tool profiles")
    sp.set_defaults(func=cmd_orch_profiles)

    # v3.3.0: Goal Continuation commands
    sp = orch_sub.add_parser("evaluate", help="Evaluate goal completion status")
    sp.add_argument("--results", required=True, help="JSON array of sub-results")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_evaluate)

    sp = orch_sub.add_parser("continue", help="Check if continuation is warranted and re-orchestrate")
    sp.add_argument("--orchestration-id", required=True, help="Orchestration ID")
    sp.add_argument("task", help="Original or refined task description")
    sp.add_argument("--results", required=True, help="JSON array of previous sub-results")
    sp.add_argument("--context-size", type=int, default=0)
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_continue)

    sp = orch_sub.add_parser("goal-status", help="Get goal continuation status")
    sp.add_argument("--orchestration-id", required=True, help="Orchestration ID")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_goal_status)

    sp = orch_sub.add_parser("continuation-reset", help="Reset continuation state")
    sp.add_argument("--workspace", help="Workspace name")
    sp.set_defaults(func=cmd_orch_continuation_reset)

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
