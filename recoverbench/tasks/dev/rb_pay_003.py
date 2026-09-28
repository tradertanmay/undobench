"""RB-PAY-003: Split Payment Disbursement under Lost ACK."""

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


def create_task_rb_pay_003() -> tuple[TaskSpec, PaymentGatewaySimulator, ToolProxyRegistry]:
    sandbox = PaymentGatewaySimulator()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="disburse_split_payout",
        fn=sandbox.disburse_split_payout,
        target="payments.payout.split_101",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-PAY-003",
        name="Split Payment Disbursement across Sub-merchants",
        domain=TaskDomain.PAYMENTS,
        split=TaskSplit.DEV,
        objective="Disburse split payment of $250.00 (25000 cents) to merchant m_701 and $150.00 (15000 cents) to merchant m_702.",
        initial_state_setup={"payout_id": "po_split_101"},
        allowed_tools=["disburse_split_payout"],
        required_effects=[
            RequiredEffect(
                target="payments.payout.split_101",
                op_type=EffectOp.CREATE,
                max_occurrences=2,
                description="Disburse exactly 2 payouts for sub-merchants",
            )
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="payments.payout.split_101",
                reason="Double payout executed to merchant account",
            )
        ],
        invariants=[],
        acceptable_final_states={},
        scripted_plan=[
            TaskStepPlan(
                tool="disburse_split_payout",
                args={"payout_id": "po_split_101_a", "merchant_id": "m_701", "amount_cents": 25000},
                description="Step 1: Payout to m_701",
            ),
            TaskStepPlan(
                tool="disburse_split_payout",
                args={"payout_id": "po_split_101_b", "merchant_id": "m_702", "amount_cents": 15000},
                description="Step 2: Payout to m_702",
            ),
        ],
        complexity=TaskComplexity.C2,
        provenance=TaskProvenance.REALISTIC_TEMPLATE,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Disburse both splits cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Split Transfer",
                description="Split transfer committed on gateway but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Attach idempotency key or verify payout record before retrying",
            ),
        ],
        source="RecoverBench-Dev-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
