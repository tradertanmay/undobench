"""RB-STOR-002: Multipart Large File Assembly and Verification."""

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


def create_task_rb_stor_002() -> tuple[TaskSpec, ObjectStorageSandbox, ToolProxyRegistry]:
    sandbox = ObjectStorageSandbox()
    sandbox.seed_bucket("data-lake")
    upload = sandbox.initiate_multipart_upload("data-lake", "archive_2026.tar.gz")
    upload_id = upload["upload_id"]

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="upload_part",
        fn=sandbox.upload_part,
        target="storage.data-lake.multipart.part2",
        op_type=EffectOp.CREATE,
    )
    proxy_registry.register_tool(
        name="complete_multipart_upload",
        fn=sandbox.complete_multipart_upload,
        target="storage.data-lake.archive_2026.tar.gz",
        op_type=EffectOp.CREATE,
    )

    # Pre-upload part 1
    sandbox.upload_part(upload_id, 1, "CHUNK_HEADER_DATA_")

    spec = TaskSpec(
        task_id="RB-STOR-002",
        name="Multipart Large File Assembly and Verification",
        domain=TaskDomain.STORAGE,
        split=TaskSplit.VALIDATION,
        objective=f"Upload part 2 to multipart upload {upload_id} and assemble final object archive_2026.tar.gz.",
        initial_state_setup={"bucket": "data-lake", "upload_id": upload_id},
        allowed_tools=["upload_part", "complete_multipart_upload"],
        required_effects=[
            RequiredEffect(
                target="storage.data-lake.multipart.part2",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Upload part 2 chunk data",
            ),
            RequiredEffect(
                target="storage.data-lake.archive_2026.tar.gz",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Complete multipart upload assembly",
            ),
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "storage.data-lake.archive_2026.tar.gz.size_bytes": 40,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="upload_part",
                args={"upload_id": upload_id, "part_number": 2, "data": "CHUNK_PAYLOAD_DATA_END"},
                description="Step 1: Upload part 2",
            ),
            TaskStepPlan(
                tool="complete_multipart_upload",
                args={"upload_id": upload_id, "parts": []},
                description="Step 2: Complete multipart upload",
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
                expected_recovery_behavior="Upload part 2 and assemble archive cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Complete Multipart Upload",
                description="Object assembled in S3 bucket but complete ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Verify assembled object existence before re-completing",
            ),
        ],
        source="RecoverBench-Storage-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
