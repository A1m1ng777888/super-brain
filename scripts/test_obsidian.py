#!/usr/bin/env python3
"""
SuperBrain Obsidian 同步测试（步骤1 格式 / 步骤3 安全 / 步骤2 图谱）

不依赖真实 super-brain 数据：通过 monkeypatch 注入 fixture，
写入临时 vault 目录验证导出产物格式。

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""
import os
import sys
import json
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import sb_obsidian as obs

SAMPLE_MEMORY = {
    "id": "mem_test_001",
    "type": "decision",
    "entity": "超脑升级",
    "content": "测试记忆：决定采用 callout 格式",
    "confidence": 0.95,
    "status": "active",
    "timestamp": "2026-07-09T00:00:00",
    "tags": [],
}


def _install_fakes():
    obs.read_memories = lambda workspace=None: [SAMPLE_MEMORY]
    obs.read_graph = lambda workspace=None: {"nodes": {}, "edges": {}}
    obs.read_meta = lambda workspace=None: {}


# ===================== 步骤1：格式底座对齐 =====================

def test_render_callout():
    lines = obs._render_callout(SAMPLE_MEMORY)
    assert lines[0] == "> [!info] 元数据", lines
    assert any("**类型**: decision" in l for l in lines), lines
    assert any("**置信度**: 0.95" in l for l in lines), lines
    print("PASS test_render_callout")


def test_export_format_callout_and_blockref():
    _install_fakes()
    with tempfile.TemporaryDirectory() as tmp:
        obs.export_to_obsidian(workspace="test", vault_path=tmp)
        export_dir = obs.get_vault_memory_dir(tmp)
        files = [f for f in os.listdir(export_dir) if f.endswith(".md") and f != "_INDEX.md"]
        assert files, "no memory file exported"
        with open(os.path.join(export_dir, files[0]), encoding="utf-8") as fh:
            text = fh.read()
        assert "> [!info] 元数据" in text, "callout missing"
        assert "^sb-content" in text, "block reference missing"
    print("PASS test_export_format_callout_and_blockref")


# ===================== 步骤3：安全护栏 =====================

def test_safe_write_valid():
    _install_fakes()
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = obs.get_vault_memory_dir(tmp)
        target = os.path.join(export_dir, "ok.md")
        obs.safe_write_file(target, "# hello", tmp)
        assert os.path.isfile(target)
        assert open(target, encoding="utf-8").read() == "# hello"
    print("PASS test_safe_write_valid")


def test_safe_write_rejects_traversal():
    _install_fakes()
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = obs.get_vault_memory_dir(tmp)
        bad = os.path.join(export_dir, "..", "escaped.md")
        try:
            obs.safe_write_file(bad, "x", tmp)
            assert False, "should have raised on '..' traversal"
        except obs.SafeWriteError:
            pass
    print("PASS test_safe_write_rejects_traversal")


def test_safe_write_rejects_absolute_outside():
    _install_fakes()
    with tempfile.TemporaryDirectory() as tmp:
        # 绝对路径落在 vault 根但不在导出目录内（无 '..'）
        sibling = os.path.join(tmp, "sibling.md")
        try:
            obs.safe_write_file(sibling, "x", tmp)
            assert False, "should have raised outside export dir"
        except obs.SafeWriteError:
            pass
    print("PASS test_safe_write_rejects_absolute_outside")


def test_export_through_safe_write():
    """export_to_obsidian 全程走 safe_write_file，依旧正确落盘。"""
    _install_fakes()
    with tempfile.TemporaryDirectory() as tmp:
        obs.export_to_obsidian(workspace="test", vault_path=tmp)
        export_dir = obs.get_vault_memory_dir(tmp)
        files = [f for f in os.listdir(export_dir) if f.endswith(".md")]
        assert "_INDEX.md" in files, "index not written via safe_write"
        assert any(f != "_INDEX.md" for f in files), "memory file not written via safe_write"
    print("PASS test_export_through_safe_write")


# ===================== 步骤2：图谱可视化 =====================

def _install_graph_fakes():
    # 3 条记忆：mem_a 与 mem_c 同 entity "X"（应聚成同一星系），mem_b 单独 entity "Y"
    mem_a = {"id": "mem_a", "type": "fact", "entity": "X", "content": "记忆A内容",
             "confidence": 0.9, "status": "active", "timestamp": "2026-07-09T00:00:00", "tags": []}
    mem_b = {"id": "mem_b", "type": "decision", "entity": "Y", "content": "记忆B内容",
             "confidence": 0.8, "status": "active", "timestamp": "2026-07-09T00:00:00", "tags": []}
    mem_c = {"id": "mem_c", "type": "event", "entity": "X", "content": "记忆C内容",
             "confidence": 0.7, "status": "active", "timestamp": "2026-07-09T00:00:00", "tags": []}
    obs.read_memories = lambda w=None: [mem_a, mem_b, mem_c]
    # 图节点带 type（类别）与 name，用于验证实体配色 / 文本
    obs.read_graph = lambda w=None: {
        "nodes": {
            "ent_z": {"id": "ent_z", "name": "实体Z", "type": "person"},
            "ent_w": {"id": "ent_w", "name": "实体W", "type": "tool"},
        },
        "edges": {
            "e1": {"source": "ent_z", "target": "ent_w", "type": "uses"},
        },
    }
    obs.read_meta = lambda w=None: {}


def test_export_graph_as_canvas():
    """记忆级图谱：实体节点 + 主题节点 + 记忆 file 节点 + 归属边。"""
    _install_graph_fakes()
    with tempfile.TemporaryDirectory() as tmp:
        result = obs.export_graph_as_canvas(workspace="t", vault_path=tmp)
        export_dir = obs.get_vault_memory_dir(tmp)
        canvas_path = os.path.join(export_dir, "知识图谱.canvas")
        assert os.path.isfile(canvas_path), "canvas not written"
        data = json.loads(open(canvas_path, encoding="utf-8").read())

        ids = {nd["id"] for nd in data["nodes"]}
        non_legend = [nd for nd in data["nodes"] if not nd["id"].startswith("legend")]

        # 节点三类：2 实体 + 2 主题(X/Y) + 3 记忆 = 7（不含图例）
        ent_nodes = [nd for nd in non_legend if nd["id"].startswith("ent_")]
        topic_nodes = [nd for nd in non_legend if nd["id"].startswith("topic_")]
        mem_nodes = [nd for nd in non_legend if nd["id"].startswith("mem_")]
        assert len(ent_nodes) == 2, ent_nodes
        assert len(topic_nodes) == 2, topic_nodes  # X 与 Y 两个主题
        assert len(mem_nodes) == 3, mem_nodes
        assert len(non_legend) == 7, non_legend

        # 记忆节点是 file 类型且链 .md
        for nd in mem_nodes:
            assert nd["type"] == "file", nd
            assert nd["file"].endswith(".md"), nd
        # 主题 / 实体节点是 text 且带 color
        for nd in ent_nodes + topic_nodes:
            assert nd["type"] == "text" and "color" in nd, nd

        # 实体类别配色：person→1, tool→4
        color_of = {nd["id"]: nd["color"] for nd in ent_nodes}
        assert color_of["ent_z"] == "1" and color_of["ent_w"] == "4"

        # 边：1 实体关系 + 3 记忆→主题归属 = 4
        assert len(data["edges"]) == 4, data["edges"]
        mem_edges = [e for e in data["edges"] if e["id"].startswith("emem-")]
        assert len(mem_edges) == 3, mem_edges
        # 同 entity 的 mem_a / mem_c 都指向同一 topic_X
        topic_of = {}
        for e in mem_edges:
            topic_of[e["fromNode"]] = e["toNode"]
        assert topic_of["mem_a"] == topic_of["mem_c"], "同 entity 记忆应聚同一主题"
        assert topic_of["mem_b"] != topic_of["mem_a"]

        # 力导向铺开：非图例节点最远两两距离 > 200
        pts = [(nd["x"], nd["y"]) for nd in non_legend]
        max_dist = max(
            ((pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2) ** 0.5
            for i in range(len(pts)) for j in range(i + 1, len(pts))
        )
        assert max_dist > 200, f"layout not spread (max_dist={max_dist})"
        # 非图例节点整体在图例右侧（x>=540）
        assert min(nd["x"] for nd in non_legend) >= 540

        # 图例：标题 + 类别图例 + 记忆/主题图例
        assert "legend_title" in ids
        assert "legend_mem" in ids and "legend_topic" in ids
        # 边引用存在的节点
        for e in data["edges"]:
            assert e["fromNode"] in ids and e["toNode"] in ids
        assert result["nodes"] == 7 and result["edges"] == 4
    print("PASS test_export_graph_as_canvas")


if __name__ == "__main__":
    test_render_callout()
    test_export_format_callout_and_blockref()
    test_safe_write_valid()
    test_safe_write_rejects_traversal()
    test_safe_write_rejects_absolute_outside()
    test_export_through_safe_write()
    test_export_graph_as_canvas()
    print("ALL OBSIDIAN STEP-1/2/3 TESTS PASSED")
