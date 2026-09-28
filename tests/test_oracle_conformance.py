"""Clean-room conformance suite for RecoverBench State & Effect History Oracle.

Verifies that the Oracle accurately evaluates, discriminates, and classifies 8 deterministic
reference agent behavioral archetypes without bias toward any specific recovery method:
1. Perfect_NoFault_Agent -> Evaluates 100% SUCCESS
2. AlwaysRetry_Agent -> Evaluates UNSAFE_RETRY / DUPLICATE_EFFECT on non-idempotent Lost-ACK
3. NeverRetry_Agent -> Evaluates MISSING_EFFECT / RECOVERY_ABORT on transient failure
4. DuplicateEffect_Agent -> Evaluates DUPLICATE_EFFECT on duplicate mutation
5. SkipEffect_Agent -> Evaluates MISSING_EFFECT on omitted required step
6. CompensateCorrectly_Agent -> Evaluates SUCCESS / correct recovery on clean compensation
7. CompensateIncorrectly_Agent -> Evaluates FAILED_COMPENSATION / EXTERNAL_STATE_DIVERGENCE
8. ConflictBlind_Agent -> Evaluates CONCURRENT_CONFLICT_LOSS / EXTERNAL_STATE_DIVERGENCE
"""

import pytest
from recoverbench.faults.injector import DeterministicFaultInjector
from recoverbench.faults.proxy import ToolProxyRegistry
from recoverbench.oracle.state_oracle import StateOracle
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.tasks.registry import TaskRegistry


def test_ref_agent_1_perfect_nofault():
    """Reference Agent 1: Executes task steps exactly as required under NO_FAULT."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-DB-001")
    proxy_registry.injector = DeterministicFaultInjector(
        FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)
    )

    deduct = proxy_registry.get_proxied_tool("deduct_account_balance")
    credit = proxy_registry.get_proxied_tool("credit_account_balance")

    deduct(account_id="acc_alice", amount=30.0)
    credit(account_id="acc_bob", amount=30.0)

    verdict = StateOracle.evaluate(
        task=task_spec,
        sandbox=sandbox,
        proxy_registry=proxy_registry,
        method_name="perfect_agent",
        boundary_name="NO_FAULT",
        perturbation_name="NONE",
        agent_succeeded=True,
    )

    assert verdict.overall_recovery_correct is True
    assert verdict.final_state_valid is True
    assert verdict.duplicate_effects_count == 0
    assert verdict.missing_effects_count == 0
    assert verdict.primary_failure_classification == "SUCCESS"


def test_ref_agent_2_always_retry():
    """Reference Agent 2: Blindly retries mutating tool calls on Lost-ACK, causing duplicate effects."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-DB-001")
    proxy_registry.injector = DeterministicFaultInjector(
        FaultSpec(
            boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK,
            perturbation=Perturbation.ACK_LOSS,
            target_call_index=1,
        )
    )

    deduct = proxy_registry.get_proxied_tool("deduct_account_balance")
    credit = proxy_registry.get_proxied_tool("credit_account_balance")

    # Attempt 1: succeeds externally, but raises Lost-ACK
    with pytest.raises(Exception):
        deduct(account_id="acc_alice", amount=30.0)

    # AlwaysRetry Agent blindly retries deduct
    deduct(account_id="acc_alice", amount=30.0)
    credit(account_id="acc_bob", amount=30.0)

    verdict = StateOracle.evaluate(
        task=task_spec,
        sandbox=sandbox,
        proxy_registry=proxy_registry,
        method_name="always_retry",
        boundary_name="POST_MUTATION_PRE_ACK",
        perturbation_name="ACK_LOSS",
        agent_succeeded=True,
    )

    assert verdict.overall_recovery_correct is False
    assert verdict.duplicate_effects_count >= 1
    assert verdict.primary_failure_classification in ("UNSAFE_RETRY", "DUPLICATE_EFFECT")


def test_ref_agent_3_never_retry():
    """Reference Agent 3: Aborts immediately on first transient failure and never retries."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-DB-001")
    proxy_registry.injector = DeterministicFaultInjector(
        FaultSpec(
            boundary=ExecutionBoundary.PRE_MUTATION,
            perturbation=Perturbation.NETWORK_TIMEOUT,
            target_call_index=1,
        )
    )

    deduct = proxy_registry.get_proxied_tool("deduct_account_balance")

    agent_succeeded = True
    error_msg = None
    try:
        deduct(account_id="acc_alice", amount=30.0)
    except Exception as ex:
        # NeverRetry agent aborts immediately
        agent_succeeded = False
        error_msg = str(ex)

    verdict = StateOracle.evaluate(
        task=task_spec,
        sandbox=sandbox,
        proxy_registry=proxy_registry,
        method_name="never_retry",
        boundary_name="PRE_MUTATION",
        perturbation_name="NETWORK_TIMEOUT",
        agent_succeeded=agent_succeeded,
        agent_error=error_msg,
    )

    assert verdict.overall_recovery_correct is False
    assert verdict.missing_effects_count >= 1
    assert verdict.primary_failure_classification in ("MISSING_EFFECT", "RECOVERY_ABORT", "TASK_FAILURE")


def test_ref_agent_4_duplicate_effect():
    """Reference Agent 4: Intentionally executes mutating tool calls twice under NO_FAULT."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-DB-001")
    proxy_registry.injector = DeterministicFaultInjector(
        FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)
    )

    deduct = proxy_registry.get_proxied_tool("deduct_account_balance")
    credit = proxy_registry.get_proxied_tool("credit_account_balance")

    deduct(account_id="acc_alice", amount=30.0)
    # Duplicate execution of deduct!
    deduct(account_id="acc_alice", amount=30.0)
    credit(account_id="acc_bob", amount=30.0)

    verdict = StateOracle.evaluate(
        task=task_spec,
        sandbox=sandbox,
        proxy_registry=proxy_registry,
        method_name="duplicate_agent",
        boundary_name="NO_FAULT",
        perturbation_name="NONE",
        agent_succeeded=True,
    )

    assert verdict.overall_recovery_correct is False
    assert verdict.duplicate_effects_count >= 1
    assert verdict.primary_failure_classification in ("DUPLICATE_EFFECT", "UNSAFE_RETRY")


def test_ref_agent_5_skip_effect():
    """Reference Agent 5: Deliberately skips one of the required workflow steps."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-PAY-002")
    proxy_registry.injector = DeterministicFaultInjector(
        FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)
    )

    # RB-PAY-002 requires 2 journal entries (charge + compensating reversal).
    # SkipEffect Agent posts entry 1, but skips entry 2!
    post_entry = proxy_registry.get_proxied_tool("post_journal_entry")
    post_entry(
        debit_account="merchant_revenue",
        credit_account="customer_funds",
        amount_cents=5000,
        memo="Order #901 purchase",
        is_compensating=False,
    )

    verdict = StateOracle.evaluate(
        task=task_spec,
        sandbox=sandbox,
        proxy_registry=proxy_registry,
        method_name="skip_agent",
        boundary_name="NO_FAULT",
        perturbation_name="NONE",
        agent_succeeded=True,
    )

    assert verdict.overall_recovery_correct is False
    assert verdict.final_state_valid is False
    assert verdict.primary_failure_classification in (
        "MISSING_EFFECT",
        "EXTERNAL_STATE_DIVERGENCE",
        "TASK_FAILURE",
    )


def test_ref_agent_6_compensate_correctly():
    """Reference Agent 6: Executes clean compensating reversal, fulfilling the task's recovery specification."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-PAY-002")
    proxy_registry.injector = DeterministicFaultInjector(
        FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)
    )

    post_entry = proxy_registry.get_proxied_tool("post_journal_entry")

    # Step 1: initial charge
    post_entry(
        debit_account="merchant_revenue",
        credit_account="customer_funds",
        amount_cents=5000,
        memo="Order #901 purchase",
        is_compensating=False,
    )

    # Step 2: compensating reversal
    post_entry(
        debit_account="customer_funds",
        credit_account="merchant_revenue",
        amount_cents=5000,
        memo="Order #901 compensation reversal",
        is_compensating=True,
    )

    verdict = StateOracle.evaluate(
        task=task_spec,
        sandbox=sandbox,
        proxy_registry=proxy_registry,
        method_name="compensate_correctly",
        boundary_name="NO_FAULT",
        perturbation_name="NONE",
        agent_succeeded=True,
    )

    assert verdict.overall_recovery_correct is True
    assert verdict.final_state_valid is True
    assert verdict.primary_failure_classification == "SUCCESS"


def test_ref_agent_7_compensate_incorrectly():
    """Reference Agent 7: Attempts flawed or partial compensation leaving corrupted state."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-PAY-002")
    proxy_registry.injector = DeterministicFaultInjector(
        FaultSpec(
            boundary=ExecutionBoundary.DURING_COMPENSATION,
            perturbation=Perturbation.RECOVERY_CRASH,
            target_call_index=2,
        )
    )

    post_entry = proxy_registry.get_proxied_tool("post_journal_entry")

    # Step 1: initial charge of $50 (5000 cents)
    post_entry(
        debit_account="merchant_revenue",
        credit_account="customer_funds",
        amount_cents=5000,
        memo="Order #901 purchase",
        is_compensating=False,
    )

    # Flawed compensation: crashes or fails during execution
    compensation_failed = False
    try:
        post_entry(
            debit_account="customer_funds",
            credit_account="merchant_revenue",
            amount_cents=1000,
            memo="Partial flawed reversal",
            is_compensating=True,
        )
    except Exception:
        compensation_failed = True

    assert compensation_failed is True

    verdict = StateOracle.evaluate(
        task=task_spec,
        sandbox=sandbox,
        proxy_registry=proxy_registry,
        method_name="bad_compensator",
        boundary_name="DURING_COMPENSATION",
        perturbation_name="RECOVERY_CRASH",
        agent_succeeded=False,
    )

    assert verdict.overall_recovery_correct is False
    assert verdict.final_state_valid is False
    assert verdict.primary_failure_classification in (
        "FAILED_COMPENSATION",
        "EXTERNAL_STATE_DIVERGENCE",
    )


def test_ref_agent_8_conflict_blind():
    """Reference Agent 8: Ignores external concurrent modification / state divergence."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-DB-001")
    proxy_registry.injector = DeterministicFaultInjector(
        FaultSpec(
            boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK,
            perturbation=Perturbation.CONCURRENT_WRITE,
            target_call_index=1,
            concurrent_state_delta={"accounts.acc_alice.balance": 999.0},
        )
    )

    deduct = proxy_registry.get_proxied_tool("deduct_account_balance")
    credit = proxy_registry.get_proxied_tool("credit_account_balance")

    # Out-of-band concurrent change reduces Alice balance to 10
    sandbox.deduct_account_balance("acc_alice", 90.0)

    # Agent blindly deducts 30 anyway without checking balance precondition
    deduct(account_id="acc_alice", amount=30.0)
    credit(account_id="acc_bob", amount=30.0)

    verdict = StateOracle.evaluate(
        task=task_spec,
        sandbox=sandbox,
        proxy_registry=proxy_registry,
        method_name="conflict_blind",
        boundary_name="POST_MUTATION_PRE_ACK",
        perturbation_name="CONCURRENT_WRITE",
        agent_succeeded=True,
    )

    assert verdict.overall_recovery_correct is False
    assert verdict.primary_failure_classification in (
        "CONCURRENT_CONFLICT_LOSS",
        "EXTERNAL_STATE_DIVERGENCE",
        "TASK_FAILURE",
        "ORACLE_VIOLATION",
    )
