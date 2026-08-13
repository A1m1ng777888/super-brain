# -*- coding: utf-8 -*-
"""
test_forgetting.py — 遗忘治理模块测试（sb_forgetting.py v1.0.0）

覆盖：
- 项目档位判定（天数分档边界）
- 活跃度计算（时间主导，访问频率只做放大器）
- forget_priority（规模×不活跃×衰减；豁免=0）
- get_memory_weight（dormant/warm/active/豁免）
- scan（dormant + warm 高风险分层）
- apply（只 demote dormant，幂等，豁免不动）

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import pathlib
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import sb_forgetting as fg


def make_mem(mid, entity, days_ago_access, days_ago_update, access_count=0,
             pinned=False, gating=None, status="active"):
    """构造测试记忆。days_ago_* 为 None 表示无时间字段。"""
    def ts(days):
        if days is None:
            return None
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    mem = {
        "id": mid, "entity": entity, "type": "fact",
        "content": f"{entity} 测试内容 {mid}",
        "access_count": access_count,
        "status": status,
        "timestamp": ts(days_ago_update),
        "last_accessed": ts(days_ago_access),
    }
    if pinned:
        mem["pinned"] = True
    if gating:
        mem["gating_override"] = gating
    return mem


class TestTierBoundary(unittest.TestCase):
    """天数分档边界：14/15/45/46。"""

    def test_active_boundary_14(self):
        self.assertEqual(fg.project_tier(14), "active")

    def test_warm_boundary_15(self):
        self.assertEqual(fg.project_tier(15), "warm")

    def test_warm_boundary_45(self):
        self.assertEqual(fg.project_tier(45), "warm")

    def test_dormant_boundary_46(self):
        self.assertEqual(fg.project_tier(46), "dormant")

    def test_no_signal_is_dormant(self):
        self.assertEqual(fg.project_tier(None), "dormant")


class TestProjectActivity(unittest.TestCase):
    """活跃度：时间主导，访问频率只做放大器。"""

    def test_recent_project_high_activity(self):
        mems = [make_mem(f"m{i}", "projA", days_ago_access=3, days_ago_update=5, access_count=2)
                for i in range(3)]
        A = fg.compute_project_activity(mems)
        self.assertGreaterEqual(A, 0.9)

    def test_old_project_low_activity(self):
        # 60 天没访问：时间分归零，即使历史访问多也不该抬分
        mems = [make_mem(f"m{i}", "projB", days_ago_access=60, days_ago_update=70, access_count=8)
                for i in range(3)]
        A = fg.compute_project_activity(mems)
        self.assertEqual(A, 0.0)

    def test_median_not_min(self):
        # 一条记忆最近访问，其他都老 → median 决定，避免单条拉活整个项目
        mems = [
            make_mem("m1", "projC", days_ago_access=2, days_ago_update=2, access_count=1),
            make_mem("m2", "projC", days_ago_access=50, days_ago_update=50, access_count=0),
            make_mem("m3", "projC", days_ago_access=50, days_ago_update=50, access_count=0),
        ]
        median = fg.compute_project_median_days(mems)
        self.assertEqual(median, 50)
        self.assertEqual(fg.project_tier(median), "dormant")


class TestForgetPriority(unittest.TestCase):
    """遗忘优先级 = 规模 × (1-A) × 衰减；豁免 = 0。"""

    def test_exempt_mem_priority_zero(self):
        mems = [make_mem(f"m{i}", "砚", days_ago_access=60, days_ago_update=60)
                for i in range(3)]
        stats = fg.compute_project_stats(mems)
        p = fg.compute_forget_priority(mems[0], stats)
        self.assertEqual(p, 0.0)  # 砚 是身份实体 → 豁免

    def test_pinned_mem_priority_zero(self):
        mems = [make_mem(f"m{i}", "projX", days_ago_access=60, days_ago_update=60, pinned=True)
                for i in range(3)]
        stats = fg.compute_project_stats(mems)
        self.assertEqual(fg.compute_forget_priority(mems[0], stats), 0.0)

    def test_large_dormant_project_higher_priority(self):
        # 规模大 + dormant → 高优先级（实验型大项目场景）
        big = [make_mem(f"b{i}", "bigProj", days_ago_access=60, days_ago_update=60) for i in range(30)]
        small = [make_mem(f"s{i}", "smallProj", days_ago_access=60, days_ago_update=60) for i in range(3)]
        mems = big + small
        stats = fg.compute_project_stats(mems)
        p_big = fg.compute_forget_priority(big[0], stats)
        p_small = fg.compute_forget_priority(small[0], stats)
        self.assertGreater(p_big, p_small)  # 规模大 → 遗忘优先级高

    def test_never_accessed_boosts_priority(self):
        # 占比稀释（真实场景 S 不会=1），避免 clamp 饱和
        proj = [make_mem(f"m{i}", "projD", days_ago_access=60, days_ago_update=60, access_count=0)
                for i in range(3)]
        proj.append(make_mem("m4", "projD", days_ago_access=60, days_ago_update=60, access_count=5))
        filler = [make_mem(f"f{i}", "activeProj", days_ago_access=3, days_ago_update=3)
                  for i in range(5)]
        mems = proj + filler  # projD 占比 4/9
        stats = fg.compute_project_stats(mems)
        p_never = fg.compute_forget_priority(proj[0], stats)
        p_accessed = fg.compute_forget_priority(proj[3], stats)
        self.assertGreater(p_never, p_accessed)  # 从未访问 > 有访问


class TestMemoryWeight(unittest.TestCase):
    """召回权重：dormant=0.5 / warm=0.8 / active=1.0 / 豁免=1.0。"""

    def test_dormant_weight(self):
        mems = [make_mem(f"m{i}", "projE", days_ago_access=60, days_ago_update=60) for i in range(3)]
        stats = fg.compute_project_stats(mems)
        self.assertEqual(fg.get_memory_weight(mems[0], stats), 0.5)

    def test_warm_weight(self):
        mems = [make_mem(f"m{i}", "projF", days_ago_access=30, days_ago_update=30) for i in range(3)]
        stats = fg.compute_project_stats(mems)
        self.assertEqual(fg.get_memory_weight(mems[0], stats), 0.8)

    def test_active_weight(self):
        mems = [make_mem(f"m{i}", "projG", days_ago_access=3, days_ago_update=3) for i in range(3)]
        stats = fg.compute_project_stats(mems)
        self.assertEqual(fg.get_memory_weight(mems[0], stats), 1.0)

    def test_exempt_always_one(self):
        mems = [make_mem(f"m{i}", "潜进", days_ago_access=60, days_ago_update=60) for i in range(3)]
        stats = fg.compute_project_stats(mems)
        self.assertEqual(fg.get_memory_weight(mems[0], stats), 1.0)


class TestScanAndApply(unittest.TestCase):
    """scan 分层 + apply 幂等。"""

    def setUp(self):
        self.dormant = [make_mem(f"d{i}", "oldProj", days_ago_access=60, days_ago_update=60)
                        for i in range(3)]
        self.warm_big = [make_mem(f"w{i}", "warmBig", days_ago_access=30, days_ago_update=30)
                         for i in range(20)]
        self.active = [make_mem(f"a{i}", "activeProj", days_ago_access=3, days_ago_update=3)
                       for i in range(3)]
        self.mems = self.dormant + self.warm_big + self.active

    def test_scan_separates_tiers(self):
        sc = fg.scan_forgetting(self.mems)
        self.assertEqual(len(sc["dormant_candidates"]), 3)
        # warm 大项目应进高风险候选（20 条 / 26 总 = S≈0.77，pri 高）
        self.assertGreater(len(sc["warm_high_risk"]), 0)
        # active 项目不进任何候选
        active_ids = {m["id"] for m in self.active}
        all_cand = {c["id"] for c in sc["dormant_candidates"] + sc["warm_high_risk"]}
        self.assertEqual(active_ids & all_cand, set())

    def test_apply_only_demotes_dormant(self):
        res = fg.apply_forgetting(self.mems)
        self.assertEqual(res["changed"], 3)  # 只 3 条 dormant 被 demote
        for m in res["memories"]:
            if m["id"].startswith("d"):
                self.assertEqual(m.get("gating_override"), "demote")
            elif m["id"].startswith("a"):
                self.assertIsNone(m.get("gating_override"))  # active 不动
            elif m["id"].startswith("w"):
                self.assertIsNone(m.get("gating_override"))  # warm 不动（软切）

    def test_apply_idempotent(self):
        res1 = fg.apply_forgetting(self.mems)
        res2 = fg.apply_forgetting(res1["memories"])
        self.assertEqual(res2["changed"], 0)  # 已 demote 的不重复改

    def test_apply_skips_exempt(self):
        mems = [make_mem(f"m{i}", "砚", days_ago_access=60, days_ago_update=60) for i in range(3)]
        res = fg.apply_forgetting(mems)
        self.assertEqual(res["changed"], 0)
        for m in res["memories"]:
            self.assertIsNone(m.get("gating_override"))


class TestActiveScope(unittest.TestCase):
    """v3.11: scan/status/apply 只统计 active 子集（与 search 降权同源）。"""

    def _mix(self):
        active = [make_mem(f"a{i}", "liveProj", days_ago_access=3, days_ago_update=3)
                  for i in range(3)]
        archived = [make_mem(f"z{i}", "deadProj", days_ago_access=60, days_ago_update=60,
                             status="archived") for i in range(3)]
        return active + archived

    def test_scan_excludes_archived(self):
        mems = self._mix()
        sc = fg.scan_forgetting(mems)
        # deadProj 60 天不活跃 → dormant，但它是 archived，不应进候选
        ids = {c["id"] for c in sc["dormant_candidates"] + sc["warm_high_risk"]}
        self.assertTrue(all(not i.startswith("z") for i in ids),
                        f"archived 记忆不应进候选，got {ids}")

    def test_apply_skips_archived(self):
        mems = self._mix()
        res = fg.apply_forgetting(mems)
        # deadProj 是 dormant 但 archived，不应被 demote
        for m in res["memories"]:
            if m["id"].startswith("z"):
                self.assertIsNone(m.get("gating_override"),
                                  f"archived 记忆不应被 demote: {m['id']}")

    def test_status_reports_active_count(self):
        mems = self._mix()
        st = fg.status_forgetting(mems)
        self.assertEqual(st["total"], 6)      # 全量
        self.assertEqual(st["active"], 3)     # active 子集
        # tier_counts 只基于 active（3 条 liveProj，全部 active 档）
        self.assertEqual(st["tier_counts"].get("active"), 3)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestSuite()
    for cls in [TestTierBoundary, TestProjectActivity, TestForgetPriority,
                TestMemoryWeight, TestScanAndApply, TestActiveScope]:
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(cls))
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
