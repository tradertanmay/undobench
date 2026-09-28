from recoverbench.domains.cloud.cloud_sandbox import CloudResourceSandbox
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


def create_task_rb_cloud_001() -> tuple[TaskSpec, CloudResourceSandbox, ToolProxyRegistry]:
    sandbox = CloudResourceSandbox()
    sandbox.seed_service("checkout-service", desired_replicas=3)

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="scale_service",
        fn=sandbox.scale_service,
        target="cloud.service.checkout-service.scale",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="sync_discovery_catalog",
        fn=sandbox.sync_discovery_catalog,
        target="cloud.discovery.catalog.checkout-service",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-CLOUD-001",
        name="Cloud Service Scale-Out & Discovery Sync",
        domain=TaskDomain.CLOUD,
        split=TaskSplit.VALIDATION,
        objective="Scale checkout-service from 3 to 6 replicas and sync service discovery catalog.",
        initial_state_setup={"service_name": "checkout-service", "replicas": 3},
        allowed_tools=["scale_service", "sync_discovery_catalog"],
        required_effects=[
            RequiredEffect(
                target="cloud.service.checkout-service.scale",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Scale compute replicas to exactly 6",
            ),
            RequiredEffect(
                target="cloud.discovery.catalog.checkout-service",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Synchronize active instances with discovery catalog",
            ),
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "services.checkout-service.desired_replicas": 6,
            "running_replicas": 6,
            "catalog_count": 6,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="scale_service",
                args={"service_name": "checkout-service", "new_replicas": 6},
                description="Step 1: Scale instances to 6",
            ),
            TaskStepPlan(
                tool="sync_discovery_catalog",
                args={"service_name": "checkout-service"},
                description="Step 2: Sync discovery catalog",
            ),
        ],
        complexity=TaskComplexity.C3,
        provenance=TaskProvenance.REALISTIC_TEMPLATE,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Scale instances and sync catalog cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-POST-ACK-PRE-CHECKPOINT",
                name="Crash Post-ACK Pre-Checkpoint",
                description="Scale succeeds and ACK returned, but worker crashes before catalog sync",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_ACK_PRE_CHECKPOINT, perturbation=Perturbation.WORKER_CRASH, target_call_index=1),
                expected_recovery_behavior="Resume and synchronize discovery catalog without re-scaling",
            ),
        ],
        source="RecoverBench-Validation-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
