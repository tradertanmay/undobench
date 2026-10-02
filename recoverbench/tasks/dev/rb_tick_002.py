"""RB-TICK-002: P1 Incident Severity Upgrade and Team Assignment under Lost ACK."""

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


def create_task_rb_tick_002() -> tuple[TaskSpec, IncidentDeskSandbox, ToolProxyRegistry]:
    sandbox = IncidentDeskSandbox()
    sandbox.seed_incident(
        incident_id="INC-802",
        title="Payment Gateway Connectivity Outage",
        severity="SEV3",
        status="INVESTIGATING",
    )

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="update_incident_status",
        fn=sandbox.update_incident_status,
        target="ticketing.incident.INC-802.severity",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="assign_incident_team",
        fn=sandbox.assign_incident_team,
        target="ticketing.incident.INC-802.team",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-TICK-002",
        name="P1 Incident Severity Upgrade and Team Assignment",
        domain=TaskDomain.TICKETING,
        split=TaskSplit.DEV,
        objective="Escalate incident INC-802 to SEV1 and assign ownership to team 'payments-sre'.",
        initial_state_setup={"incident_id": "INC-802", "severity": "SEV3"},
        allowed_tools=["update_incident_status", "assign_incident_team"],
        required_effects=[
            RequiredEffect(
                target="ticketing.incident.INC-802.severity",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Update incident severity to SEV1",
            ),
            RequiredEffect(
                target="ticketing.incident.INC-802.team",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Assign ticket to team payments-sre",
            ),
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "incidents.INC-802.severity": "SEV1",
            "incidents.INC-802.assigned_team": "payments-sre",
        },
        scripted_plan=[
            TaskStepPlan(
                tool="update_incident_status",
                args={"incident_id": "INC-802", "new_severity": "SEV1"},
                description="Step 1: Escalate severity to SEV1",
            ),
            TaskStepPlan(
                tool="assign_incident_team",
                args={"incident_id": "INC-802", "team_name": "payments-sre"},
                description="Step 2: Assign team payments-sre",
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
                expected_recovery_behavior="Escalate severity and assign team without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Severity Update",
                description="Severity updated on incident desk but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Verify current severity before repeating update call",
            ),
        ],
        source="RecoverBench-Dev-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
