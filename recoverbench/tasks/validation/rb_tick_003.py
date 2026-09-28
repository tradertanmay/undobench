"""RB-TICK-003: Multi-Party Incident Resolution and Customer Notification."""

from recoverbench.domains.ticketing.ticketing_sandbox import IncidentDeskSandbox
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


def create_task_rb_tick_003() -> tuple[TaskSpec, IncidentDeskSandbox, ToolProxyRegistry]:
    sandbox = IncidentDeskSandbox()
    sandbox.seed_incident(
        incident_id="INC-991",
        title="Database Deadlock during Flash Sale",
        severity="SEV1",
        status="INVESTIGATING",
    )

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="resolve_incident",
        fn=sandbox.resolve_incident,
        target="ticketing.incident.INC-991.resolution",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="dispatch_resolution_notice",
        fn=sandbox.dispatch_resolution_notice,
        target="ticketing.notice.INC-991",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-TICK-003",
        name="Multi-Party Incident Resolution and Customer Notification",
        domain=TaskDomain.TICKETING,
        split=TaskSplit.VALIDATION,
        objective="Resolve incident INC-991 with resolution notes and dispatch notification notice to customer leadership.",
        initial_state_setup={"incident_id": "INC-991", "status": "INVESTIGATING"},
        allowed_tools=["resolve_incident", "dispatch_resolution_notice"],
        required_effects=[
            RequiredEffect(
                target="ticketing.incident.INC-991.resolution",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Mark incident as RESOLVED",
            ),
            RequiredEffect(
                target="ticketing.notice.INC-991",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Dispatch resolution notice email to customer",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="ticketing.notice.INC-991",
                reason="Duplicate customer resolution notice dispatched due to blind retry",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "incidents.INC-991.status": "RESOLVED",
            "total_pages": 1,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="resolve_incident",
                args={"incident_id": "INC-991", "resolution_note": "Deadlock root cause mitigated via index reorg"},
                description="Step 1: Resolve incident ticket",
            ),
            TaskStepPlan(
                tool="dispatch_resolution_notice",
                args={"incident_id": "INC-991", "customer_email": "ops-lead@customer.com"},
                description="Step 2: Dispatch resolution notice",
            ),
        ],
        complexity=TaskComplexity.C2,
        provenance=TaskProvenance.REALISTIC_TEMPLATE,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.IRREVERSIBLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Resolve incident and dispatch notice cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Customer Notice",
                description="Notice email dispatched but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Verify dispatch history before sending duplicate customer resolution notice",
            ),
        ],
        source="RecoverBench-Validation-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
