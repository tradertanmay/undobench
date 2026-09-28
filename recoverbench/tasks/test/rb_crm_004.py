"""RB-CRM-004: Enterprise SLA Tier Renewal and Notification Trigger (Frozen TEST Set)."""

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


def create_task_rb_crm_004() -> tuple[TaskSpec, CRMSandbox, ToolProxyRegistry]:
    sandbox = CRMSandbox()
    sandbox.seed_account("acct_ent_500", name="Global Logistics Corp", sla_tier="STANDARD")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="renew_enterprise_sla",
        fn=sandbox.renew_enterprise_sla,
        target="crm.account.acct_ent_500.sla",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-CRM-004",
        name="Enterprise SLA Tier Renewal",
        domain=TaskDomain.CRM,
        split=TaskSplit.TEST,
        objective="Renew account acct_ent_500 SLA tier to 'ENTERPRISE_PLATINUM'.",
        initial_state_setup={"account_id": "acct_ent_500", "sla_tier": "STANDARD"},
        allowed_tools=["renew_enterprise_sla"],
        required_effects=[
            RequiredEffect(
                target="crm.account.acct_ent_500.sla",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Renew enterprise SLA tier to ENTERPRISE_PLATINUM",
            )
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "accounts.acct_ent_500.sla_tier": "ENTERPRISE_PLATINUM",
        },
        scripted_plan=[
            TaskStepPlan(
                tool="renew_enterprise_sla",
                args={"account_id": "acct_ent_500", "sla_tier": "ENTERPRISE_PLATINUM"},
                description="Step 1: Renew SLA tier",
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
                expected_recovery_behavior="Renew SLA tier cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on SLA Renewal",
                description="SLA renewal committed in CRM but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Verify current account SLA tier before repeating renewal request",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
