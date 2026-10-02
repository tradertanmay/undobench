"""RB-STOR-004: Cross-Bucket Replication with Preconditions (Frozen TEST Set)."""

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


def create_task_rb_stor_004() -> tuple[TaskSpec, ObjectStorageSandbox, ToolProxyRegistry]:
    sandbox = ObjectStorageSandbox()
    sandbox.seed_bucket("us-east-primary")
    sandbox.seed_bucket("eu-west-replica")
    sandbox.seed_object("us-east-primary", "dataset_v3.bin", "BINARY_DATASET_V3_CONTENT")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="copy_object",
        fn=sandbox.copy_object,
        target="storage.eu-west-replica.dataset_v3.bin",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-STOR-004",
        name="Cross-Bucket Object Replication",
        domain=TaskDomain.STORAGE,
        split=TaskSplit.TEST,
        objective="Replicate dataset_v3.bin from us-east-primary to eu-west-replica bucket.",
        initial_state_setup={"source_bucket": "us-east-primary", "target_bucket": "eu-west-replica"},
        allowed_tools=["copy_object"],
        required_effects=[
            RequiredEffect(
                target="storage.eu-west-replica.dataset_v3.bin",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Replicate dataset into eu-west-replica bucket",
            )
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "storage.eu-west-replica.dataset_v3.bin.size_bytes": 25,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="copy_object",
                args={
                    "source_bucket": "us-east-primary",
                    "source_key": "dataset_v3.bin",
                    "dest_bucket": "eu-west-replica",
                    "dest_key": "dataset_v3.bin",
                },
                description="Step 1: Replicate object",
            )
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
                expected_recovery_behavior="Replicate object cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Replication Copy",
                description="Object replicated to replica bucket but copy ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Verify target replica object ETag before re-transmitting replication stream",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
