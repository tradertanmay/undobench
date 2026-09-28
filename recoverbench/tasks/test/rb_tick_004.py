"""RB-TICK-004: SLA Breach Re-routing & Executive Escalation (Frozen TEST Set)."""

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


def create_task_rb_tick_004() -> tuple[TaskSpec, IncidentDeskSandbox, ToolProxyRegistry]:
    sandbox = IncidentDeskSandbox()
    sandbox.seed_incident(
        incident_id="INC-3301",
        title="Enterprise Single-Sign-On Auth Degradation",
        severity="SEV2",
        status="OPEN",
    )

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="escalate_incident_sla",
        fn=sandbox.escalate_incident_sla,
        target="ticketing.incident.INC-3301.sla",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="assign_incident_team",
        fn=sandbox.assign_incident_team,
        target="ticketing.incident.INC-3301.team",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-TICK-004",
        name="SLA Breach Re-routing and Executive Escalation",
        domain=TaskDomain.TICKETING,
        split=TaskSplit.TEST,
        objective="Escalate incident INC-3301 to SLA tier 'CRITICAL_15MIN' and re-route ticket to 'iam-escalations'.",
        initial_state_setup={"incident_id": "INC-3301", "severity": "SEV2"},
        allowed_tools=["escalate_incident_sla", "assign_incident_team"],
        required_effects=[
            RequiredEffect(
                target="ticketing.incident.INC-3301.sla",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Escalate incident SLA tier to CRITICAL_15MIN",
            ),
            RequiredEffect(
                target="ticketing.incident.INC-3301.team",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Re-route ticket to team iam-escalations",
            ),
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "incidents.INC-3301.sla_tier": "CRITICAL_15MIN",
            "incidents.INC-3301.assigned_team": "iam-escalations",
        },
        scripted_plan=[
            TaskStepPlan(
                tool="escalate_incident_sla",
                args={"incident_id": "INC-3301", "tier": "CRITICAL_15MIN"},
                description="Step 1: Escalate SLA tier",
            ),
            TaskStepPlan(
                tool="assign_incident_team",
                args={"incident_id": "INC-3301", "team_name": "iam-escalations"},
                description="Step 2: Assign team iam-escalations",
            ),
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
                expected_recovery_behavior="Escalate SLA and re-route ticket cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on SLA Escalation",
                description="SLA escalated on incident desk but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Inspect incident SLA status before repeating escalation command",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
