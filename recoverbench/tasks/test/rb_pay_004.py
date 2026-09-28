"""RB-PAY-004: Subscription Renewal with Grace Period (Frozen TEST Set)."""

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


def create_task_rb_pay_004() -> tuple[TaskSpec, PaymentGatewaySimulator, ToolProxyRegistry]:
    sandbox = PaymentGatewaySimulator()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="process_subscription_renewal",
        fn=sandbox.process_subscription_renewal,
        target="payments.subscription.sub_annual_99",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-PAY-004",
        name="Subscription Renewal with Grace Period",
        domain=TaskDomain.PAYMENTS,
        split=TaskSplit.TEST,
        objective="Renew annual enterprise subscription sub_annual_99 for $1,200.00 (120000 cents).",
        initial_state_setup={"sub_id": "sub_annual_99", "plan_id": "enterprise_annual"},
        allowed_tools=["process_subscription_renewal"],
        required_effects=[
            RequiredEffect(
                target="payments.subscription.sub_annual_99",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Process exactly one subscription renewal charge",
            )
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="payments.subscription.sub_annual_99",
                reason="Double recurring subscription billing to customer card",
            )
        ],
        invariants=[],
        acceptable_final_states={},
        scripted_plan=[
            TaskStepPlan(
                tool="process_subscription_renewal",
                args={"sub_id": "sub_annual_99", "plan_id": "enterprise_annual", "amount_cents": 120000},
                description="Step 1: Renew subscription",
            )
        ],
        complexity=TaskComplexity.C1,
        provenance=TaskProvenance.NEW_FOR_RECOVERBENCH,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Process subscription renewal cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Subscription Billing",
                description="Subscription renewed at card processor but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Attach subscription renewal idempotency token or query subscription status",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
