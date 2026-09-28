"""RB-CRM-002: Opportunity Pipeline Stage Progression & Quota Update under Lost ACK."""

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


def create_task_rb_crm_002() -> tuple[TaskSpec, CRMSandbox, ToolProxyRegistry]:
    sandbox = CRMSandbox()
    sandbox.seed_opportunity("opp_201", stage="PROPOSAL", deal_value=50000.0, rep_id="rep_sarah")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="advance_opportunity_stage",
        fn=sandbox.advance_opportunity_stage,
        target="crm.opportunity.opp_201.stage",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="update_rep_quota",
        fn=sandbox.update_rep_quota,
        target="crm.quota.rep_sarah",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-CRM-002",
        name="Opportunity Pipeline Stage Progression & Quota Update",
        domain=TaskDomain.CRM,
        split=TaskSplit.DEV,
        objective="Advance opportunity opp_201 to 'CLOSED_WON' ($50,000) and credit sales rep rep_sarah's quota attainment.",
        initial_state_setup={"opp_id": "opp_201", "stage": "PROPOSAL", "deal_value": 50000.0},
        allowed_tools=["advance_opportunity_stage", "update_rep_quota"],
        required_effects=[
            RequiredEffect(
                target="crm.opportunity.opp_201.stage",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Advance opportunity stage to CLOSED_WON",
            ),
            RequiredEffect(
                target="crm.quota.rep_sarah",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Credit $50,000 to rep quota attainment",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="crm.quota.rep_sarah",
                reason="Double credit applied to rep quota due to blind retry",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "opportunities.opp_201.stage": "CLOSED_WON",
            "rep_quotas.rep_sarah": 50000.0,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="advance_opportunity_stage",
                args={"opp_id": "opp_201", "stage": "CLOSED_WON", "deal_value": 50000.0},
                description="Step 1: Advance opportunity to CLOSED_WON",
            ),
            TaskStepPlan(
                tool="update_rep_quota",
                args={"rep_id": "rep_sarah", "amount": 50000.0},
                description="Step 2: Credit rep quota",
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
                expected_recovery_behavior="Advance stage and update quota cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Quota Credit",
                description="Quota credit committed in CRM but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Inspect rep quota balance before issuing duplicate credit",
            ),
        ],
        source="RecoverBench-Dev-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
