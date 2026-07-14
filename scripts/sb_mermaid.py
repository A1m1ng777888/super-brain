#!/usr/bin/env python3
"""
SuperBrain Mermaid Exporter
把知识图谱（graph.json）导出为 Mermaid 关系图文本。

v3.8.x: 收割 TencentDB-Agent-Memory「符号化卸载（symbolic offload）」范式的轻量版——
不直接把大块记忆原文塞进上下文，而是给一张关系图，需要时再按节点 id（= graph.json
的 node id）下钻回原始记忆。本模块只做"把已有 graph.json 画出来"，不动存储核心。

Usage:
    python sb_mermaid.py [--workspace NAME] [--direction LR|TB|TD|BT|RL]
    from sb_mermaid import graph_to_mermaid

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import read_graph


# Mermaid 节点标识符只接受字母/数字/下划线；知识图谱的 node id 常含中文、空格、
# 方括号等，直接用作标识符会产出非法语法（不报错、渲染空白，极难排查）。
_NID_SAFE = re.compile(r"[^A-Za-z0-9_]")
_VALID_DIR = {"LR", "TB", "TD", "BT", "RL"}


def _sanitize(label):
    """Mermaid 标签净化：
    - 双引号换单引号（避免破坏 "..." 标签边界）
    - 去换行（避免节点定义跨行导致整图语法崩）
    - ] 换全角 ］（避免提前闭合 ["..."]）
    """
    s = (label or "").replace('"', "'")
    s = s.replace("\n", " ").replace("\r", " ")
    return s.replace("]", "］")


def _safe_nid(nid, mapping):
    """把任意 node id 映射为合法 Mermaid 标识符，并登记到 mapping。

    节点与边共用同一 mapping，保证边两端引用的标识符与节点定义一致。
    假设：当前 node id 体系（UUID / slug）不会碰撞到同一 safe 串；
    碰撞兜底（加后缀去重）视为过度设计，按需后续再加。
    """
    base = _NID_SAFE.sub("_", str(nid)) or "node"
    mapping[nid] = base
    return base


def graph_to_mermaid(workspace=None, direction="LR"):
    """读取 graph.json，导出 Mermaid 关系图字符串。

    Args:
        workspace: 工作空间名（None = 当前工作空间）
        direction: 布局方向，合法值 LR/TB/TD/BT/RL；非法值兜底为 LR

    Returns:
        Mermaid 图定义文本。空图谱返回带注释的占位图。
    """
    # P1：read_graph 可能返回 None（工作空间不存在 / 文件损坏 / graph.json 异常）
    graph = read_graph(workspace)
    if not isinstance(graph, dict):
        wname = workspace or "默认工作空间"
        return f"graph {direction}\n  %% 读取图谱失败：{_sanitize(wname)} 返回非 dict 结构"

    nodes = graph.get("nodes") or {}
    edges = graph.get("edges") or {}
    # 结构守卫：节点/边本身必须是 dict，畸形数据走占位图而非抛 AttributeError
    if not isinstance(nodes, dict) or not isinstance(edges, dict):
        wname = workspace or "默认工作空间"
        return f"graph {direction}\n  %% 图谱结构异常：{_sanitize(wname)} 的 nodes/edges 非 dict"

    # 方向归一化（非法值兜底为 LR，不改变合法默认调用）
    direction = str(direction or "LR").upper()
    if direction not in _VALID_DIR:
        direction = "LR"

    if not nodes and not edges:
        wname = workspace or "默认工作空间"
        return f"graph {direction}\n  %% 空知识图谱（{_sanitize(wname)} 暂无节点/边）"

    lines = [f"graph {direction}"]

    # 先登记 orig->safe 映射，保证边两端引用一致、悬空判定准确
    orig_to_safe = {}
    for nid, node in nodes.items():
        if not isinstance(node, dict):
            continue
        sid = _safe_nid(nid, orig_to_safe)
        name = _sanitize(node.get("name", nid))
        ntype = _sanitize(node.get("type", "concept"))
        lines.append(f'  {sid}["{name} · {ntype}"]')

    # 边：仅当两端节点都已登记才画，避免悬空引用导致渲染失败
    dangling = 0
    for edge in edges.values():
        if not isinstance(edge, dict):
            continue
        s = orig_to_safe.get(edge.get("source"))
        t = orig_to_safe.get(edge.get("target"))
        if s is None or t is None:
            dangling += 1
            continue
        etype = _sanitize(edge.get("type", "related_to"))
        lines.append(f'  {s} -- "{etype}" --> {t}')

    if dangling:
        lines.append(f"  %% {dangling} 条悬空边已忽略")

    return "\n".join(lines)


def main():
    import argparse
    p = argparse.ArgumentParser(description="导出超脑知识图谱为 Mermaid 图")
    p.add_argument("--workspace", default=None, help="工作空间名（默认当前）")
    p.add_argument("--direction", default="LR",
                   choices=sorted(_VALID_DIR), help="布局方向 LR/TB/TD/BT/RL")
    args = p.parse_args()
    print(graph_to_mermaid(workspace=args.workspace, direction=args.direction))


if __name__ == "__main__":
    main()
