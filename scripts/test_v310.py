#!/usr/bin/env python3
"""
SuperBrain v3.10.0 评分体系重构回归测试
=========================================
覆盖待办 D + Penguin 评测范式三行映射：
① 硬/软指标分域 —— 软指标（completeness/gating_flood/duplicates 等）
   从扣分项改为报告项，总分只基于物理完整性+时效性+真损坏
② 有效性协议 —— 物理损坏时 score_status=invalid（不是低分，是无效）
③ 修复后验证 —— auto_fix 后硬分未提升则提示回滚

全程使用隔离临时目录，不触碰生产数据。
Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""
import sys, os, json, tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# 强制数据目录隔离
TEST_DATA = tempfile.mkdtemp(prefix="sb_test_v310_")
os.environ["SUPERBRAIN_DATA_DIR"] = TEST_DATA

from sb_core import ensure_workspace, write_json, get_workspace_dir
from sb_selfcheck import (
    run_full_check, get_health_score, _hard_score_from_checks,
    check_file_integrity, check_index_integrity
)

PASS = FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✓ {name}")
    else:
        FAIL += 1; print(f"  ✗ {name}  {detail}")


# ========================
# T1: 硬/软指标分域
# ========================
def test_hard_soft_split():
    print("\n--- T1: 硬/软指标分域（软指标不再扣分） ---")
    ws = ensure_workspace("v310_test")

    # 1a: 健康基线（空库 + 已备份）→ 硬分 100 且 score_status=valid
    # 注意：空库无备份时 backup_freshness 会 warning → degraded（备份时效属硬分，合理）；
    # 要先 _create_backup 消除该 warning，才能得到真正的 valid。
    from sb_selfcheck import _create_backup
    _create_backup(workspace="v310_test", reason="test_fresh")
    report = run_full_check(workspace="v310_test", auto_fix=False)
    check("T1a: 空库健康基线 score=100",
          _hard_score_from_checks(report["checks"], report.get("score_status", "valid")) == 100,
          f"Got {_hard_score_from_checks(report['checks'], report.get('score_status', 'valid'))}")
    check("T1a2: score_status=valid（已备份）", report.get("score_status") == "valid", f"Got {report.get('score_status')}")

    # 1b: 仅软指标异常（伪造 duplicates/completeness/gating_flood warning）
    #     硬分应保持 100 —— 软指标是报告项，不扣分
    fake_checks = {
        "file_integrity": {"status": "healthy", "issues_found": 0},
        "index_integrity": {"status": "healthy", "issues_found": 0},
        "backup_freshness": {"status": "healthy", "issues_found": 0, "details": {"age_days": 1}},
        "duplicates": {"status": "warning", "issues_found": 5},
        "completeness": {"status": "warning", "issues_found": 3},
        "gating_flood_protection": {"status": "critical", "issues_found": 1},
        "consistency": {"status": "warning", "issues_found": 2},
        "timeliness": {"status": "warning", "issues_found": 4},
        "temporal_validity": {"status": "warning", "issues_found": 1},
        "orphans": {"status": "warning", "issues_found": 1},
        "gating_salience_bounds": {"status": "healthy", "issues_found": 0},
        "gating_demote_integrity": {"status": "healthy", "issues_found": 0},
    }
    soft_only = _hard_score_from_checks(fake_checks, "degraded")
    check("T1b: 软指标异常不扣硬分（应 100）", soft_only == 100, f"Got {soft_only}")

    # 1c: 物理完整性损坏 → 硬分扣除
    fake_checks["file_integrity"] = {"status": "critical", "issues_found": 1}
    physical = _hard_score_from_checks(fake_checks, "invalid")
    check("T1c: 物理损坏 → 硬分 0（评测无效）", physical == 0, f"Got {physical}")

    # 1d: 真损坏（门控 demote 完整性）扣硬分，软指标仍不扣
    fake_checks["file_integrity"] = {"status": "healthy", "issues_found": 0}
    fake_checks["gating_demote_integrity"] = {"status": "critical", "issues_found": 1}
    damage = _hard_score_from_checks(fake_checks, "degraded")
    check("T1d: 真损坏扣硬分（100-20=80）", damage == 80, f"Got {damage}")


# ========================
# T2: 有效性协议
# ========================
def test_validity_protocol():
    print("\n--- T2: 有效性协议（物理损坏 = 评测无效） ---")
    ws = ensure_workspace("v310_validity")
    ws_dir = get_workspace_dir("v310_validity")
    from sb_selfcheck import _create_backup
    _create_backup(workspace="v310_validity", reason="test_fresh")

    # 2a: 健康 → score_status=valid
    report = run_full_check(workspace="v310_validity", auto_fix=False)
    check("T2a: 健康报告 score_status=valid", report.get("score_status") == "valid", f"Got {report.get('score_status')}")

    # 2b: 人为破坏 memories.json → score_status=invalid + invalid_reason
    mem_path = os.path.join(ws_dir, "memories.json")
    with open(mem_path, "w", encoding="utf-8") as f:
        f.write("{ 这不是合法 JSON")
    report = run_full_check(workspace="v310_validity", auto_fix=False)
    check("T2b: 物理损坏 → score_status=invalid",
          report.get("score_status") == "invalid", f"Got {report.get('score_status')}")
    check("T2b2: invalid_reason=file_integrity",
          report.get("invalid_reason") == "file_integrity", f"Got {report.get('invalid_reason')}")

    # 2c: get_health_score 对 invalid 返回 0（不是低分，是无效）
    score = get_health_score("v310_validity")
    check("T2c: invalid 时 score=0", score == 0, f"Got {score}")

    # 2d: 修复后恢复 valid（memories.json 期望顶层为 list）
    write_json(mem_path, [])
    report = run_full_check(workspace="v310_validity", auto_fix=False)
    check("T2d: 修复后 score_status 恢复 valid", report.get("score_status") == "valid", f"Got {report.get('score_status')}")


# ========================
# T3: 修复后验证（fix_validation）
# ========================
def test_fix_validation():
    print("\n--- T3: 修复后验证（--fix 接受标准） ---")
    ws = ensure_workspace("v310_fix")

    # 3a: 健康库 auto_fix → fix_validation 存在且 accepted
    report = run_full_check(workspace="v310_fix", auto_fix=True)
    fv = report.get("fix_validation")
    check("T3a: fix_validation 字段存在", isinstance(fv, dict), f"Got {fv}")
    if isinstance(fv, dict) and "pre_score" in fv:
        check("T3a2: 健康库修复后 accepted=True", fv.get("accepted") is True, f"Got {fv}")
        check("T3a3: 有备份路径", bool(fv.get("backup_path")), f"Got {fv.get('backup_path')}")


# ========================
# T4: 向后兼容
# ========================
def test_backward_compat():
    print("\n--- T4: 向后兼容 ---")
    report = run_full_check(workspace="v310_test", auto_fix=False)
    check("T4a: run_full_check 仍返回 12 项 checks",
          len(report.get("checks", {})) == 12, f"Got {len(report.get('checks', {}))}")
    check("T4b: checks 含新顶层字段 score_status",
          "score_status" in report, "Missing score_status")
    score = get_health_score("v310_test")
    check("T4c: get_health_score 保持 0-100", 0 <= score <= 100, f"Got {score}")


# ========================
# 运行
# ========================
if __name__ == "__main__":
    test_hard_soft_split()
    test_validity_protocol()
    test_fix_validation()
    test_backward_compat()
    print(f"\n=== v3.10.0 Test Results: {PASS} passed, {FAIL} failed, {PASS + FAIL} total ===")
    sys.exit(1 if FAIL else 0)
