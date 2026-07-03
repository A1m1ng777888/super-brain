#!/usr/bin/env python3
"""SuperBrain v2.0.0 — sb_trace + sb_skillopt test suite.
Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import sys
import os
import json
import shutil
import tempfile

# Add scripts to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from sb_core import ensure_workspace, write_json, read_json, load_config, save_config, get_timestamp, generate_id
from sb_trace import (
    compute_weighted_score, record_trace, add_explicit_feedback,
    get_traces, get_trace_stats, export_traces_for_skillopt,
    EXPLICIT_WEIGHT, IMPLICIT_WEIGHT, VALIDATION_WEIGHT, IMPLICIT_VALUES
)
from sb_skillopt import (
    load_skill_file, save_skill_file, compute_edit_budget,
    analyze_traces_for_reflection, generate_edit_suggestions, apply_edits,
    compute_validation_score, run_skillopt_epoch, optimize_external_skill,
    self_evolve, get_optimization_history, get_rejected_buffer,
    get_default_validation_tasks, skillopt_status
)

passed = 0
failed = 0
errors = []

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} - {detail}")

def section(title):
    print(f"\n=== {title} ===")

# === SETUP ===
section("Setup")

# Clean workspace
ensure_workspace("test")
# Clear trace data
trace_dir = os.path.join(ensure_workspace("test"), "traces")
if os.path.exists(trace_dir):
    shutil.rmtree(trace_dir)
os.makedirs(trace_dir, exist_ok=True)
write_json(os.path.join(trace_dir, "traces.json"), [])
write_json(os.path.join(trace_dir, "meta.json"), {"total_traces": 0, "avg_score": 0.0})
# Clear skillopt data
skillopt_dir = os.path.join(ensure_workspace("test"), "skillopt")
if os.path.exists(skillopt_dir):
    shutil.rmtree(skillopt_dir)
os.makedirs(skillopt_dir, exist_ok=True)
write_json(os.path.join(skillopt_dir, "optimization_history.json"), [])
write_json(os.path.join(skillopt_dir, "rejected_buffer.json"), [])
print("  Test workspace cleaned.")


# ==================== sb_trace tests ====================

section("compute_weighted_score")

# Explicit feedback
s1 = compute_weighted_score(explicit={"rating": "satisfied", "weight": EXPLICIT_WEIGHT})
test("satisfied = +2.0", s1 == 2.0, f"Got {s1}")

s2 = compute_weighted_score(explicit={"rating": "dissatisfied", "weight": EXPLICIT_WEIGHT})
test("dissatisfied = -2.0", s2 == -2.0, f"Got {s2}")

s3 = compute_weighted_score(explicit={"rating": "none", "weight": EXPLICIT_WEIGHT})
test("no rating = 0", s3 == 0.0, f"Got {s3}")

# Implicit signals
s4 = compute_weighted_score(implicit={"completed": True, "error": False, "timeout": False, "weight": IMPLICIT_WEIGHT})
test("completed = +0.15", s4 == 0.15, f"Got {s4}")

s5 = compute_weighted_score(implicit={"completed": False, "error": True, "timeout": False, "weight": IMPLICIT_WEIGHT})
test("error = -0.3", s5 == -0.3, f"Got {s5}")

s6 = compute_weighted_score(implicit={"completed": False, "error": False, "timeout": True, "weight": IMPLICIT_WEIGHT})
test("timeout = -0.15", s6 == -0.15, f"Got {s6}")

# Validation
s7 = compute_weighted_score(validation={"score": 1.0, "weight": VALIDATION_WEIGHT})
test("perfect validation = +0.5", s7 == 0.5, f"Got {s7}")

s8 = compute_weighted_score(validation={"score": 0.0, "weight": VALIDATION_WEIGHT})
test("zero validation = -0.5", s8 == -0.5, f"Got {s8}")

s9 = compute_weighted_score(validation={"score": 0.5, "weight": VALIDATION_WEIGHT})
test("mid validation = 0.0", s9 == 0.0, f"Got {s9}")

# Combined signals
s10 = compute_weighted_score(
    explicit={"rating": "satisfied", "weight": EXPLICIT_WEIGHT},
    implicit={"completed": True, "error": False, "timeout": False, "weight": IMPLICIT_WEIGHT},
    validation={"score": 0.8, "weight": VALIDATION_WEIGHT}
)
# 2.0 + 0.15 + (0.8-0.5)*2*0.5 = 2.0 + 0.15 + 0.3 = 2.45
test("combined satisfied+completed+good_validation", s10 == 2.45, f"Got {s10}")


section("record_trace")

# Record with explicit feedback
t1 = record_trace("memory add", {"content": "test"}, {"id": "mem_001"}, workspace="test",
                  explicit_rating="satisfied")
test("trace recorded with explicit", t1 is not None and t1["weighted_score"] == 2.15,
     f"Got score {t1.get('weighted_score') if t1 else None}")

# Record with implicit
t2 = record_trace("memory search", {"query": "abc"}, {"results": []}, workspace="test",
                  implicit_signals={"completed": True, "error": False, "timeout": False, "empty_result": True})
expected_s2 = IMPLICIT_VALUES["completed"] * IMPLICIT_WEIGHT + IMPLICIT_VALUES["empty_result"] * IMPLICIT_WEIGHT
test("trace with empty result", abs(t2["weighted_score"] - expected_s2) < 0.001,
     f"Got {t2['weighted_score']}, expected {expected_s2}")

# Record with validation
t3 = record_trace("selfcheck", {}, {"overall_status": "healthy"}, workspace="test",
                  validation_score=0.9)
expected_s3 = (0.9 - 0.5) * 2.0 * VALIDATION_WEIGHT + IMPLICIT_VALUES["completed"] * IMPLICIT_WEIGHT
test("trace with validation score", abs(t3["weighted_score"] - expected_s3) < 0.001,
     f"Got {t3['weighted_score']}, expected {expected_s3}")

# Record failure
t4 = record_trace("memory add", {"content": "fail"}, {"error": "disk full"}, workspace="test",
                  implicit_signals={"completed": False, "error": True, "timeout": False})
test("failure trace", t4["weighted_score"] < 0, f"Got {t4['weighted_score']}")


section("add_explicit_feedback")

# Add feedback to t4
updated = add_explicit_feedback(t4["trace_id"], "dissatisfied", workspace="test")
test("added explicit dissatisfied", updated is not None and updated["weighted_score"] < -1.0,
     f"Got {updated['weighted_score'] if updated else None}")

# Non-existent trace
notfound = add_explicit_feedback("nonexistent_id", "satisfied", workspace="test")
test("non-existent trace returns None", notfound is None)


section("get_traces")

# Filter by score
all_traces = get_traces(workspace="test")
test("get all traces", len(all_traces) == 4, f"Got {len(all_traces)}")

positive = get_traces(workspace="test", min_score=0)
test("filter min_score>=0", all(t["weighted_score"] >= 0 for t in positive))

negative = get_traces(workspace="test", max_score=0)
test("filter max_score<=0", len(negative) > 0 and all(t["weighted_score"] <= 0 for t in negative))

# Filter by command
memory_traces = get_traces(workspace="test", command="memory add")
test("filter by command", len(memory_traces) == 2, f"Got {len(memory_traces)}")


section("get_trace_stats")

stats = get_trace_stats(workspace="test")
test("stats total = 4", stats["total"] == 4, f"Got {stats['total']}")
test("stats has avg_score", "avg_score" in stats)
test("stats has command_distribution", "command_distribution" in stats)
test("stats has explicit feedback count", stats["explicit_feedback_count"] == 2,
     f"Got {stats['explicit_feedback_count']}")


section("export_traces_for_skillopt")

export_path = export_traces_for_skillopt(workspace="test")
test("export file exists", os.path.exists(export_path))
export_data = read_json(export_path)
test("export has success/failure counts", 
     export_data["success_count"] + export_data["failure_count"] == 4)
test("export has total_traces", export_data["total_traces"] == 4)


# ==================== sb_skillopt tests ====================

section("load/save_skill_file")

# Create a test SKILL.md
test_skill = os.path.join(tempfile.gettempdir(), "test_skillopt_skill.md")
test_fm = {"name": "test-skill", "version": "v1.0", "description": "Test skill for skillopt"}
test_content = "# Test Skill\n\n## 触发词\n\n- test, 测试\n\n## 子命令\n\n### test add\n\n添加测试数据\n"
save_skill_file(test_skill, test_fm, test_content)

fm_load, cont_load = load_skill_file(test_skill)
test("load frontmatter", fm_load == test_fm)
# strip() normalizes trailing whitespace (save → read round trip)
test("load content", cont_load.strip() == test_content.strip())

# Save without frontmatter
test_skill_no_fm = os.path.join(tempfile.gettempdir(), "test_skillopt_no_fm.md")
save_skill_file(test_skill_no_fm, {}, "No frontmatter content")
fm2, c2 = load_skill_file(test_skill_no_fm)
test("load without frontmatter", fm2 == {} and c2 == "No frontmatter content")

# Clean up
os.remove(test_skill)
os.remove(test_skill_no_fm)


section("compute_edit_budget")

test("epoch 1 budget = 4", compute_edit_budget(1) == 4)
test("epoch 2 budget = 4", compute_edit_budget(2) == 4)
test("epoch 3 budget = 3", compute_edit_budget(3) == 3)
test("epoch 5 budget = 3", compute_edit_budget(5) == 3)
test("epoch 6 budget = 2", compute_edit_budget(6) == 2)
test("epoch 10 budget = 2", compute_edit_budget(10) == 2)


section("analyze_traces_for_reflection")

# Use our recorded traces from earlier
traces = get_traces(workspace="test")
reflection = analyze_traces_for_reflection(traces, test_content)
test("reflection total = 4", reflection["total_traces"] == 4)
test("reflection has failure_patterns", len(reflection["failure_patterns"]) > 0)
test("reflection has success_patterns", len(reflection["success_patterns"]) > 0)


section("generate_edit_suggestions")

edits = generate_edit_suggestions(reflection, test_content, 4)
test("edits generated from reflection", len(edits) > 0, f"Got {len(edits)} edits")
test("edits within budget", len(edits) <= 4)

# Test budget limiting
edits_1 = generate_edit_suggestions(reflection, test_content, 1)
test("edits limited by budget", len(edits_1) == 1, f"Got {len(edits_1)}")

# Test empty reflection
empty_reflection = {
    "epoch": 0,
    "total_traces": 0,
    "success_count": 0,
    "failure_count": 0,
    "success_patterns": [],
    "failure_patterns": [],
    "edit_suggestions": []
}
edits_empty = generate_edit_suggestions(empty_reflection, test_content, 4)
test("no edits from empty reflection", len(edits_empty) == 0)


section("apply_edits")

test_content_for_edit = "## Section A\n\nSome text about A.\n\n## Section B\n\nSome text about B.\n"

# Test add
add_edits = [{"type": "add", "content": "\n### Added Section\n\nNew content.\n", "reason": "test add"}]
new_content, applied = apply_edits(test_content_for_edit, add_edits)
test("add edit applied", "Added Section" in new_content and len(applied) == 1)

# Test replace
replace_edits = [{"type": "replace", "target": "text about A.", "content": "text about AAA.", "reason": "test replace"}]
new_content2, applied2 = apply_edits(test_content_for_edit, replace_edits)
test("replace edit applied", "text about AAA." in new_content2 and "text about A." not in new_content2)
test("replace applied count", len(applied2) == 1)

# Test replace not found
replace_nf = [{"type": "replace", "target": "nonexistent text", "content": "replacement", "reason": "test"}]
new_content3, applied3 = apply_edits(test_content_for_edit, replace_nf)
test("replace not found = no change", new_content3 == test_content_for_edit and len(applied3) == 0)

# Test delete
delete_edits = [{"type": "delete", "target": "Some text about A.", "reason": "test delete"}]
new_content4, applied4 = apply_edits(test_content_for_edit, delete_edits)
test("delete edit applied", "Some text about A." not in new_content4 and len(applied4) == 1)


section("compute_validation_score")

# Create a complete-looking skill
complete_skill = os.path.join(tempfile.gettempdir(), "complete_skill.md")
full_content = (
    "# Complete Skill\n\n"
    "## 触发词 (Triggers)\n\n"
    "- test\n\n"
    "## 子命令 (Subcommands)\n\n"
    "### cmd1\n\n"
    "## 示例 (Examples)\n\n"
    "```python\nprint('example')\n```\n\n"
    "## 常见错误处理 (Troubleshooting)\n\n"
    "## 最佳实践 (Best Practices)\n\n"
    + "x" * 1000  # length > 1000
)
save_skill_file(complete_skill, {}, full_content)
score_good = compute_validation_score(complete_skill, [])
test("complete skill score = 1.0", score_good == 1.0, f"Got {score_good}")

# Create a minimal skill
minimal_skill = os.path.join(tempfile.gettempdir(), "minimal_skill.md")
save_skill_file(minimal_skill, {}, "# Minimal\n\ntest command\n")
score_low = compute_validation_score(minimal_skill, [])
test("minimal skill score < 0.5", score_low < 0.5, f"Got {score_low}")

# Non-existent skill
score_none = compute_validation_score("/nonexistent/skill.md", [])
test("non-existent skill = 0.0", score_none == 0.0)

os.remove(complete_skill)
os.remove(minimal_skill)


section("run_skillopt_epoch")

# Use our test traces and a test skill
test_skill_epoch = os.path.join(tempfile.gettempdir(), "epoch_test_skill.md")
save_skill_file(test_skill_epoch, {"name": "epoch-test", "version": "v1.0"},
                "# Epoch Test Skill\n\n## 触发词\n\ntest\n\n" + "x" * 800)

result = run_skillopt_epoch(test_skill_epoch, traces, [], epoch=1, workspace="test")
test("epoch has result", result is not None)
test("epoch has epoch number", result["epoch"] == 1)
test("epoch has reflection", "reflection" in result)
test("epoch has current_score", "current_score" in result)
test("epoch has candidate_score", "candidate_score" in result)

# Clean up
if os.path.exists(test_skill_epoch):
    os.remove(test_skill_epoch)
candidate = test_skill_epoch + ".candidate"
if os.path.exists(candidate):
    os.remove(candidate)


section("optimization history & rejected buffer")

history = get_optimization_history(workspace="test")
test("history is list", isinstance(history, list))
# At least the epoch we just ran should be in history (if accepted)
print(f"  History entries: {len(history)}")

rejected = get_rejected_buffer(workspace="test")
test("rejected buffer is list", isinstance(rejected, list))
print(f"  Rejected entries: {len(rejected)}")


section("get_default_validation_tasks")

tasks = get_default_validation_tasks()
test("default tasks has 4 items", len(tasks) == 4, f"Got {len(tasks)}")
test("tasks have required fields", all("name" in t and "command" in t for t in tasks))


section("skillopt_status")

status = skillopt_status(workspace="test")
test("status has optimization_epochs", "optimization_epochs" in status)
test("status has trace_stats", "trace_stats" in status)
test("status has rejected_edits", "rejected_edits" in status)
print(f"  Status: {json.dumps(status, ensure_ascii=False)}")


section("self_evolve")

# self_evolve needs traces -> we have them
evolve_result = self_evolve(epochs=2, workspace="test")
test("self_evolve returns result", evolve_result is not None)
test("self_evolve has epochs", "epochs_completed" in evolve_result)
print(f"  Epochs completed: {evolve_result.get('epochs_completed', 'N/A')}")
print(f"  Final status: {evolve_result.get('final_status', 'N/A')}")


section("optimize_external_skill")

# Optimize a temporary skill
external_skill = os.path.join(tempfile.gettempdir(), "external_skill.md")
save_skill_file(external_skill, {"name": "external-test", "version": "v1.0"},
                "# External Skill\n\n## 触发词\n\nexternal, test\n\n## 子命令\n\n### ext add\n\n" + "x" * 800)

opt_result = optimize_external_skill(external_skill, traces, [], epochs=2, workspace="test")
test("external optimize returns result", opt_result is not None)
test("external optimize has results", len(opt_result["results"]) > 0)

os.remove(external_skill)
cand = external_skill + ".candidate"
if os.path.exists(cand):
    os.remove(cand)


# ==================== Edge Cases ====================

section("Edge Cases")

# compute_weighted_score with None signals
s_none = compute_weighted_score(explicit=None, implicit=None, validation=None)
test("all None = 0.0", s_none == 0.0, f"Got {s_none}")

# get_traces on empty workspace (fresh)
empty_traces = get_traces(workspace="test", limit=0)
test("limit=0 returns empty list", len(empty_traces) == 0)

# analyze_traces_for_reflection with empty list
reflection_empty = analyze_traces_for_reflection([], "")
test("empty traces reflection", reflection_empty["total_traces"] == 0)

# skillopt_status on empty workspace (fresh)
os.makedirs(os.path.join(ensure_workspace("fresh_test"), "skillopt"), exist_ok=True)
status_empty = skillopt_status(workspace="fresh_test")
test("empty status has 0 epochs", status_empty["optimization_epochs"] == 0)


# ==================== SUMMARY ====================

section("Summary")
print(f"  Tests passed: {passed}")
print(f"  Tests failed: {failed}")
if errors:
    print(f"\n  Failed tests:")
    for e in errors:
        print(f"    - {e}")

if failed == 0:
    print("\n  *** ALL TESTS PASSED ***")
    sys.exit(0)
else:
    print(f"\n  *** {failed} TEST(S) FAILED ***")
    sys.exit(1)
