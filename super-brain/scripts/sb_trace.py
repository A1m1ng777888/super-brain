#!/usr/bin/env python3
"""
SuperBrain Trace - Execution trace recorder for self-evolution.

Records execution traces with three signal sources:
1. Explicit feedback (user rating: satisfied/dissatisfied) - weight 1.0
2. Implicit signals (completion, errors, timeout) - weight 0.3
3. Validation set scores (predefined tasks with known answers) - weight 0.5

Trace data model:
{
  "trace_id": "tr_20260627_xxx",
  "timestamp": "2026-06-27T02:30:00",
  "command": "memory add",
  "input": {"content": "...", "type": "fact"},
  "output": {"id": "mem_xxx", "status": "success"},
  "signals": {
    "explicit": {"rating": "satisfied", "weight": 1.0},
    "implicit": {"completed": true, "error": false, "timeout": false, "weight": 0.3},
    "validation": {"score": null, "weight": 0.5}
  },
  "weighted_score": 1.3,  # computed from signals
  "epoch": null  # set during skillopt optimization
}
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sb_core import ensure_workspace, read_json, write_json, get_timestamp, generate_id


# Signal weights (user-configurable via config)
EXPLICIT_WEIGHT = 1.0
IMPLICIT_WEIGHT = 0.3
VALIDATION_WEIGHT = 0.5

# Implicit signal values
IMPLICIT_VALUES = {
    "completed": 0.5,    # task completed successfully
    "error": -1.0,       # execution error occurred
    "timeout": -0.5,     # execution timed out
    "empty_result": -0.2 # returned empty/null result
}


def get_trace_dir(workspace=None):
    """Get trace directory path."""
    from sb_core import load_config
    config = load_config()
    ws_dir = ensure_workspace(workspace)
    trace_dir = os.path.join(ws_dir, "traces")
    os.makedirs(trace_dir, exist_ok=True)
    return trace_dir


def compute_weighted_score(explicit=None, implicit=None, validation=None):
    """
    Compute weighted score from three signal sources.
    
    Args:
        explicit: dict with 'rating' (satisfied/dissatisfied/none) and optional 'weight'
        implicit: dict with signal flags (completed, error, timeout, empty_result)
        validation: dict with 'score' (float 0-1) and optional 'weight'
    
    Returns:
        float: weighted score in range [-2.0, +2.0] approximately
    """
    score = 0.0
    
    # Explicit feedback (highest priority)
    if explicit:
        w = explicit.get("weight", EXPLICIT_WEIGHT)
        rating = explicit.get("rating", "none")
        if rating == "satisfied":
            score += 2.0 * w
        elif rating == "dissatisfied":
            score -= 2.0 * w
        # "none" or unknown: no contribution
    
    # Implicit signals
    if implicit:
        w = implicit.get("weight", IMPLICIT_WEIGHT)
        if implicit.get("completed"):
            score += IMPLICIT_VALUES["completed"] * w
        if implicit.get("error"):
            score += IMPLICIT_VALUES["error"] * w
        if implicit.get("timeout"):
            score += IMPLICIT_VALUES["timeout"] * w
        if implicit.get("empty_result"):
            score += IMPLICIT_VALUES["empty_result"] * w
    
    # Validation set score
    if validation and validation.get("score") is not None:
        w = validation.get("weight", VALIDATION_WEIGHT)
        # score is 0-1, map to -1 to +1
        val_score = (validation["score"] - 0.5) * 2.0
        score += val_score * w
    
    return round(score, 4)


def record_trace(command, input_data, output_data, workspace=None,
                explicit_rating=None, implicit_signals=None, validation_score=None):
    """
    Record an execution trace.
    
    Args:
        command: str, the superbrain subcommand executed (e.g., "memory add")
        input_data: dict, input arguments
        output_data: dict, output result
        workspace: str, workspace name
        explicit_rating: str or None, "satisfied" / "dissatisfied"
        implicit_signals: dict, e.g. {"completed": True, "error": False, "timeout": False}
        validation_score: float or None, 0-1 score on validation task
    
    Returns:
        dict: the recorded trace
    """
    trace_id = generate_id("tr")
    
    # Build signals dict
    explicit = None
    if explicit_rating:
        explicit = {"rating": explicit_rating, "weight": EXPLICIT_WEIGHT}
    
    implicit = implicit_signals or {"completed": True, "error": False, "timeout": False}
    implicit["weight"] = IMPLICIT_WEIGHT
    
    validation = None
    if validation_score is not None:
        validation = {"score": validation_score, "weight": VALIDATION_WEIGHT}
    
    weighted_score = compute_weighted_score(explicit, implicit, validation)
    
    trace = {
        "trace_id": trace_id,
        "timestamp": get_timestamp(),
        "command": command,
        "input": input_data,
        "output": output_data,
        "signals": {
            "explicit": explicit,
            "implicit": implicit,
            "validation": validation
        },
        "weighted_score": weighted_score,
        "epoch": None,
        "used_in_optimization": False
    }
    
    # Append to traces file
    trace_dir = get_trace_dir(workspace)
    traces_path = os.path.join(trace_dir, "traces.json")
    traces = read_json(traces_path) or []
    traces.append(trace)
    write_json(traces_path, traces)
    
    # Also update meta
    meta_path = os.path.join(trace_dir, "meta.json")
    meta = read_json(meta_path) or {"total_traces": 0, "avg_score": 0.0}
    meta["total_traces"] = len(traces)
    meta["avg_score"] = round(sum(t["weighted_score"] for t in traces) / len(traces), 4)
    meta["last_updated"] = get_timestamp()
    write_json(meta_path, meta)
    
    return trace


def add_explicit_feedback(trace_id, rating, workspace=None):
    """
    Add explicit feedback to an existing trace.
    This can be called later (e.g., user provides feedback after seeing output).
    """
    trace_dir = get_trace_dir(workspace)
    traces_path = os.path.join(trace_dir, "traces.json")
    traces = read_json(traces_path) or []
    
    for trace in traces:
        if trace["trace_id"] == trace_id:
            trace["signals"]["explicit"] = {"rating": rating, "weight": EXPLICIT_WEIGHT}
            trace["weighted_score"] = compute_weighted_score(
                trace["signals"]["explicit"],
                trace["signals"]["implicit"],
                trace["signals"]["validation"]
            )
            trace["feedback_updated"] = get_timestamp()
            write_json(traces_path, traces)
            return trace
    
    return None


def get_traces(workspace=None, min_score=None, max_score=None, command=None, limit=100):
    """Get traces with filters."""
    trace_dir = get_trace_dir(workspace)
    traces_path = os.path.join(trace_dir, "traces.json")
    traces = read_json(traces_path) or []
    
    if min_score is not None:
        traces = [t for t in traces if t["weighted_score"] >= min_score]
    if max_score is not None:
        traces = [t for t in traces if t["weighted_score"] <= max_score]
    if command:
        traces = [t for t in traces if t["command"] == command]
    
    traces.sort(key=lambda t: t["timestamp"], reverse=True)
    return traces[:limit]


def get_trace_stats(workspace=None):
    """Get trace statistics."""
    traces = get_traces(workspace, limit=10000)
    if not traces:
        return {"total": 0}
    
    scores = [t["weighted_score"] for t in traces]
    explicit_ratings = [t["signals"]["explicit"]["rating"] 
                        for t in traces if t["signals"]["explicit"]]
    
    return {
        "total": len(traces),
        "avg_score": round(sum(scores) / len(scores), 4),
        "min_score": min(scores),
        "max_score": max(scores),
        "explicit_feedback_count": len(explicit_ratings),
        "satisfied_count": explicit_ratings.count("satisfied"),
        "dissatisfied_count": explicit_ratings.count("dissatisfied"),
        "command_distribution": _count_by_command(traces)
    }


def _count_by_command(traces):
    """Count traces per command."""
    counts = {}
    for t in traces:
        cmd = t["command"]
        counts[cmd] = counts.get(cmd, 0) + 1
    return counts


def export_traces_for_skillopt(workspace=None, output_path=None):
    """
    Export traces in SkillOpt-compatible format for optimization.
    Returns path to exported file.
    """
    traces = get_traces(workspace, limit=10000)
    
    # Group by success/failure
    successes = [t for t in traces if t["weighted_score"] > 0]
    failures = [t for t in traces if t["weighted_score"] <= 0]
    
    export = {
        "total_traces": len(traces),
        "success_count": len(successes),
        "failure_count": len(failures),
        "success_traces": successes,
        "failure_traces": failures,
        "exported_at": get_timestamp()
    }
    
    if output_path is None:
        trace_dir = get_trace_dir(workspace)
        output_path = os.path.join(trace_dir, "export_for_skillopt.json")
    
    write_json(output_path, export)
    return output_path
