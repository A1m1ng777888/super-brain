# Super Brain Data Schema

## Memory Record

Stored in `workspaces/{workspace}/memories.json` as a JSON array.

```json
{
  "id": "mem_20260626_143000_a1b2c3d4",
  "timestamp": "2026-06-26T14:30:00",
  "type": "fact | preference | event | relationship | task | decision | context",
  "entity": "primary-entity-name",
  "content": "Concise one-sentence memory content",
  "attributes": {
    "scope": "global | project | workspace | session",
    "category": "knowledge | personal | history | social | work | background",
    "tags": ["tag1", "tag2"]
  },
  "source_session": "session identifier or description",
  "confidence": 0.95,
  "last_accessed": "2026-06-26T14:30:00",
  "access_count": 0,
  "status": "active | archived | deprecated | superseded",
  "simhash": 1126685795764943806,
  "related_nodes": ["node_001", "node_002"],
  "valid_from": "2023-01-01",
  "valid_until": "2025-12-31",
  "replaces": "mem_xxx",
  "replaced_by": "mem_yyy"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier: `mem_{timestamp}_{uuid8}` |
| `timestamp` | ISO 8601 | Creation time (UTC) |
| `type` | enum | Memory classification (see types below) |
| `entity` | string | Primary entity this memory is about |
| `content` | string | The actual memory content, one sentence preferred |
| `attributes` | object | Extended metadata (scope, category, tags) |
| `source_session` | string | Where this memory originated |
| `confidence` | float | 0.0-1.0, how certain this memory is |
| `last_accessed` | ISO 8601 | Last time this memory was retrieved |
| `access_count` | int | How many times retrieved |
| `status` | enum | active (in use), archived (deprecated), deprecated (superseded), superseded (replaced by newer memory) |
| `simhash` | int | 64-bit SimHash fingerprint of content for fast similarity |
| `related_nodes` | array | Knowledge graph node IDs related to this memory |
| `valid_from` | ISO date | (v2.1.0) When the fact became true in reality, e.g. "2023-01-01" |
| `valid_until` | ISO date | (v2.1.0) When the fact ceased to be true, null = still ongoing |
| `replaces` | string | (v2.1.0) Memory ID this memory supersedes |
| `replaced_by` | string | (v2.1.0) Memory ID that superseded this memory |

### Temporal Validity (v2.1.0)

The dual-time mechanism tracks two independent timelines:

| Timeline | Field | Description |
|----------|-------|-------------|
| **Fact validity** | `valid_from` / `valid_until` | When the fact was/is true in the real world |
| **System tracking** | `timestamp` / `status` / `replaces` / `replaced_by` | When the system learned about it and its lifecycle |

**Example — tracking a fact change:**
```
Memory A: valid_from=2023-01-01, valid_until=2025-06-15, status=superseded, replaced_by=mem_B
Memory B: valid_from=2025-06-15, valid_until=null, status=active, replaces=mem_A
```

**Conflict detection:** When `valid_from` is provided and temporal config is enabled,
the system checks for overlapping time ranges on the same entity+type and warns.

### Memory Types

| Type | Use Case | Example |
|------|----------|---------|
| `fact` | Objective information | "Project uses Python 3.13" |
| `preference` | User likes/dislikes | "User prefers dark mode" |
| `event` | What happened | "Deployed v2.0 on June 26" |
| `relationship` | Entity connections | "Alice leads Project Alpha" |
| `task` | Action items | "Need to write tests for auth module" |
| `decision` | Choices made | "Chose SimHash over vector DB" |
| `context` | Background info | "Meeting scheduled for Friday" |

### Confidence Guidelines

| Range | Meaning | Source |
|-------|---------|--------|
| 0.95-1.0 | Explicit user statement | User directly stated this |
| 0.8-0.94 | Strong inference | Clearly implied by user behavior or words |
| 0.6-0.79 | Moderate inference | Inferred from context |
| 0.3-0.59 | Weak inference | Uncertain, needs confirmation |
| 0.0-0.29 | Very uncertain | Auto-archived by self-check |

---

## Knowledge Graph

Stored in `workspaces/{workspace}/graph.json` as a JSON object with nodes and edges.

### Node Structure

```json
{
  "id": "node_20260626_143000_a1b2c3d4",
  "type": "person | project | preference | fact | task | document | concept | tool | place | organization",
  "name": "Display Name",
  "aliases": ["alias1", "alias2"],
  "attributes": {
    "description": "Optional description"
  },
  "related_memories": ["mem_001", "mem_002"],
  "created_at": "2026-06-26T14:30:00",
  "updated_at": "2026-06-26T14:30:00"
}
```

### Edge Structure

```json
{
  "id": "edge_20260626_143000_a1b2c3d4",
  "source": "node_001",
  "target": "node_002",
  "type": "belongs_to | likes | participates_in | discussed | depends_on | created | related_to | part_of | uses | knows | located_in | works_on",
  "weight": 1.0,
  "source_memory": "mem_001",
  "created_at": "2026-06-26T14:30:00",
  "updated_at": "2026-06-26T14:30:00"
}
```

### Node Types

| Type | Description | Example |
|------|-------------|---------|
| `person` | A human | Alice, Bob |
| `project` | A project or product | Project Alpha, Super Brain |
| `preference` | A preference node | Dark mode preference |
| `fact` | A factual knowledge node | Python 3.13 features |
| `task` | A task or action | Write auth tests |
| `document` | A document or file | API spec, design doc |
| `concept` | An abstract concept | SimHash, TF-IDF |
| `tool` | A software tool | React, Python, WorkBuddy |
| `place` | A physical location | Office, Server room |
| `organization` | An org or company | Tencent, Acme Corp |

### Edge Types

| Type | Meaning | Example |
|------|---------|---------|
| `belongs_to` | A is a member of B | Alice belongs_to Engineering |
| `likes` | A likes/prefers B | User likes Dark mode |
| `participates_in` | A is involved in B | Alice participates_in Project Alpha |
| `discussed` | A was discussed in context of B | Auth module discussed in Meeting |
| `depends_on` | A requires B | Auth depends_on Database |
| `created` | A created B | Alice created Project Alpha |
| `related_to` | Generic relation | React related_to TypeScript |
| `part_of` | A is a component of B | Auth part_of Backend |
| `uses` | A uses B | Project Alpha uses React |
| `knows` | Person A knows person B | Alice knows Bob |
| `located_in` | A is in B | Server located_in Datacenter |
| `works_on` | A is working on B | Alice works_on Auth module |

---

## Workspace Metadata

Stored in `workspaces/{workspace}/meta.json`.

```json
{
  "name": "default",
  "created_at": "2026-06-26T14:30:00",
  "memory_count": 42,
  "node_count": 15,
  "edge_count": 23,
  "last_self_check": "2026-06-26T14:30:00"
}
```

---

## Health Report

Stored in `health/latest_report.json`.

```json
{
  "timestamp": "2026-06-26T14:30:00",
  "workspace": "default",
  "checks": {
    "consistency": {
      "check": "consistency",
      "status": "healthy | warning",
      "issues_found": 0,
      "details": [],
      "recommendation": "..."
    }
  },
  "overall_status": "healthy | needs_attention",
  "total_issues": 0,
  "auto_fixed": 0
}
```

---

## Search & Dynamic Threshold (v2.1.0)

### Scoring Pipeline

```
Query → Tokenize → SimHash coarse (+ TF-IDF + Keyword) → Combined score
                                                              ↓
                                              Dynamic quality line = max(0.10, min(0.30, top_score × 0.50))
                                                              ↓
                                                        Filter & return
```

### Dynamic Threshold Config

```json
{
  "search": {
    "dynamic_threshold": true,
    "base_quality_line": 0.10,
    "max_quality_line": 0.30,
    "score_ratio": 0.50,
    "coarse_filter_threshold": 0.02
  }
}
```

### How It Works

Instead of a fixed `similarity_threshold`, the quality line adapts to each query:
- **High-quality query** (top score 0.80) → quality line = 0.30 → only highly relevant results pass
- **Medium query** (top score 0.40) → quality line = 0.20 → moderate filtering
- **Niche query** (top score 0.15) → quality line = 0.10 → floor, allows weak matches through

This ensures the bar rises with result quality — you never get false positives on good queries,
and you never get zero results on niche queries.
