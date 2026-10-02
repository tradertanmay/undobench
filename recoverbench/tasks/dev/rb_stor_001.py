"""RB-STOR-001: Object Upload with ETag Precondition Checking under Lost ACK."""

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


def create_task_rb_stor_001() -> tuple[TaskSpec, ObjectStorageSandbox, ToolProxyRegistry]:
    sandbox = ObjectStorageSandbox()
    sandbox.seed_bucket("production-assets")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="put_object",
        fn=sandbox.put_object,
        target="storage.production-assets.manifest.json",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-STOR-001",
        name="Object Upload with ETag Precondition Checking",
        domain=TaskDomain.STORAGE,
        split=TaskSplit.DEV,
        objective="Upload configuration artifact manifest.json to S3 bucket production-assets.",
        initial_state_setup={"bucket": "production-assets"},
        allowed_tools=["put_object"],
        required_effects=[
            RequiredEffect(
                target="storage.production-assets.manifest.json",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Upload manifest.json object to storage bucket",
            )
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "storage.production-assets.manifest.json.key": "manifest.json",
        },
        scripted_plan=[
            TaskStepPlan(
                tool="put_object",
                args={
                    "bucket_name": "production-assets",
                    "key": "manifest.json",
                    "content": '{"version": "1.0.0", "build": 4021, "status": "OK"}',
                },
                description="Step 1: Upload manifest.json",
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
                expected_recovery_behavior="Upload object cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Object Put",
                description="Object stored in S3 bucket but HTTP ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Check bucket head-object / ETag witness before re-uploading",
            ),
        ],
        source="RecoverBench-Storage-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
