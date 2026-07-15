#!/usr/bin/env python3
"""
SuperBrain Knowledge Graph
Entity-relationship network: nodes, edges, queries, entity alignment.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    generate_id, get_timestamp, read_graph, write_graph,
    print_json, load_config
)


# Node types
NODE_TYPES = ["person", "project", "preference", "fact", "task", "document", "concept", "tool", "place", "organization"]

# Edge types
EDGE_TYPES = [
    "belongs_to",      # A belongs to B
    "likes",           # A likes B
    "participates_in", # A participates in B
    "discussed",       # A discussed B
    "depends_on",      # A depends on B
    "created",         # A created B
    "related_to",      # A is related to B (generic)
    "part_of",         # A is part of B
    "uses",            # A uses B
    "knows",           # A knows B (person to person)
    "located_in",      # A is located in B
    "works_on",        # A works on B
]


def add_node(name, node_type="concept", aliases=None, attributes=None,
             related_memory=None, workspace=None):
    """
    Add a node to the knowledge graph.
    If a node with the same name/alias exists, update it instead.
    Returns the node dict.
    """
    graph = read_graph(workspace)

    # Check for existing node (entity alignment)
    existing = find_node(name, graph)
    if existing:
        # Update: merge aliases and attributes
        if aliases:
            existing_aliases = set(existing.get("aliases", []))
            for a in aliases if isinstance(aliases, list) else [aliases]:
                existing_aliases.add(a)
            existing["aliases"] = list(existing_aliases)
        if attributes:
            if "attributes" not in existing:
                existing["attributes"] = {}
            existing["attributes"].update(attributes)
        if related_memory:
            if "related_memories" not in existing:
                existing["related_memories"] = []
            if related_memory not in existing["related_memories"]:
                existing["related_memories"].append(related_memory)
        existing["updated_at"] = get_timestamp()
        write_graph(graph, workspace)
        return existing

    # Create new node
    node_id = generate_id("node")
    node = {
        "id": node_id,
        "type": node_type,
        "name": name,
        "aliases": aliases if isinstance(aliases, list) else ([aliases] if aliases else []),
        "attributes": attributes or {},
        "related_memories": [related_memory] if related_memory else [],
        "created_at": get_timestamp(),
        "updated_at": get_timestamp()
    }
    graph["nodes"][node_id] = node
    write_graph(graph, workspace)
    return node


def add_edge(source_name_or_id, target_name_or_id, edge_type="related_to",
             weight=1.0, source_memory=None, workspace=None):
    """
    Add an edge between two nodes.
    Accepts node names or IDs. Auto-creates nodes if they don't exist.
    Returns the edge dict.
    """
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"Invalid edge type: {edge_type}. Must be one of {EDGE_TYPES}")

    graph = read_graph(workspace)

    # Resolve source node
    source_node = find_node(source_name_or_id, graph)
    if not source_node:
        if source_name_or_id in graph.get("nodes", {}):
            source_node = graph["nodes"][source_name_or_id]
        else:
            source_node = add_node(source_name_or_id, workspace=workspace)
            graph = read_graph(workspace)  # Reload after modification

    # Resolve target node
    target_node = find_node(target_name_or_id, graph)
    if not target_node:
        if target_name_or_id in graph.get("nodes", {}):
            target_node = graph["nodes"][target_name_or_id]
        else:
            target_node = add_node(target_name_or_id, workspace=workspace)
            graph = read_graph(workspace)  # Reload

    # Check if edge already exists
    for edge_id, edge in graph.get("edges", {}).items():
        if (edge["source"] == source_node["id"] and
            edge["target"] == target_node["id"] and
            edge["type"] == edge_type):
            # Update existing edge
            edge["weight"] = max(edge.get("weight", 1.0), weight)
            edge["updated_at"] = get_timestamp()
            if source_memory and source_memory not in edge.get("source_memories", []):
                if "source_memories" not in edge:
                    edge["source_memories"] = []
                edge["source_memories"].append(source_memory)
            write_graph(graph, workspace)
            return edge

    # Create new edge
    edge_id = generate_id("edge")
    edge = {
        "id": edge_id,
        "source": source_node["id"],
        "target": target_node["id"],
        "type": edge_type,
        "weight": weight,
        "source_memories": [source_memory] if source_memory else [],  # v3.9.2: 统一为复数键
        "created_at": get_timestamp(),
        "updated_at": get_timestamp()
    }
    graph["edges"][edge_id] = edge
    write_graph(graph, workspace)
    return edge


def find_node(name_or_id, graph=None):
    """
    Find a node by ID, name, or alias.
    Returns the node dict or None.
    """
    if graph is None:
        graph = read_graph()

    # Check by ID first
    if name_or_id in graph.get("nodes", {}):
        return graph["nodes"][name_or_id]

    # Check by name (case-insensitive)
    name_lower = name_or_id.lower()
    for node_id, node in graph.get("nodes", {}).items():
        if node.get("name", "").lower() == name_lower:
            return node
        # Check aliases
        for alias in node.get("aliases", []):
            if alias.lower() == name_lower:
                return node

    return None


def list_nodes(node_type=None, limit=50, workspace=None):
    """List nodes with optional type filter."""
    graph = read_graph(workspace)
    nodes = list(graph.get("nodes", {}).values())

    if node_type:
        nodes = [n for n in nodes if n.get("type") == node_type]

    nodes.sort(key=lambda n: n.get("updated_at", ""), reverse=True)
    return nodes[:limit]


def list_edges(node_id=None, edge_type=None, limit=50, workspace=None):
    """List edges with optional filters."""
    graph = read_graph(workspace)
    edges = list(graph.get("edges", {}).values())

    if node_id:
        # Resolve node name to ID if needed
        node = find_node(node_id, graph)
        actual_id = node["id"] if node else node_id
        edges = [e for e in edges if e["source"] == actual_id or e["target"] == actual_id]

    if edge_type:
        edges = [e for e in edges if e.get("type") == edge_type]

    edges.sort(key=lambda e: e.get("weight", 1.0), reverse=True)
    return edges[:limit]


def query_graph(name_or_id, depth=2, workspace=None):
    """
    Query the graph starting from a node, expanding to given depth.
    Returns the subgraph as nodes and edges.
    """
    graph = read_graph(workspace)
    start_node = find_node(name_or_id, graph)
    if not start_node:
        return {"error": f"Node not found: {name_or_id}"}

    visited_nodes = {start_node["id"]}
    visited_edges = set()
    result_nodes = {start_node["id"]: start_node}
    result_edges = {}

    # BFS expansion
    frontier = [start_node["id"]]
    for _ in range(depth):
        next_frontier = []
        for node_id in frontier:
            for edge_id, edge in graph.get("edges", {}).items():
                if edge_id in visited_edges:
                    continue
                # Check if this edge connects to our node
                connected_id = None
                if edge["source"] == node_id:
                    connected_id = edge["target"]
                elif edge["target"] == node_id:
                    connected_id = edge["source"]

                if connected_id and connected_id not in visited_nodes:
                    visited_edges.add(edge_id)
                    result_edges[edge_id] = edge
                    connected_node = graph["nodes"].get(connected_id)
                    if connected_node:
                        result_nodes[connected_id] = connected_node
                        next_frontier.append(connected_id)
                        visited_nodes.add(connected_id)
                elif connected_id and edge_id not in visited_edges:
                    visited_edges.add(edge_id)
                    result_edges[edge_id] = edge

        frontier = next_frontier
        if not frontier:
            break

    # Get direct connections summary
    connections = []
    for edge in result_edges.values():
        source = result_nodes.get(edge["source"], {}).get("name", edge["source"])
        target = result_nodes.get(edge["target"], {}).get("name", edge["target"])
        connections.append({
            "source": source,
            "target": target,
            "type": edge["type"],
            "weight": edge.get("weight", 1.0)
        })

    return {
        "start_node": start_node["name"],
        "nodes_found": len(result_nodes),
        "edges_found": len(result_edges),
        "nodes": [{"name": n["name"], "type": n["type"], "id": n["id"]} for n in result_nodes.values()],
        "connections": connections
    }


def delete_node(node_id_or_name, workspace=None):
    """Delete a node and all its edges."""
    graph = read_graph(workspace)
    node = find_node(node_id_or_name, graph)
    if not node:
        return False

    node_id = node["id"]
    # Delete node
    if node_id in graph["nodes"]:
        del graph["nodes"][node_id]
    # Delete connected edges
    to_delete = []
    for edge_id, edge in graph.get("edges", {}).items():
        if edge["source"] == node_id or edge["target"] == node_id:
            to_delete.append(edge_id)
    for eid in to_delete:
        del graph["edges"][eid]

    write_graph(graph, workspace)
    return node_id  # v3.9.2: 返回被删节点 ID，供调用方级联清理 related_nodes


def get_stats(workspace=None):
    """Get graph statistics."""
    graph = read_graph(workspace)
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", {})

    # Type distribution
    node_types = {}
    for n in nodes.values():
        t = n.get("type", "unknown")
        node_types[t] = node_types.get(t, 0) + 1

    edge_types = {}
    for e in edges.values():
        t = e.get("type", "unknown")
        edge_types[t] = edge_types.get(t, 0) + 1

    # Find orphan nodes (no edges)
    connected_ids = set()
    for e in edges.values():
        connected_ids.add(e["source"])
        connected_ids.add(e["target"])
    orphans = [nid for nid in nodes if nid not in connected_ids]

    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "node_types": node_types,
        "edge_types": edge_types,
        "orphan_nodes": len(orphans),
        "orphan_ids": orphans[:10]
    }
