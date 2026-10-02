"""RB-MSG-004: High-Urgency Pager Callout with Delivery ACK (Frozen TEST Set)."""

from recoverbench.domains.messaging.messaging_sandbox import MessagingNotificationSandbox
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


def create_task_rb_msg_004() -> tuple[TaskSpec, MessagingNotificationSandbox, ToolProxyRegistry]:
    sandbox = MessagingNotificationSandbox()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="page_oncall_engineer",
        fn=sandbox.page_oncall_engineer,
        target="messaging.pager.dispatch.payments-core",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-MSG-004",
        name="High-Urgency Pager Callout with Delivery ACK",
        domain=TaskDomain.MESSAGING,
        split=TaskSplit.TEST,
        objective="Dispatch high-urgency P1 pager alert to on-call team for service 'payments-core'.",
        initial_state_setup={},
        allowed_tools=["page_oncall_engineer"],
        required_effects=[
            RequiredEffect(
                target="messaging.pager.dispatch.payments-core",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Dispatch exactly one P1 on-call page",
            )
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="messaging.pager.dispatch.payments-core",
                reason="Spamming duplicate on-call engineer phone pages",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "total_pages": 1,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="page_oncall_engineer",
                args={"service": "payments-core", "alert_title": "Database Master Unresponsive", "severity": "P1"},
                description="Step 1: Page on-call engineer",
            )
        ],
        complexity=TaskComplexity.C1,
        provenance=TaskProvenance.NEW_FOR_RECOVERBENCH,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.IRREVERSIBLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Dispatch pager alert cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Pager Callout",
                description="Pager dispatched to phone provider but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Check paging audit logs before re-triggering loud phone alerts",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
