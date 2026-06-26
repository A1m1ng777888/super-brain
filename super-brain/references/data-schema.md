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
  "status": "active | archived | deprecated",
  "simhash": 1126685795764943806,
  "related_nodes": ["node_001", "node_002"]
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
| `status` | enum | active (in use), archived (deprecated), deprecated (superseded) |
| `simhash` | int | 64-bit SimHash fingerprint of content for fast similarity |
| `related_nodes` | array | Knowledge graph node IDs related to this memory |

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
