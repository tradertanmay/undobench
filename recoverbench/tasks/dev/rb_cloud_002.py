"""RB-CLOUD-002: Multi-Tier Cluster Provisioning under Lost ACK."""

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


def create_task_rb_cloud_002() -> tuple[TaskSpec, CloudResourceSandbox, ToolProxyRegistry]:
    sandbox = CloudResourceSandbox()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="provision_cluster_tier",
        fn=sandbox.provision_cluster_tier,
        target="cloud.cluster.tier",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-CLOUD-002",
        name="Multi-Tier Cluster Provisioning",
        domain=TaskDomain.CLOUD,
        split=TaskSplit.DEV,
        objective="Provision multi-tier cluster: 4 app nodes (tier 'web-tier') and 2 cache nodes (tier 'redis-tier').",
        initial_state_setup={"cluster_nodes": 0},
        allowed_tools=["provision_cluster_tier"],
        required_effects=[
            RequiredEffect(
                target="cloud.cluster.tier",
                op_type=EffectOp.CREATE,
                max_occurrences=2,
                description="Provision web-tier and redis-tier",
            )
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="cloud.cluster.tier",
                reason="Overprovisioned duplicate cluster nodes due to blind retry",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "services.web-tier.desired_replicas": 4,
            "services.redis-tier.desired_replicas": 2,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="provision_cluster_tier",
                args={"tier_name": "web-tier", "instance_count": 4, "instance_type": "c5.xlarge"},
                description="Step 1: Provision web tier",
            ),
            TaskStepPlan(
                tool="provision_cluster_tier",
                args={"tier_name": "redis-tier", "instance_count": 2, "instance_type": "r5.large"},
                description="Step 2: Provision redis tier",
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
                expected_recovery_behavior="Provision both tiers cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Tier Provisioning",
                description="Web tier provisioned in cloud but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Query cloud resource registry before re-provisioning duplicate nodes",
            ),
        ],
        source="RecoverBench-Dev-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
