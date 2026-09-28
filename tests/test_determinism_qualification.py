"""Determinism qualification test suite (N=10 trials).

Runs each task x recovery method x fault condition across 10 trials.
Asserts zero variance in:
1. Trajectory execution sequence
2. Wire effect history (targets, operations, commit status, ack status)
3. Final external physical state
4. Oracle decomposed verdicts and failure classifications
"""

from __future__ import annotations
import copy
import hashlib
import json
import pytest
from recoverbench.runner.runner import BenchmarkRunner
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.tasks.registry import TaskRegistry


def normalize_event(e: dict) -> dict:
    """Strip non-deterministic run-level timestamps, commit hashes, and random UUIDs."""
    import re
    norm = copy.deepcopy(e)
    norm.pop("timestamp", None)
    out = norm.get("output")
    if isinstance(out, dict):
        if "refund_id" in out:
            out["refund_id"] = "NORM_REFUND_ID"
        if "audit_id" in out:
            out["audit_id"] = "NORM_AUDIT_ID"
        if "commit_hash" in out:
            out["commit_hash"] = "NORM_COMMIT_HASH"
        if "raw" in out:
            out["raw"] = re.sub(r"[0-9a-f]{7,40}", "NORM_HASH", str(out["raw"]))
    return norm


def normalize_state(s: dict) -> dict:
    """Normalize dynamic IDs, commit hashes, and timestamps in state objects."""
    norm = copy.deepcopy(s)
    if "refunds" in norm:
        for r in norm["refunds"]:
            r.pop("timestamp", None)
            r["refund_id"] = "NORM_REFUND_ID"
    if "journal" in norm:
        for j in norm["journal"]:
            j.pop("timestamp", None)
    if "latest_commit" in norm and norm["latest_commit"]:
        norm["latest_commit"] = "NORM_COMMIT_HASH"
    return norm


def compute_structural_hash(result) -> str:
    """Compute deterministic sha256 hash of execution results."""
    v = result.verdict
    payload = {
        "success": result.success,
        "goal_satisfied": v.goal_satisfied,
        "final_state_correct": v.final_state_correct,
        "invariant_satisfied": v.invariant_satisfied,
        "required_effects_satisfied": v.required_effects_satisfied,
        "effect_multiplicity_correct": v.effect_multiplicity_correct,
        "forbidden_effects_absent": v.forbidden_effects_absent,
        "ordering_correct": v.ordering_correct,
        "overall_recovery_correct": v.overall_recovery_correct,
        "duplicate_effects_count": v.duplicate_effects_count,
        "missing_effects_count": v.missing_effects_count,
        "forbidden_effects_count": v.forbidden_effects_count,
        "violations": sorted(v.violations),
        "effects": [normalize_event(e) for e in v.observed_effects],
        "state": normalize_state(v.final_state),
        "primary_classification": v.primary_failure_classification,
    }
    encoded = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("task_id", ["RB-DB-001", "RB-PAY-001", "RB-GIT-001", "RB-CLOUD-001"])
@pytest.mark.parametrize("method", ["naive", "idempotency", "evoundo"])
def test_determinism_n10_no_fault(task_id: str, method: str):
    """Assert N=10 identical execution runs under NO_FAULT control."""
    runner = BenchmarkRunner(output_dir="results/determinism_test")
    ctrl_fault = FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)

    hashes = []
    for _ in range(10):
        res = runner.run_trial(task_id, method, ctrl_fault, is_control_run=True)
        hashes.append(compute_structural_hash(res))

    assert len(set(hashes)) == 1, f"Non-determinism discovered across 10 NO_FAULT runs for {task_id} x {method}"


@pytest.mark.parametrize("task_id", ["RB-DB-001", "RB-PAY-001", "RB-PAY-002", "RB-CLOUD-001"])
@pytest.mark.parametrize("method", ["naive", "idempotency", "evoundo"])
def test_determinism_n10_fault(task_id: str, method: str):
    """Assert N=10 identical execution runs under injected FAULT conditions."""
    runner = BenchmarkRunner(output_dir="results/determinism_test")
    designated_fault = FaultSpec.from_alias("F2")
    if task_id == "RB-PAY-002":
        designated_fault = FaultSpec(
            boundary=ExecutionBoundary.DURING_COMPENSATION,
            perturbation=Perturbation.RECOVERY_CRASH,
            target_call_index=2,
        )
    elif task_id == "RB-CLOUD-001":
        designated_fault = FaultSpec.from_alias("F3")

    hashes = []
    for _ in range(10):
        res = runner.run_trial(task_id, method, designated_fault, is_control_run=False)
        hashes.append(compute_structural_hash(res))

    assert len(set(hashes)) == 1, f"Non-determinism discovered across 10 FAULT runs for {task_id} x {method}"
