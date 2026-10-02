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


def create_task_rb_tick_001() -> tuple[TaskSpec, IncidentDeskSandbox, ToolProxyRegistry]:
    sandbox = IncidentDeskSandbox()
    sandbox.seed_incident(
        incident_id="INC-404",
        title="Production Checkout Latency Spike",
        severity="LOW",
        status="OPEN",
        assignee=None,
    )

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="dispatch_oncall_page",
        fn=sandbox.dispatch_oncall_page,
        target="ticketing.paging.dispatch",
        op_type=EffectOp.EXECUTE,
    )
    proxy_registry.register_tool(
        name="update_incident_status",
        fn=sandbox.update_incident_status,
        target="ticketing.incident.INC-404.status",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-TICK-001",
        name="Urgent Incident Escalation & On-Call Page",
        domain=TaskDomain.TICKETING,
        split=TaskSplit.VALIDATION,
        objective="Dispatch high-urgency on-call page to alice_sre for incident INC-404 and escalate status to PAGED.",
        initial_state_setup={"incident_id": "INC-404", "status": "OPEN", "severity": "LOW"},
        allowed_tools=["dispatch_oncall_page", "update_incident_status"],
        required_effects=[
            RequiredEffect(
                target="ticketing.paging.dispatch",
                op_type=EffectOp.EXECUTE,
                max_occurrences=1,
                description="Dispatch exactly one phone/pager alert to on-call engineer",
            ),
            RequiredEffect(
                target="ticketing.incident.INC-404.status",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Update incident status to PAGED and severity to SEV1",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="ticketing.paging.dispatch",
                reason="Duplicate paging alert dispatched to on-call engineer",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "incidents.INC-404.status": "PAGED",
            "incidents.INC-404.severity": "SEV1",
            "total_pages": 1,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="dispatch_oncall_page",
                args={"incident_id": "INC-404", "oncall_engineer": "alice_sre", "urgency": "HIGH"},
                description="Step 1: Page on-call engineer",
            ),
            TaskStepPlan(
                tool="update_incident_status",
                args={"incident_id": "INC-404", "new_severity": "SEV1", "new_status": "PAGED", "assignee": "alice_sre"},
                description="Step 2: Update incident ticket",
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
                expected_recovery_behavior="Page dispatched and ticket updated without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Paging Dispatch",
                description="Page sent to engineer phone but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Check paging audit log before re-paging engineer",
            ),
        ],
        source="RecoverBench-Validation-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
