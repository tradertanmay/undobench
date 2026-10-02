"""Head-to-head evaluation test for Phase RB-0 prototype."""

import pytest
from recoverbench.runner.runner import BenchmarkRunner
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation


try:
    from recoverbench.recovery_methods.evoundo_adapter import EVOUNDO_AVAILABLE
except ImportError:
    EVOUNDO_AVAILABLE = False


def test_payment_refund_head_to_head():
    runner = BenchmarkRunner(output_dir="results/test_runs")
    f2 = FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS)

    # 1. Control Run (NO_FAULT) -> Must succeed for all methods
    ctrl_fault = FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)
    res_ctrl = runner.run_trial("RB-PAY-001", "naive", ctrl_fault, is_control_run=True)
    assert res_ctrl.success is True
    assert res_ctrl.verdict.is_safe_and_successful is True

    # 2. Naive Retry under Lost-ACK (F2) -> FAILS: double refund committed!
    res_naive = runner.run_trial("RB-PAY-001", "naive", f2)
    assert res_naive.success is False
    assert res_naive.verdict.duplicate_effects_count >= 1
    assert any("Duplicate effect" in v for v in res_naive.verdict.violations)

    # 3. Idempotency Key under Lost-ACK (F2) -> SUCCEEDS: gateway deduplicates key!
    res_idem = runner.run_trial("RB-PAY-001", "idempotency", f2)
    assert res_idem.success is True
    assert res_idem.verdict.duplicate_effects_count == 0
    assert res_idem.verdict.exactly_once_satisfied is True

    # 4. EvoUndo under Lost-ACK (F2) -> Evaluated under identical oracle
    if EVOUNDO_AVAILABLE:
        res_evoundo = runner.run_trial("RB-PAY-001", "evoundo", f2)
        # Measured with the exact same oracle: verdict is recorded without privileged pass conditions
        assert res_evoundo.verdict.task_id == "RB-PAY-001"
        assert res_evoundo.verdict.method == "evoundo"
        assert isinstance(res_evoundo.verdict.duplicate_effects_count, int)


def test_suite_eval_runner():
    runner = BenchmarkRunner(output_dir="results/suite_test")
    methods = ["naive", "idempotency", "evoundo"] if EVOUNDO_AVAILABLE else ["naive", "idempotency"]
    summary = runner.run_suite(
        task_ids=["RB-PAY-001", "RB-DB-001"],
        recovery_methods=methods,
        include_controls=True,
        trials=1,
    )

    expected_total = 2 * len(methods) * 2  # 2 tasks * len(methods) * (1 control + 1 fault)
    assert summary["total_runs"] == expected_total
    summaries = summary["summaries"]

    # Naive retry shows duplicate effect rate > 0 across both tasks
    assert summaries["naive_retry"]["duplicate_effect_rate"] > 0
    # Idempotency succeeds on payments (RB-PAY-001) but duplicates on raw SQL updates without key support (RB-DB-001)
    assert summaries["idempotency"]["recovery_success_rate"] > 0
    # EvoUndo performance is objectively measured under the identical oracle without assumed success
    if EVOUNDO_AVAILABLE:
        assert summaries["evoundo"]["control_success_rate"] == 1.0
        assert "recovery_success_rate" in summaries["evoundo"]
