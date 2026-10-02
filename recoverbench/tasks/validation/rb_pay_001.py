"""RB-PAY-001: Customer Refund under Lost ACK."""

from recoverbench.domains.payments.payment_sandbox import PaymentGatewaySimulator
from recoverbench.faults.proxy import ToolProxyRegistry
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.schemas.task import (
    EffectOp,
    EffectReversibility,
    FaultScenarioSpec,
    ForbiddenEffect,
    OutcomeObservability,
    RequiredEffect,
    TaskComplexity,
    TaskDomain,
    TaskProvenance,
    TaskSpec,
    TaskSplit,
    TaskStepPlan,
)


def create_task_rb_pay_001() -> tuple[TaskSpec, PaymentGatewaySimulator, ToolProxyRegistry]:
    sandbox = PaymentGatewaySimulator()
    sandbox.seed_charge("ch_9001", "cust_alice", 10000)  # $100.00 charge

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="refund_charge",
        fn=sandbox.refund_charge,
        target="payments.charge.ch_9001.refund",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-PAY-001",
        name="Customer Refund under Lost ACK",
        domain=TaskDomain.PAYMENTS,
        split=TaskSplit.VALIDATION,
        objective="Issue a full $100.00 refund (10000 cents) on settled charge ch_9001.",
        initial_state_setup={"charge_id": "ch_9001", "amount_cents": 10000},
        allowed_tools=["refund_charge"],
        required_effects=[
            RequiredEffect(
                target="payments.charge.ch_9001.refund",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Issue exactly one $100.00 refund on ch_9001",
            )
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="payments.charge.ch_9001.refund",
                reason="Double refund issued on customer charge ch_9001 ($200 loss)",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "charges.ch_9001.amount_refunded_cents": 10000,
            "total_refunds_count": 1,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="refund_charge",
                args={"charge_id": "ch_9001", "amount_cents": 10000},
                description="Step 1: Refund charge ch_9001",
            )
        ],
        complexity=TaskComplexity.C1,
        provenance=TaskProvenance.REALISTIC_TEMPLATE,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Refund issued without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Refund",
                description="Refund succeeded on gateway but network dropped ACK",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Use idempotency key or verify gateway status before retrying",
            ),
        ],
        source="RecoverBench-Validation-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
