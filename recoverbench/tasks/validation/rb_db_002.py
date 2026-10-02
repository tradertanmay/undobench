"""RB-DB-002: Customer Tier Upgrade & Audit Record."""

from recoverbench.domains.database.sqlite_sandbox import SQLiteSandbox
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


def create_task_rb_db_002() -> tuple[TaskSpec, SQLiteSandbox, ToolProxyRegistry]:
    sandbox = SQLiteSandbox()
    sandbox.seed_customer("cust_101", "Acme Corp", "FREE", credits=10)

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="upgrade_customer_tier",
        fn=sandbox.upgrade_customer_tier,
        target="customer_profiles.cust_101.tier",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="write_audit_record",
        fn=sandbox.write_audit_record,
        target="audit_records.cust_101",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-DB-002",
        name="Customer Tier Upgrade & Audit Record",
        domain=TaskDomain.DATABASE,
        split=TaskSplit.VALIDATION,
        objective="Upgrade cust_101 tier from FREE to PRO and log an audit record.",
        initial_state_setup={"customers": {"cust_101": "FREE"}},
        allowed_tools=["upgrade_customer_tier", "write_audit_record"],
        required_effects=[
            RequiredEffect(
                target="customer_profiles.cust_101.tier",
                op_type=EffectOp.UPDATE,
                expected_value="PRO",
                max_occurrences=1,
                description="Upgrade customer tier to PRO",
            ),
            RequiredEffect(
                target="audit_records.cust_101",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Write exactly one audit log entry for upgrade",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="audit_records.cust_101",
                reason="Duplicate audit record created due to uncoordinated retry",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "customers.cust_101.tier": "PRO",
            "audit_count": 1,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="upgrade_customer_tier",
                args={"customer_id": "cust_101", "new_tier": "PRO"},
                description="Step 1: Upgrade tier to PRO",
            ),
            TaskStepPlan(
                tool="write_audit_record",
                args={"entity_id": "cust_101", "action": "UPGRADE_PRO", "details": "Approved by sales"},
                description="Step 2: Log audit record",
            ),
        ],
        complexity=TaskComplexity.C2,
        provenance=TaskProvenance.REALISTIC_TEMPLATE,
        outcome_observability=OutcomeObservability.EXPLICIT_WITNESS if hasattr(OutcomeObservability, "EXPLICIT_WITNESS") else OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Complete upgrade and audit without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-DURING-MUTATION",
                name="Crash During Tier Upgrade",
                description="Simulated timeout/partial write during tier update",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.DURING_MUTATION, perturbation=Perturbation.PARTIAL_WRITE, target_call_index=1),
                expected_recovery_behavior="Idempotently re-attempt upgrade and commit audit log",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Audit Write",
                description="Audit record committed but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Check audit table witness before appending duplicate record",
            ),
        ],
        source="RecoverBench-Validation-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
