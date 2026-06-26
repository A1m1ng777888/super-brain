# Super Brain Architecture

## Three-Layer Eight-Module Design

```
+-----------------------------------------------------------+
|                   Interaction Layer                        |
|   CLI Commands  |  Proactive Prompts  |  Health Reports   |
+-----------------------------------------------------------+
|                   Core Cognitive Layer                     |
|  +----------+  +----------+  +----------+                |
|  | Memory   |  | Knowledge|  | Perception|               |
|  | Engine   |  | Graph    |  | Enhancement|              |
|  +----------+  +----------+  +----------+                |
|  +----------+  +----------+  +----------+                |
|  | Semantic |  | Intelligent| | Self-Check|              |
|  | Search   |  | Error Fix  | | System    |              |
|  +----------+  +----------+  +----------+                |
+-----------------------------------------------------------+
|                   Storage & Infrastructure                 |
|  Workspace Isolation  |  Token Optimizer  |  File Store   |
+-----------------------------------------------------------+
```

## Module Interactions

### Memory Engine (sb_memory.py)
Central hub that all other modules interact with:
- **Receives** extraction requests from the AI → stores memories with SimHash fingerprints
- **Provides** memories to Semantic Search for query matching
- **Feeds** entity data to Knowledge Graph for node/edge creation
- **Supplies** memory data to Self-Check for diagnostic scanning
- **Returns** token-optimized context to the AI via `get_context()`

### Knowledge Graph (sb_graph.py)
Entity-relationship network that provides structural context:
- **Receives** entities from Memory Engine (via AI extraction)
- **Provides** graph traversal results for context expansion
- **Reports** orphan nodes to Self-Check for cleanup
- **Supports** entity alignment (alias-based deduplication)

### Semantic Search (sb_search.py)
Hybrid retrieval engine combining three strategies:
1. **SimHash** (fast coarse filtering) — 64-bit locality-sensitive hash, Hamming distance comparison
2. **TF-IDF Cosine Similarity** (precise ranking) — term frequency with inverse document frequency
3. **Keyword Match** (exact hit boosting) — token overlap ratio

Search pipeline: Query → SimHash filter → TF-IDF rank → Keyword boost → Top-N results

### Self-Check System (sb_selfcheck.py)
Periodic diagnostics with five check types:
- **Consistency**: Detects same-entity memories with high TF-IDF similarity (potential contradictions)
- **Timeliness**: Flags memories older than 90 days with zero access and low confidence
- **Completeness**: Finds task-type memories without completion status
- **Orphans**: Identifies graph nodes with no edges
- **Duplicates**: Detects memories with SimHash similarity > 85%

Auto-fix capabilities:
- Archives memories with confidence < 0.3 that are stale
- Merges memories with similarity > 0.95

### Token Optimizer (cross-cutting)
Applied across all modules:
- **Context Compression**: `get_context()` returns only id, type, entity, content, confidence, score — not full memory objects
- **Structured Injection**: JSON format instead of natural language prose
- **On-Demand Loading**: Only retrieves `--limit` memories per query (default 5-10)
- **Incremental Updates**: Only changed data is written, not full rewrites
- **Confidence Weighting**: Low-confidence memories are filtered out of context injection

## Data Flow

### Memory Extraction Flow
```
AI detects memory-worthy info
  → AI calls: memory add --type ... --content ...
    → sb_memory.add_memory()
      → Generate SimHash fingerprint
      → Append to memories.json
      → Update workspace meta
    → Return memory ID to AI
```

### Context Retrieval Flow
```
User asks a question
  → AI calls: memory context "query" --limit 5
    → sb_memory.get_context()
      → sb_search.search_memories() 
        → SimHash filter + TF-IDF rank + keyword boost
      → Update access counts on matched memories
      → Return compressed JSON context
  → AI injects context into response
```

### Self-Check Flow
```
AI calls: selfcheck --fix
  → sb_selfcheck.run_full_check(auto_fix=True)
    → Run 5 checks (consistency, timeliness, completeness, orphans, duplicates)
    → If auto_fix: archive stale low-confidence, merge near-duplicates
    → Save report to health/latest_report.json
    → Return summary to AI
```

## File Layout

```
~/.workbuddy/super-brain/
├── config.json                          # Global configuration
├── health/
│   ├── latest_report.json               # Most recent self-check
│   └── report_2026-06-26T06-38-05.json  # Historical reports
└── workspaces/
    └── default/
        ├── memories.json                # All memory records
        ├── graph.json                   # Knowledge graph (nodes + edges)
        └── meta.json                    # Workspace metadata
```

## Configuration

```json
{
  "version": "1.0.0",
  "data_dir": "~/.workbuddy/super-brain",
  "current_workspace": "default",
  "simhash_bits": 64,
  "similarity_threshold": 0.65,
  "max_memories_per_load": 20,
  "self_check_interval_days": 7,
  "auto_extract": true,
  "token_optimization": {
    "context_compression": true,
    "max_context_memories": 10,
    "summary_mode": "structured"
  }
}
```
