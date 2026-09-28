"""RB-CRM-003: Customer Account Merging with Audit Trail under Lost ACK."""

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


def create_task_rb_crm_003() -> tuple[TaskSpec, CRMSandbox, ToolProxyRegistry]:
    sandbox = CRMSandbox()
    sandbox.seed_account("acct_prime_10", name="Apex Global Corp")
    sandbox.seed_account("acct_dupe_11", name="Apex Global Inc (Duplicate)")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="merge_customer_accounts",
        fn=sandbox.merge_customer_accounts,
        target="crm.account.merge.acct_dupe_11",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-CRM-003",
        name="Customer Account Merging with Audit Trail",
        domain=TaskDomain.CRM,
        split=TaskSplit.DEV,
        objective="Merge duplicate customer account acct_dupe_11 into primary account acct_prime_10.",
        initial_state_setup={"primary": "acct_prime_10", "duplicate": "acct_dupe_11"},
        allowed_tools=["merge_customer_accounts"],
        required_effects=[
            RequiredEffect(
                target="crm.account.merge.acct_dupe_11",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Mark duplicate account as MERGED into acct_prime_10",
            )
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "accounts.acct_dupe_11.status": "MERGED",
            "accounts.acct_dupe_11.merged_into": "acct_prime_10",
        },
        scripted_plan=[
            TaskStepPlan(
                tool="merge_customer_accounts",
                args={"primary_id": "acct_prime_10", "secondary_id": "acct_dupe_11"},
                description="Step 1: Merge accounts",
            )
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
                expected_recovery_behavior="Merge accounts cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Account Merge",
                description="Merge transaction committed in CRM but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Inspect account merge status before re-invoking merge",
            ),
        ],
        source="RecoverBench-Dev-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
