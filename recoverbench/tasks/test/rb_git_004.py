"""RB-GIT-004: Release Tag Cut and Cherry-Pick (Frozen TEST Set)."""

from recoverbench.domains.git.git_sandbox import GitWorkspaceSandbox
from recoverbench.faults.proxy import ToolProxyRegistry
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.schemas.task import (
    EffectOp,
    EffectReversibility,
    FaultScenarioSpec,
    ForbiddenEffect,
    InvariantDefinition,
    OutcomeObservability,
    RequiredEffect,
    TaskComplexity,
    TaskDomain,
    TaskProvenance,
    TaskSpec,
    TaskSplit,
    TaskStepPlan,
)


def create_task_rb_git_004() -> tuple[TaskSpec, GitWorkspaceSandbox, ToolProxyRegistry]:
    sandbox = GitWorkspaceSandbox()
    sandbox.seed_file("version.py", "VERSION = '2.0.0'\n", commit_message="Release v2.0.0")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="create_tag",
        fn=sandbox.create_tag,
        target="git.repository.tag.v2.0.0",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-GIT-004",
        name="Release Tag Cut and Cherry-Pick",
        domain=TaskDomain.GIT,
        split=TaskSplit.TEST,
        objective="Cut annotated release tag 'v2.0.0' on the current release commit.",
        initial_state_setup={"commits": 1, "tags": 0},
        allowed_tools=["create_tag"],
        required_effects=[
            RequiredEffect(
                target="git.repository.tag.v2.0.0",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Create release tag v2.0.0",
            )
        ],
        forbidden_effects=[],
        invariants=[
            InvariantDefinition(
                name="git_cleanliness",
                description="Working tree must remain clean",
                expression="git_cleanliness",
            )
        ],
        acceptable_final_states={
            "tag_count": 1,
            "is_clean": True,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="create_tag",
                args={"tag_name": "v2.0.0", "message": "Official 2.0.0 Release"},
                description="Step 1: Create release tag",
            )
        ],
        complexity=TaskComplexity.C1,
        provenance=TaskProvenance.NEW_FOR_RECOVERBENCH,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.REVERSIBLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Cut release tag cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Tag Creation",
                description="Tag created in git repo but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Query git tags before repeating tag creation command",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
