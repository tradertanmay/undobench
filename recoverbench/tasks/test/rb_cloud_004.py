"""RB-CLOUD-004: Blue-Green Service Deployment Cutover (Frozen TEST Set)."""

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


def create_task_rb_cloud_004() -> tuple[TaskSpec, CloudResourceSandbox, ToolProxyRegistry]:
    sandbox = CloudResourceSandbox()
    sandbox.seed_service("billing-api", desired_replicas=3)

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="deploy_green_service",
        fn=sandbox.deploy_green_service,
        target="cloud.deployment.billing-api-green",
        op_type=EffectOp.CREATE,
    )
    proxy_registry.register_tool(
        name="switch_traffic_routing",
        fn=sandbox.switch_traffic_routing,
        target="cloud.routing.billing-api.active",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-CLOUD-004",
        name="Blue-Green Service Deployment Cutover",
        domain=TaskDomain.CLOUD,
        split=TaskSplit.TEST,
        objective="Deploy green service environment for billing-api (version 'v2.4.0') and cut over traffic routing to 'green'.",
        initial_state_setup={"service": "billing-api", "active_color": "blue"},
        allowed_tools=["deploy_green_service", "switch_traffic_routing"],
        required_effects=[
            RequiredEffect(
                target="cloud.deployment.billing-api-green",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Deploy green service environment",
            ),
            RequiredEffect(
                target="cloud.routing.billing-api.active",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Switch active ingress route to green",
            ),
        ],
        forbidden_effects=[],
        invariants=[],
        acceptable_final_states={
            "services.billing-api-green.desired_replicas": 3,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="deploy_green_service",
                args={"service_name": "billing-api", "version": "v2.4.0"},
                description="Step 1: Deploy green service",
            ),
            TaskStepPlan(
                tool="switch_traffic_routing",
                args={"service_name": "billing-api", "target_color": "green"},
                description="Step 2: Switch traffic routing to green",
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
                expected_recovery_behavior="Deploy green service and switch traffic cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Traffic Cutover",
                description="Traffic router cutover executed in cloud but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Check active router ingress state before repeating cutover signal",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
