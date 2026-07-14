#!/usr/bin/env python3
"""
SuperBrain Mermaid Exporter
把知识图谱（graph.json）导出为 Mermaid 关系图文本。

v3.8.x: 收割 TencentDB-Agent-Memory「符号化卸载（symbolic offload）」范式的轻量版——
不直接把大块记忆原文塞进上下文，而是给一张关系图，需要时再按节点 id（= graph.json
的 node id）下钻回原始记忆。本模块只做"把已有 graph.json 画出来"，不动存储核心。

Usage:
    python sb_mermaid.py [--workspace NAME] [--direction LR|TB]
    from sb_mermaid import graph_to_mermaid

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_graph


def _sanitize(label):
    """Mermaid 标签里双引号会破坏语法，统一换成单引号。"""
    return (label or "").replace('"', "'")


def graph_to_mermaid(workspace=None, direction="LR"):
    """读取 graph.json，导出 Mermaid 关系图字符串。

    Args:
        workspace: 工作空间名（None = 当前工作空间）
        direction: 布局方向，"LR"（左右）或 "TB"（上下）

    Returns:
        Mermaid 图定义文本。空图谱返回带注释的占位图。
    """
    graph = read_graph(workspace)
    nodes = graph.get("nodes", {}) or {}
    edges = graph.get("edges", {}) or {}

    if not nodes and not edges:
        wname = workspace or "默认工作空间"
        return f"graph {direction}\n  %% 空知识图谱（{_sanitize(wname)} 暂无节点/边）"

    lines = [f"graph {direction}"]

    # 节点：用 node id 作 Mermaid 标识符，引号内显示 name · type
    for nid, node in nodes.items():
        name = _sanitize(node.get("name", nid))
        ntype = _sanitize(node.get("type", "concept"))
        # 形如：node_abc["砚 · person"]
        lines.append(f'  {nid}["{name} · {ntype}"]')

    # 边：仅当两端节点都存在才画，避免悬空引用导致 Mermaid 渲染失败
    for eid, edge in edges.items():
        src = edge.get("source")
        tgt = edge.get("target")
        etype = _sanitize(edge.get("type", "related_to"))
        if src in nodes and tgt in nodes:
            lines.append(f'  {src} -- "{etype}" --> {tgt}')

    return "\n".join(lines)


def main():
    import argparse
    p = argparse.ArgumentParser(description="导出超脑知识图谱为 Mermaid 图")
    p.add_argument("--workspace", default=None, help="工作空间名（默认当前）")
    p.add_argument("--direction", default="LR", help="布局方向 LR/TB")
    args = p.parse_args()
    print(graph_to_mermaid(workspace=args.workspace, direction=args.direction))


if __name__ == "__main__":
    main()
