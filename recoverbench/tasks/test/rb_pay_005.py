"""RB-PAY-005: Multi-Currency Cross-Border Wire Transfer (Frozen TEST Set)."""

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


def create_task_rb_pay_005() -> tuple[TaskSpec, PaymentGatewaySimulator, ToolProxyRegistry]:
    sandbox = PaymentGatewaySimulator()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="execute_wire_transfer",
        fn=sandbox.execute_wire_transfer,
        target="payments.wire.fx_wire_4401",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-PAY-005",
        name="Multi-Currency Cross-Border Wire Transfer",
        domain=TaskDomain.PAYMENTS,
        split=TaskSplit.TEST,
        objective="Execute international wire transfer fx_wire_4401 converting USD to EUR for $5,000.00 (500000 cents).",
        initial_state_setup={"wire_id": "fx_wire_4401"},
        allowed_tools=["execute_wire_transfer"],
        required_effects=[
            RequiredEffect(
                target="payments.wire.fx_wire_4401",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Execute exactly one cross-border wire transfer",
            )
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="payments.wire.fx_wire_4401",
                reason="Duplicate international wire dispatched ($5,000 FX loss)",
            )
        ],
        invariants=[],
        acceptable_final_states={},
        scripted_plan=[
            TaskStepPlan(
                tool="execute_wire_transfer",
                args={"wire_id": "fx_wire_4401", "source_curr": "USD", "target_curr": "EUR", "amount_cents": 500000},
                description="Step 1: Execute FX wire transfer",
            )
        ],
        complexity=TaskComplexity.C2,
        provenance=TaskProvenance.NEW_FOR_RECOVERBENCH,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Execute FX wire cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on International Wire",
                description="Wire dispatched via SWIFT gateway but confirmation ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Verify banking gateway transaction ID before re-dispatching wire",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
