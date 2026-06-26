#!/usr/bin/env python3
"""
Example 1: Basic memory operations
Store and retrieve memories using the SuperBrain CLI.
"""

import os
import sys

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from sb_core import ensure_workspace
from sb_memory import add_memory, search, get_context, list_memories

# Initialize
ensure_workspace("default")
print("Initialized workspace: default")

# Add memories
mem1 = add_memory(
    content="User prefers dark theme for IDE",
    mem_type="preference",
    entity="user",
    confidence=0.95,
    source="example_session"
)
print(f"Added memory: {mem1['id']}")

mem2 = add_memory(
    content="Project uses Python 3.13 with FastAPI",
    mem_type="fact",
    entity="my-project",
    confidence=0.9,
    source="example_session"
)
print(f"Added memory: {mem2['id']}")

# Search memories
print("\n--- Search results ---")
results = search("dark theme", limit=5)
for mem, score, match_type in results:
    print(f"  [{match_type}] {score:.3f}: {mem['content']}")

# Get context (token-optimized)
print("\n--- Context for AI prompt ---")
ctx = get_context("user preferences", limit=3)
print(ctx)

# List all memories
print("\n--- All memories ---")
memories = list_memories(limit=10)
for m in memories:
    print(f"  {m['id']}: [{m['type']}] {m['content'][:50]}...")
