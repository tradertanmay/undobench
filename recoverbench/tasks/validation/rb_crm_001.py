from recoverbench.domains.crm.crm_sandbox import CRMSandbox
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


def create_task_rb_crm_001() -> tuple[TaskSpec, CRMSandbox, ToolProxyRegistry]:
    sandbox = CRMSandbox()
    sandbox.seed_lead("lead_505", name="David Warner", email="david@enterprise.io", status="NEW")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="convert_lead_status",
        fn=sandbox.convert_lead_status,
        target="crm.lead.lead_505.status",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="queue_welcome_sequence",
        fn=sandbox.queue_welcome_sequence,
        target="crm.outbound.welcome_queue.lead_505",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-CRM-001",
        name="Lead Conversion & Welcome Queue",
        domain=TaskDomain.CRM,
        split=TaskSplit.VALIDATION,
        objective="Convert lead lead_505 to ACTIVE_CUSTOMER and queue welcome onboarding sequence.",
        initial_state_setup={"lead_id": "lead_505", "status": "NEW"},
        allowed_tools=["convert_lead_status", "queue_welcome_sequence"],
        required_effects=[
            RequiredEffect(
                target="crm.lead.lead_505.status",
                op_type=EffectOp.UPDATE,
                expected_value="ACTIVE_CUSTOMER",
                max_occurrences=1,
                description="Update lead status to ACTIVE_CUSTOMER",
            ),
            RequiredEffect(
                target="crm.outbound.welcome_queue.lead_505",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Queue onboarding welcome event exactly once",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="crm.outbound.welcome_queue.lead_505",
                reason="Duplicate welcome email / sequence queued for converted lead",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "leads.lead_505.status": "ACTIVE_CUSTOMER",
            "queued_events_count": 1,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="convert_lead_status",
                args={"lead_id": "lead_505", "new_status": "ACTIVE_CUSTOMER"},
                description="Step 1: Convert status to ACTIVE_CUSTOMER",
            ),
            TaskStepPlan(
                tool="queue_welcome_sequence",
                args={"lead_id": "lead_505"},
                description="Step 2: Queue welcome sequence",
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
                expected_recovery_behavior="Convert lead and queue welcome sequence without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Outbound Queue",
                description="Outbound welcome email event queued but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Check outbound queue state before enqueuing duplicate welcome message",
            ),
        ],
        source="RecoverBench-Validation-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
