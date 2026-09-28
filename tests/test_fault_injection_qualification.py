"""Qualification tests proving exact fault injection timing across all 6 execution boundaries.

Demonstrates experimentally that:
1. PRE_MUTATION strictly aborts before the underlying domain function executes.
2. DURING_MUTATION strictly aborts during dispatch without committing external state.
3. POST_MUTATION_PRE_ACK executes the external mutation first, commits state, and drops ACK.
4. POST_ACK_PRE_CHECKPOINT commits state, sets acknowledged=True, and crashes before checkpoint.
5. DURING_COMPENSATION intercepts compensating reversal steps and injects RECOVERY_CRASH.
"""

from __future__ import annotations
import pytest
from recoverbench.faults.injector import (
    DeterministicFaultInjector,
    InjectedAckLoss,
    InjectedNetworkTimeout,
    InjectedRecoveryFailure,
    InjectedWorkerCrash,
)
from recoverbench.faults.proxy import ToolProxyRegistry
from recoverbench.schemas.fault import (
    ExecutionBoundary,
    FaultSpec,
    Perturbation,
)
from recoverbench.tasks.registry import TaskRegistry


def test_timing_pre_mutation_prevents_commit():
    """Prove PRE_MUTATION intercepts before the domain mutation runs."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-DB-001")
    fault = FaultSpec(
        boundary=ExecutionBoundary.PRE_MUTATION,
        perturbation=Perturbation.WORKER_CRASH,
        target_tool="deduct_account_balance",
        trigger_call_index=1,
    )
    proxy_registry.injector = DeterministicFaultInjector(fault_spec=fault)

    # Initial state
    assert sandbox.query_account_balance("acc_alice") == 100.0

    tool = proxy_registry.get_proxied_tool("deduct_account_balance")
    with pytest.raises(InjectedWorkerCrash) as exc_info:
        tool(account_id="acc_alice", amount=30.0)

    assert "boundary PRE_MUTATION" in str(exc_info.value)
    # State MUST NOT be modified
    assert sandbox.query_account_balance("acc_alice") == 100.0
    # Wire log MUST show committed_externally = False
    assert len(proxy_registry.effect_log) == 1
    event = proxy_registry.effect_log[0]
    assert event.committed_externally is False
    assert event.acknowledged_to_agent is False


def test_timing_during_mutation_prevents_commit():
    """Prove DURING_MUTATION intercepts before external commit."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-DB-002")
    fault = FaultSpec(
        boundary=ExecutionBoundary.DURING_MUTATION,
        perturbation=Perturbation.NETWORK_TIMEOUT,
        target_tool="upgrade_customer_tier",
        trigger_call_index=1,
    )
    proxy_registry.injector = DeterministicFaultInjector(fault_spec=fault)

    assert sandbox.query_customer_tier("cust_101") == "FREE"

    tool = proxy_registry.get_proxied_tool("upgrade_customer_tier")
    with pytest.raises(InjectedNetworkTimeout) as exc_info:
        tool(customer_id="cust_101", new_tier="PRO")

    assert "boundary DURING_MUTATION" in str(exc_info.value)
    # State MUST NOT be modified
    assert sandbox.query_customer_tier("cust_101") == "FREE"
    # Wire log verification
    assert len(proxy_registry.effect_log) == 1
    event = proxy_registry.effect_log[0]
    assert event.committed_externally is False
    assert event.acknowledged_to_agent is False


def test_timing_post_mutation_pre_ack_commits_before_fault():
    """Prove POST_MUTATION_PRE_ACK executes external mutation before dropping ACK."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-DB-001")
    fault = FaultSpec(
        boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK,
        perturbation=Perturbation.ACK_LOSS,
        target_tool="deduct_account_balance",
        trigger_call_index=1,
    )
    proxy_registry.injector = DeterministicFaultInjector(fault_spec=fault)

    assert sandbox.query_account_balance("acc_alice") == 100.0

    tool = proxy_registry.get_proxied_tool("deduct_account_balance")
    with pytest.raises(InjectedAckLoss) as exc_info:
        tool(account_id="acc_alice", amount=30.0)

    assert "boundary POST_MUTATION_PRE_ACK" in str(exc_info.value)
    # External state WAS committed on physical SQLite database!
    assert sandbox.query_account_balance("acc_alice") == 70.0
    # Wire log MUST show committed_externally = True, acknowledged = False
    assert len(proxy_registry.effect_log) == 1
    event = proxy_registry.effect_log[0]
    assert event.committed_externally is True
    assert event.acknowledged_to_agent is False


def test_timing_post_mutation_pre_ack_worker_crash():
    """Prove POST_MUTATION_PRE_ACK with WORKER_CRASH commits state on payments."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-PAY-001")
    fault = FaultSpec(
        boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK,
        perturbation=Perturbation.WORKER_CRASH,
        target_tool="refund_charge",
        trigger_call_index=1,
    )
    proxy_registry.injector = DeterministicFaultInjector(fault_spec=fault)

    assert sandbox.query_charge_refunded_amount("ch_9001") == 0

    tool = proxy_registry.get_proxied_tool("refund_charge")
    with pytest.raises(InjectedWorkerCrash) as exc_info:
        tool(charge_id="ch_9001", amount_cents=10000)

    assert "boundary POST_MUTATION_PRE_ACK" in str(exc_info.value)
    # External charge WAS refunded on sandbox
    assert sandbox.query_charge_refunded_amount("ch_9001") == 10000
    assert len(proxy_registry.effect_log) == 1
    event = proxy_registry.effect_log[0]
    assert event.committed_externally is True
    assert event.acknowledged_to_agent is False


def test_timing_post_ack_pre_checkpoint():
    """Prove POST_ACK_PRE_CHECKPOINT acknowledges mutation before crash."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-CLOUD-001")
    fault = FaultSpec(
        boundary=ExecutionBoundary.POST_ACK_PRE_CHECKPOINT,
        perturbation=Perturbation.WORKER_CRASH,
        target_tool="scale_service",
        trigger_call_index=1,
    )
    proxy_registry.injector = DeterministicFaultInjector(fault_spec=fault)

    assert sandbox.query_running_replicas("checkout-service") == 3

    tool = proxy_registry.get_proxied_tool("scale_service")
    with pytest.raises(InjectedWorkerCrash) as exc_info:
        tool(service_name="checkout-service", new_replicas=6)

    assert "boundary POST_ACK_PRE_CHECKPOINT" in str(exc_info.value)
    # External state was committed
    assert sandbox.query_running_replicas("checkout-service") == 6
    # Wire log shows committed=True and acknowledged=True
    assert len(proxy_registry.effect_log) == 1
    event = proxy_registry.effect_log[0]
    assert event.committed_externally is True
    assert event.acknowledged_to_agent is True


def test_timing_during_compensation():
    """Prove DURING_COMPENSATION intercepts compensating transactions."""
    task_spec, sandbox, proxy_registry = TaskRegistry.load_task("RB-PAY-002")
    fault = FaultSpec(
        boundary=ExecutionBoundary.DURING_COMPENSATION,
        perturbation=Perturbation.RECOVERY_CRASH,
        target_tool="post_journal_entry",
        target_call_index=2, # Trigger on Step 2 (the compensating reversal)
    )
    proxy_registry.injector = DeterministicFaultInjector(fault_spec=fault)

    tool = proxy_registry.get_proxied_tool("post_journal_entry")
    # Step 1: forward charge succeeds cleanly
    step1_res = tool(
        debit_account="merchant_revenue",
        credit_account="customer_funds",
        amount_cents=5000,
        memo="Order #901 purchase",
        is_compensating=False,
    )
    assert "entry_id" in step1_res
    assert len(sandbox.journal) == 1

    # Step 2: compensating transaction triggered and intercepted
    with pytest.raises(InjectedRecoveryFailure) as exc_info:
        tool(
            debit_account="customer_funds",
            credit_account="merchant_revenue",
            amount_cents=5000,
            memo="Order #901 compensation reversal",
            is_compensating=True,
        )

    assert "boundary DURING_COMPENSATION" in str(exc_info.value)
    # Journal still only has 1 entry because compensation crashed before commit
    assert len(sandbox.journal) == 1
    assert len(proxy_registry.effect_log) == 2
    assert proxy_registry.effect_log[0].committed_externally is True
    assert proxy_registry.effect_log[1].committed_externally is False
