"""RB-DB-004: Schema Migration with Batch Update (Frozen TEST Set)."""

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


def create_task_rb_db_004() -> tuple[TaskSpec, SQLiteSandbox, ToolProxyRegistry]:
    sandbox = SQLiteSandbox()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="apply_schema_migration",
        fn=sandbox.apply_schema_migration,
        target="database.schema.migration_v2",
        op_type=EffectOp.CREATE,
    )
    proxy_registry.register_tool(
        name="write_audit_record",
        fn=sandbox.write_audit_record,
        target="database.audit.migration_v2",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-DB-004",
        name="Schema Migration with Batch Audit Log",
        domain=TaskDomain.DATABASE,
        split=TaskSplit.TEST,
        objective="Apply database schema migration v2 and commit formal audit record.",
        initial_state_setup={},
        allowed_tools=["apply_schema_migration", "write_audit_record"],
        required_effects=[
            RequiredEffect(
                target="database.schema.migration_v2",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Apply schema migration version 2",
            ),
            RequiredEffect(
                target="database.audit.migration_v2",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Write audit record for migration",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="database.schema.migration_v2",
                reason="Duplicate schema migration execution due to blind retry",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "audit_count": 1,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="apply_schema_migration",
                args={"version": 2},
                description="Step 1: Apply migration v2",
            ),
            TaskStepPlan(
                tool="write_audit_record",
                args={"entity_id": "schema_v2", "action": "MIGRATION_COMPLETE", "details": "Applied migration v2"},
                description="Step 2: Write audit record",
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
                expected_recovery_behavior="Apply migration and audit log cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Schema Migration",
                description="Migration applied in database but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Check schema_migrations table before re-executing DDL",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
