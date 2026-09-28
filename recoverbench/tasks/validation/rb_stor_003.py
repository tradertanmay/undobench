"""RB-STOR-003: Cross-Bucket Archival & Source Deletion."""

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


def create_task_rb_stor_003() -> tuple[TaskSpec, ObjectStorageSandbox, ToolProxyRegistry]:
    sandbox = ObjectStorageSandbox()
    sandbox.seed_bucket("hot-storage")
    sandbox.seed_bucket("cold-archive")
    sandbox.seed_object("hot-storage", "report_q1.pdf", "%PDF-1.4 Report Content...")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="copy_object",
        fn=sandbox.copy_object,
        target="storage.cold-archive.report_q1.pdf",
        op_type=EffectOp.CREATE,
    )
    proxy_registry.register_tool(
        name="delete_object",
        fn=sandbox.delete_object,
        target="storage.hot-storage.report_q1.pdf",
        op_type=EffectOp.DELETE,
    )

    spec = TaskSpec(
        task_id="RB-STOR-003",
        name="Cross-Bucket Archival & Source Deletion",
        domain=TaskDomain.STORAGE,
        split=TaskSplit.VALIDATION,
        objective="Archive report_q1.pdf from hot-storage to cold-archive bucket, then delete from hot-storage.",
        initial_state_setup={"hot_bucket": "hot-storage", "archive_bucket": "cold-archive"},
        allowed_tools=["copy_object", "delete_object"],
        required_effects=[
            RequiredEffect(
                target="storage.cold-archive.report_q1.pdf",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Copy report object into cold-archive bucket",
            ),
            RequiredEffect(
                target="storage.hot-storage.report_q1.pdf",
                op_type=EffectOp.DELETE,
                max_occurrences=1,
                description="Delete source report object from hot-storage",
            ),
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "storage.cold-archive.report_q1.pdf.size_bytes": 26,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="copy_object",
                args={
                    "source_bucket": "hot-storage",
                    "source_key": "report_q1.pdf",
                    "dest_bucket": "cold-archive",
                    "dest_key": "report_q1.pdf",
                },
                description="Step 1: Copy to cold archive",
            ),
            TaskStepPlan(
                tool="delete_object",
                args={"bucket_name": "hot-storage", "key": "report_q1.pdf"},
                description="Step 2: Delete from hot storage",
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
                expected_recovery_behavior="Copy and delete objects cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Source Deletion",
                description="Object deleted from hot storage but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Verify object is already deleted before repeating deletion",
            ),
        ],
        source="RecoverBench-Storage-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
