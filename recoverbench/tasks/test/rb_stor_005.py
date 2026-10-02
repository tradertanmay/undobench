"""RB-STOR-005: Atomic Object Swap with Rollback (Frozen TEST Set)."""

from recoverbench.domains.storage.storage_sandbox import ObjectStorageSandbox
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


def create_task_rb_stor_005() -> tuple[TaskSpec, ObjectStorageSandbox, ToolProxyRegistry]:
    sandbox = ObjectStorageSandbox()
    sandbox.seed_bucket("configs-bucket")
    sandbox.seed_object("configs-bucket", "active_flags.json", '{"feature_x": false}')

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="put_object",
        fn=sandbox.put_object,
        target="storage.configs-bucket.active_flags.json",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="delete_object",
        fn=sandbox.delete_object,
        target="storage.configs-bucket.active_flags.json.bak",
        op_type=EffectOp.DELETE,
    )

    # Seed temporary backup flag object
    sandbox.seed_object("configs-bucket", "active_flags.json.bak", '{"feature_x": false}')

    spec = TaskSpec(
        task_id="RB-STOR-005",
        name="Atomic Object Swap with Cleanup",
        domain=TaskDomain.STORAGE,
        split=TaskSplit.TEST,
        version="1.0.1",
        objective="Update active_flags.json to enable feature_x and delete staging backup active_flags.json.bak.",
        initial_state_setup={"bucket": "configs-bucket"},
        allowed_tools=["put_object", "delete_object"],
        required_effects=[
            RequiredEffect(
                target="storage.configs-bucket.active_flags.json",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Update feature flag object to true",
            ),
            RequiredEffect(
                target="storage.configs-bucket.active_flags.json.bak",
                op_type=EffectOp.DELETE,
                max_occurrences=1,
                description="Delete temporary backup object",
            ),
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "storage.configs-bucket.active_flags.json.size_bytes": 19,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="put_object",
                args={"bucket_name": "configs-bucket", "key": "active_flags.json", "content": '{"feature_x": true}'},
                description="Step 1: Put updated flags object",
            ),
            TaskStepPlan(
                tool="delete_object",
                args={"bucket_name": "configs-bucket", "key": "active_flags.json.bak"},
                description="Step 2: Delete backup object",
            ),
        ],
        complexity=TaskComplexity.C3,
        provenance=TaskProvenance.NEW_FOR_RECOVERBENCH,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Update flags and delete backup cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Backup Cleanup",
                description="Backup object deleted but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Verify backup deletion before re-invoking delete operation",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
