#!/usr/bin/env python3
"""
SuperBrain Knowledge Graph
Entity-relationship network: nodes, edges, queries, entity alignment.

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import (
    generate_id, get_timestamp, read_graph, write_graph,
    print_json, load_config, workspace_lock
)


def _write_locked(func):
    """写事务装饰器：graph 写操作整体包进跨进程 workspace 锁（2026-08-30 并发安全修复）。
    与 sb_memory._write_locked 同构；锁在 sb_core.workspace_lock 层可重入，
    因此 add_node 内再嵌套其他已锁写调用也不会死锁。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ws = kwargs.get("workspace")
        with workspace_lock(ws):
            return func(*args, **kwargs)
    return wrapper


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


@_write_locked
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


@_write_locked
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


@_write_locked
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


# ============================================================================
# v3.11.2 (P0-I): 从记忆自动构建图谱
# ============================================================================
# 背景与诊断（2026-08-30 实测）：图谱空转率 97.8%（627 记忆仅 14 节点）的
# 根因不是 bug，而是**自动建图能力从未实现**——sb_graph 只有手动
# add_node/add_edge，现存 14 节点全是 2026-07-14 的演示数据（含 "Alice"），
# 且 add_memory 把 related_nodes 初始化为空数组后全仓库无人回填。
# 连带后果：compute_salience 的 entanglement 项（0.15 权重）结构性恒零，
# salience 五项中 35% 的权重是死的（另 20% 是 access，见访问统计时点断裂）。
#
# 设计（边阈值标定的教训与 BM25 归一化同源）：
#   - 节点 = entity（general/空实体不建节点：未分类记忆保持冷却是合理语义）
#   - 边 = entity 伪文档（每实体取 5 条最长成员记忆）的库级 IDF 余弦相似度
#   - 建边用 **top-K + 地板** 而非绝对阈值：实测 10731 个实体对的相似度
#     分布极低平（p50=0.012 / p99=0.087 / max=0.462），任何全局绝对阈值
#     要么糊成全连接（0.03）要么只剩个位数边（0.2）。top-K 是 scale-free 的，
#     每个实体连自己最相似的 K 个邻居，与分布的绝对水平解耦。
#     floor=0.05 + K=3 实测：241 边 / 135/147 实体连通 / 度中位 3 / 最大 31。
#   - related_nodes 回填 = [自身节点] + 权重最高的前 4 个邻居节点 ID。
#     用节点 ID 而非实体名：sb_obsidian._edge_to_note_title 按 ID 解析节点
#     （这是该字段的既定语义）；推理链写入的记忆 ID 不受影响（合并不覆盖）。
#     截断到 1+4=5 使 ent_score = min(1, n/5) 恢复 0~1 区分度：
#     度 1~3 的实体 0.4~0.8 / 度 ≥4 的枢纽实体 1.0 / **孤立实体与 general 恒 0**
#     （孤立实体不建节点：无边节点不携带图信息，且会被 selfcheck orphans
#     持续告警——实测首版 12 个孤立节点把 selfcheck 从 1 issue 推回 13）。
#   - 幂等：节点按 name/alias 去重（find_node），边按无序对去重；
#     related_nodes 合并而非覆盖（保护推理链的记忆 ID 链接）。

GRAPH_BUILD_FLOOR = 0.05     # 建边最低相似度（过滤 p90 以下的长尾噪声）
GRAPH_BUILD_TOP_K = 3        # 每实体保留最相似的 K 个邻居
GRAPH_BUILD_PSEUDO_DOCS = 5  # 伪文档取每实体的前 N 条最长成员记忆
RELATED_NODES_MAX = 5        # related_nodes 回填上限（= ent_score 满分刻度）


@_write_locked
def build_from_memories(workspace=None, floor=GRAPH_BUILD_FLOOR, top_k=GRAPH_BUILD_TOP_K,
                        dry_run=False):
    """从 active 记忆自动构建知识图谱，并回填记忆的 related_nodes。

    v3.11.2 (P0-I 审阅补遗)：本函数做 read-modify-write 且会重写
    memories.json（related_nodes 回填），必须持有跨进程写锁——鲸砚（DSH）
    与砚共享记忆池，并发 add_memory 时无锁建图会丢写入（2026-08-30 审阅发现）。
    ⚠️ 调用方必须以 workspace= 关键字传参（装饰器从 kwargs 取锁名）。

    流程：entity 分桶 → 建节点 → 伪文档余弦相似度 → top-K 建边 →
    回填 related_nodes。graph.json 与 memories.json 各写一次。

    Returns:
        dict: 统计信息（nodes/edges/回填数/度分布/最强边样例/建后晋升比例）。
    """
    from sb_core import read_memories, write_memories
    from sb_search import tokenize
    from collections import Counter, defaultdict
    import math

    memories = read_memories(workspace)
    active = [m for m in memories if m.get("status") == "active"]

    # 1) entity 分桶（general/空 不建节点）
    groups = defaultdict(list)
    skipped = 0
    for m in active:
        e = (m.get("entity") or "").strip()
        if e and e.lower() != "general":
            groups[e].append(m)
        else:
            skipped += 1

    # 2) 伪文档 + 库级 IDF（在实体伪文档语料上算，抑制跨主题共词）
    docs = {}
    for e, ms in groups.items():
        top = sorted(ms, key=lambda m: len(m.get("content", "")), reverse=True)[:GRAPH_BUILD_PSEUDO_DOCS]
        toks = []
        for m in top:
            toks.extend(tokenize(m.get("content", "")))
        docs[e] = Counter(toks)
    names = list(docs)
    n_docs = len(names)
    if n_docs < 2:
        return {"error": "可用实体不足 2 个，无法建图", "entities": n_docs}

    df = Counter()
    for c in docs.values():
        for t in c:
            df[t] += 1
    idf = {t: math.log(1 + (n_docs - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def _cos(a, b):
        common = set(a) & set(b)
        if not common:
            return 0.0
        num = sum(a[t] * b[t] * idf.get(t, 1.0) ** 2 for t in common)
        da = math.sqrt(sum((a[t] * idf.get(t, 1.0)) ** 2 for t in a))
        db = math.sqrt(sum((b[t] * idf.get(t, 1.0)) ** 2 for t in b))
        return num / (da * db) if da and db else 0.0

    # 3) 全对相似度（147 实体 ≈ 1.1 万对，纯 Python 数秒内）
    sims = {}
    for i in range(n_docs):
        for j in range(i + 1, n_docs):
            s = _cos(docs[names[i]], docs[names[j]])
            if s > 0:
                sims[(names[i], names[j])] = s

    # 4) top-K 建边（scale-free，见模块注释）
    edge_pairs = {}  # (a, b) 无序对 -> weight
    for e in names:
        cand = sorted(
            ((s, pair) for pair, s in sims.items() if e in pair),
            key=lambda x: -x[0]
        )[:top_k]
        for s, (a, b) in cand:
            if s >= floor:
                edge_pairs[(a, b) if a < b else (b, a)] = s

    if dry_run:
        deg = Counter()
        for a, b in edge_pairs:
            deg[a] += 1
            deg[b] += 1
        return {
            "dry_run": True,
            "entities": n_docs,
            "skipped_memories": skipped,
            "new_nodes": len({e for pair in edge_pairs for e in pair}),
            "new_edges": len(edge_pairs),
            "connected_entities": len(deg),
            "isolated_entities": n_docs - len(deg),
            "top_pairs": sorted(((s, a, b) for (a, b), s in edge_pairs.items()),
                                key=lambda x: -x[0])[:8],
        }

    # 5) 落盘：只为「有边」的实体建节点。
    #    孤立实体节点（无边）不携带任何图信息，还会被 selfcheck 的 orphans
    #    检查持续告警——留待未来某次重建时它连上了再纳入。
    graph = read_graph(workspace)
    nodes = graph.setdefault("nodes", {})
    edges = graph.setdefault("edges", {})
    now = get_timestamp()

    connected = {e for pair in edge_pairs for e in pair}
    name_to_id = {}
    new_nodes = 0
    for e in connected:
        existing = find_node(e, graph)
        if existing:
            name_to_id[e] = existing["id"]
            # 把成员记忆挂到节点的 related_memories（幂等合并）
            rm = set(existing.get("related_memories") or [])
            rm.update(m["id"] for m in groups[e])
            existing["related_memories"] = sorted(rm)
            existing["updated_at"] = now
        else:
            nid = generate_id("node")
            nodes[nid] = {
                "id": nid,
                "type": "concept",
                "name": e,
                "aliases": [],
                "attributes": {"member_count": len(groups[e])},
                "related_memories": sorted(m["id"] for m in groups[e]),
                "created_at": now,
                "updated_at": now,
            }
            name_to_id[e] = nid
            new_nodes += 1

    # 6) 落盘：边（按无序对去重，跳过已存在的同对同型边）
    new_edges = 0
    for (a, b), w in edge_pairs.items():
        na, nb = name_to_id[a], name_to_id[b]
        exists = any(
            (ed["source"], ed["target"]) in ((na, nb), (nb, na))
            and ed.get("type") == "related_to"
            for ed in edges.values()
        )
        if exists:
            continue
        eid = generate_id("edge")
        edges[eid] = {
            "id": eid, "source": na, "target": nb, "type": "related_to",
            "weight": round(w, 4), "source_memory": None,
            "created_at": now, "updated_at": now,
        }
        new_edges += 1

    # 7) 邻居表（按边权重排序）→ 回填 related_nodes
    neighbors = defaultdict(list)  # node_id -> [(weight, other_id)]
    for ed in edges.values():
        if ed.get("type") != "related_to":
            continue
        neighbors[ed["source"]].append((ed.get("weight", 1.0), ed["target"]))
        neighbors[ed["target"]].append((ed.get("weight", 1.0), ed["source"]))
    for nid in neighbors:
        neighbors[nid].sort(reverse=True)

    backfilled = 0
    for e in connected:
        ms = groups[e]
        my_id = name_to_id[e]
        nb_ids = [other for _w, other in neighbors.get(my_id, [])[:RELATED_NODES_MAX - 1]]
        for m in ms:
            cur = list(m.get("related_nodes") or [])
            merged = list(dict.fromkeys(cur + [my_id] + nb_ids))[:RELATED_NODES_MAX]
            if merged != cur:
                m["related_nodes"] = merged
                backfilled += 1

    write_graph(graph, workspace)
    write_memories(memories, workspace)

    deg = Counter()
    for a, b in edge_pairs:
        deg[a] += 1
        deg[b] += 1

    # v3.11.2 (P0-I 审阅补遗)：建图会改变 entanglement → salience 分布整体
    # 漂移，晋升阈值可能随之出带（0.35→0.55→0.70 一天三标就是教训）。把
    # 建后晋升比例直接放进返回统计，漂移自动浮出，不再依赖人工记得跑 calibrate。
    from sb_gating import get_threshold, compute_salience
    thr = get_threshold(workspace)
    # P0-L 审阅补遗：候选池口径（排除 override），与 calibrate/门控一致
    candidates = [m for m in active if not m.get("gating_override")]
    over_thr = sum(1 for m in candidates if compute_salience(m, workspace) >= thr)
    ratio = over_thr / max(len(candidates), 1)
    ratio_note = ""
    if ratio > 0.25:
        ratio_note = f"⚠️ 建后晋升比例 {ratio:.1%} 超出 GWT 带(8~25%)，请用 calibrate 重新标定阈值"
    elif ratio < 0.08:
        ratio_note = f"⚠️ 建后晋升比例 {ratio:.1%} 低于 GWT 带(8~25%)，请用 calibrate 重新标定阈值"

    return {
        "entities": n_docs,
        "skipped_memories": skipped,
        "new_nodes": new_nodes,
        "new_edges": new_edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "connected_entities": len(deg),
        "isolated_entities": n_docs - len(deg),
        "memories_backfilled": backfilled,
        "post_build_promotion": {"threshold": thr, "ratio": round(ratio, 3),
                                 "note": ratio_note or "GWT 带内，阈值无需重标"},
        "top_pairs": sorted(((s, a, b) for (a, b), s in edge_pairs.items()),
                            key=lambda x: -x[0])[:8],
    }
