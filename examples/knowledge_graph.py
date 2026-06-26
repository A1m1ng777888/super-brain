#!/usr/bin/env python3
"""
Example 2: Knowledge graph operations
Build and query a knowledge graph of projects and tools.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from sb_core import ensure_workspace
from sb_graph import add_node, add_edge, query_graph, list_nodes

# Initialize
ensure_workspace("example-graph")
print("Initialized workspace: example-graph")

# Add nodes
add_node(name="Super Brain", node_type="tool", aliases=["super-brain", "超脑"])
add_node(name="WorkBuddy", node_type="platform", aliases=["workbuddy"])
add_node(name="Python", node_type="tool", aliases=["python"])
add_node(name="SimHash", node_type="algorithm", aliases=["simhash"])

print("Added 4 nodes")

# Add edges (relationships)
add_edge(source_name_or_id="Super Brain", target_name_or_id="WorkBuddy", edge_type="runs_on")
add_edge(source_name_or_id="Super Brain", target_name_or_id="Python", edge_type="implemented_in")
add_edge(source_name_or_id="Super Brain", target_name_or_id="SimHash", edge_type="uses_algorithm")
add_edge(source_name_or_id="Python", target_name_or_id="SimHash", edge_type="used_by")

print("Added 4 edges")

# Query graph
print("\n--- Graph query (depth 2) ---")
result = query_graph("Super Brain", depth=2)

print(f"Starting node: {result['node']['name']}")
print(f"\nConnected nodes ({len(result['connected_nodes'])}):")
for node in result['connected_nodes']:
    print(f"  - {node['name']} ({node['type']})")

print(f"\nEdges ({len(result['edges'])}):")
for edge in result['edges']:
    print(f"  {edge['source']} --[{edge['type']}]--> {edge['target']}")

# List all nodes
print("\n--- All nodes ---")
nodes = list_nodes(limit=20)
for n in nodes:
    print(f"  {n['id']}: {n['name']} ({n['type']})")
