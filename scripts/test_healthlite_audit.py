# -*- coding: utf-8 -*-
"""
test_healthlite_audit.py — 运行史审计测试（sb_healthlite.audit_history, v3.14.0）

覆盖：
- 空历史/文件缺失/损坏 JSON → no_history（容错不崩溃）
- 正常节奏 → ok，n_runs / days_since_last 正确
- 守护停滞（>2 天未运行）→ warn
- 断档（相邻间隔 >48h）→ warn + gaps 检出
- 疑似重复执行（相邻间隔 <60min）→ warn + duplicates 检出
- 窗口截断（--days 只看最近 N 天）
- 畸形时间戳条目被跳过而非拖垮审计

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sb_healthlite as hl

NOW = datetime(2026, 9, 24, 9, 30, tzinfo=timezone.utc)


def _ts(days_ago=0.0, hours_ago=0.0, minutes_ago=0.0):
    return (NOW - timedelta(days=days_ago, hours=hours_ago,
                            minutes=minutes_ago)).isoformat()


def _entry(days_ago=0.0, hours_ago=0.0, minutes_ago=0.0, status="ok"):
    return {"ts": _ts(days_ago, hours_ago, minutes_ago), "status": status,
            "n_issues": 0, "n_err": 0, "new_nodes": 0, "new_edges": 0,
            "duration_sec": 12.3}


class AuditBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="sb_audit_")
        self.hist = os.path.join(self.tmpdir, "health_history.json")

    def _write(self, data):
        with open(self.hist, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def audit(self, days=30):
        return hl.audit_history(days=days, history_path=self.hist, now=NOW)


class TestEmptyHistory(AuditBase):
    def test_missing_file_is_no_history(self):
        r = self.audit()
        self.assertEqual(r["status"], "no_history")
        self.assertEqual(r["n_runs"], 0)

    def test_empty_list_is_no_history(self):
        self._write([])
        self.assertEqual(self.audit()["status"], "no_history")

    def test_corrupted_json_is_no_history(self):
        with open(self.hist, "w", encoding="utf-8") as f:
            f.write("{ not json !!!")
        self.assertEqual(self.audit()["status"], "no_history")

    def test_non_list_json_is_no_history(self):
        self._write({"ts": "2026-09-24"})
        self.assertEqual(self.audit()["status"], "no_history")


class TestNormalCadence(AuditBase):
    def test_daily_runs_ok(self):
        self._write([_entry(days_ago=d) for d in range(6, -1, -1)])
        r = self.audit()
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["n_runs"], 7)
        self.assertEqual(r["days_since_last"], 0.0)
        self.assertEqual(r["gaps"], [])
        self.assertEqual(r["duplicates"], [])
        self.assertEqual(r["last_ts"][:10], "2026-09-24")


class TestAnomalies(AuditBase):
    def test_stall_warns(self):
        self._write([_entry(days_ago=5)])
        r = self.audit()
        self.assertEqual(r["status"], "warn")
        self.assertEqual(r["days_since_last"], 5.0)
        self.assertTrue(any("停滞" in n for n in r["notes"]))

    def test_gap_detected(self):
        # 正常 → 断 5 天 → 正常
        self._write([_entry(days_ago=10), _entry(days_ago=9),
                     _entry(days_ago=4), _entry(days_ago=3),
                     _entry(days_ago=2), _entry(days_ago=1), _entry()])
        r = self.audit()
        self.assertEqual(r["status"], "warn")
        self.assertEqual(len(r["gaps"]), 1)
        self.assertGreater(r["gaps"][0]["gap_hours"], 48)

    def test_duplicate_detected(self):
        self._write([_entry(hours_ago=2), _entry(hours_ago=1.9),
                     _entry(minutes_ago=30)])
        r = self.audit()
        self.assertEqual(r["status"], "warn")
        self.assertEqual(len(r["duplicates"]), 1)
        self.assertLess(r["duplicates"][0]["interval_min"], 60)

    def test_stale_boundary_not_duplicate(self):
        # 恰 61 分钟间隔：不算重复
        self._write([_entry(minutes_ago=61), _entry()])
        r = self.audit()
        self.assertEqual(r["duplicates"], [])


class TestWindowAndRobustness(AuditBase):
    def test_window_cutoff(self):
        self._write([_entry(days_ago=20), _entry(days_ago=3), _entry()])
        r = self.audit(days=7)
        self.assertEqual(r["n_runs"], 2)  # 20 天前那条出窗

    def test_malformed_entries_skipped(self):
        self._write([{"ts": "not-a-time"}, {"no_ts": True},
                     "garbage", _entry()])
        r = self.audit()
        self.assertEqual(r["n_runs"], 1)
        self.assertEqual(r["status"], "ok")

    def test_naive_timestamp_treated_as_utc(self):
        self._write([{"ts": (NOW - timedelta(days=1))
                      .replace(tzinfo=None).isoformat()}])
        r = self.audit()
        self.assertEqual(r["n_runs"], 1)
        self.assertEqual(r["days_since_last"], 1.0)


if __name__ == "__main__":
    unittest.main()
