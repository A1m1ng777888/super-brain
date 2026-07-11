# Super Brain Token Optimization

## Core Principle

Every feature must provide more value than the tokens it consumes. Super Brain is designed to ENHANCE capability while REDUCING total token consumption compared to unassisted operation.

## Strategy 1: Context Compression

### Problem
Loading full memory records (with all metadata) into context wastes tokens on fields the AI doesn't need for reasoning.

### Solution
The `memory context` command returns a compressed structure with only essential fields:

**Full memory record** (~200 tokens):
```json
{
  "id": "mem_20260626_143000_a1b2c3d4",
  "timestamp": "2026-06-26T14:30:00",
  "type": "preference",
  "entity": "user",
  "content": "User prefers dark mode IDE theme",
  "attributes": {"scope": "global", "category": "personal"},
  "source_session": "session_test",
  "confidence": 0.95,
  "last_accessed": "2026-06-26T14:30:00",
  "access_count": 3,
  "status": "active",
  "simhash": 1126685795764943806,
  "related_nodes": []
}
```

**Compressed context** (~50 tokens):
```json
{
  "id": "mem_20260626_143000_a1b2c3d4",
  "type": "preference",
  "entity": "user",
  "content": "User prefers dark mode IDE theme",
  "confidence": 0.95,
  "score": 0.87,
  "match": "keyword",
  "timestamp": "2026-06-26"
}
```

**Savings: ~75% per memory.**

## Strategy 2: On-Demand Loading

### Problem
Loading all memories into context at conversation start is wasteful — most won't be relevant.

### Solution
Use semantic search to load only relevant memories:
- Default limit: 5 memories per query
- Only active-status memories are searched
- Confidence threshold filters out uncertain data
- Access counts prioritize frequently-useful memories

**Before** (naive approach): Load 100 memories = ~20,000 tokens
**After** (Super Brain): Load 5 relevant memories = ~250 tokens
**Savings: ~98.75%**

## Strategy 3: Structured Injection

### Problem
Natural language descriptions of memories are verbose. "The user previously mentioned that they prefer dark mode interfaces, particularly for IDE themes, and this was discussed in the context of setting up their development environment..." = ~35 tokens.

### Solution
Structured JSON injection: `{"type": "preference", "entity": "user", "content": "prefers dark mode IDE"}` = ~15 tokens.

**Savings: ~57% per memory.**

## Strategy 4: SimHash Pre-Filtering

### Problem
TF-IDF cosine similarity is expensive to compute across all memories for every query.

### Solution
SimHash provides O(1) comparison via Hamming distance:
1. Compute query SimHash (one-time cost)
2. Compare against all stored SimHashes (integer XOR + bit count, extremely fast)
3. Only run expensive TF-IDF on top candidates

This reduces the number of expensive similarity computations by ~80% for large memory stores.

## Strategy 5: Incremental Updates

### Problem
Rewriting the entire memory file on every change is I/O expensive and can cause race conditions.

### Solution
- Memory appends are O(1) — just add to the JSON array
- Only write the file when data actually changes
- Meta file tracks counts separately to avoid full file rewrites for statistics

## Strategy 6: Confidence-Weighted Retrieval

### Problem
Low-confidence memories add noise without adding value.

### Solution
Memories with confidence < 0.3 are:
- Flagged by self-check for archival
- Excluded from context injection (can be overridden with explicit search)
- Counted separately in statistics

This ensures only high-quality knowledge enters the AI's context window.

## Token Budget Analysis

| Operation | Tokens Consumed | Tokens Saved | Net Benefit |
|-----------|----------------|--------------|-------------|
| Memory extraction (1 memory) | ~50 (CLI output) | N/A (stored for future) | +future savings |
| Context recall (5 memories) | ~250 | ~20,000 (vs. loading all) | +19,750 |
| Self-check | ~200 (report) | N/A (maintenance) | +data quality |
| Graph query (depth 2) | ~150 | ~500 (vs. exploring manually) | +350 |
| Proactive surface (1 memory) | ~30 (brief mention) | ~500 (avoid re-explanation) | +470 |

**Estimated daily savings**: 15,000-30,000 tokens (depending on conversation volume and memory store size)

## Best Practices for Token Efficiency

1. **Extract sparingly**: Only store genuinely useful, non-obvious information. One-sentence memories, not paragraphs.
2. **Search before asking**: Always check memories before asking the user for information they may have already provided.
3. **Batch operations**: When extracting multiple memories from one conversation, run them in sequence without reading intermediate output.
4. **Use `context` not `search`**: For conversation injection, use `memory context` (compressed) not `memory search` (full output).
5. **Regular self-checks**: Run `selfcheck --fix` weekly to archive stale data and merge duplicates, keeping the store lean.
6. **Workspace isolation**: Use separate workspaces for unrelated projects to avoid cross-contamination in search results.
