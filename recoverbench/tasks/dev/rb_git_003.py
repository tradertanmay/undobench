"""RB-GIT-003: Multi-File Staging and Branch Creation under Lost ACK."""

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


def create_task_rb_git_003() -> tuple[TaskSpec, GitWorkspaceSandbox, ToolProxyRegistry]:
    sandbox = GitWorkspaceSandbox()
    sandbox.seed_file("README.md", "# Core Engine\n", commit_message="Initial commit")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="create_branch",
        fn=sandbox.create_branch,
        target="git.repository.branch.feature-auth",
        op_type=EffectOp.CREATE,
    )
    proxy_registry.register_tool(
        name="write_workspace_file",
        fn=sandbox.write_workspace_file,
        target="git.workspace.file.auth",
        op_type=EffectOp.CREATE,
    )
    proxy_registry.register_tool(
        name="commit_changes",
        fn=sandbox.commit_changes,
        target="git.repository.commit.auth",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-GIT-003",
        name="Multi-File Staging and Feature Branch Commit",
        domain=TaskDomain.GIT,
        split=TaskSplit.DEV,
        objective="Create feature branch 'feature-auth', write auth.py, and commit changes.",
        initial_state_setup={"branch": "main", "commits": 1},
        allowed_tools=["create_branch", "write_workspace_file", "commit_changes"],
        required_effects=[
            RequiredEffect(
                target="git.repository.branch.feature-auth",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Create git feature branch",
            ),
            RequiredEffect(
                target="git.workspace.file.auth",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Write auth module",
            ),
            RequiredEffect(
                target="git.repository.commit.auth",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Commit auth implementation",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="git.repository.commit.auth",
                reason="Duplicate commit created on feature branch",
            )
        ],
        invariants=[
            InvariantDefinition(
                name="git_cleanliness",
                description="Working tree must be clean",
                expression="git_cleanliness",
            )
        ],
        acceptable_final_states={
            "commit_count": 2,
            "is_clean": True,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="create_branch",
                args={"branch_name": "feature-auth"},
                description="Step 1: Create feature branch",
            ),
            TaskStepPlan(
                tool="write_workspace_file",
                args={"relative_path": "auth.py", "content": "def authenticate(token):\n    return True\n"},
                description="Step 2: Write auth.py",
            ),
            TaskStepPlan(
                tool="commit_changes",
                args={"message": "feat(auth): implement token authentication"},
                description="Step 3: Commit changes",
            ),
        ],
        complexity=TaskComplexity.C3,
        provenance=TaskProvenance.REALISTIC_TEMPLATE,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.REVERSIBLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Create branch, write file, and commit without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Feature Commit",
                description="Commit succeeds on feature branch but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=3),
                expected_recovery_behavior="Check git log on feature branch before duplicating commit",
            ),
        ],
        source="RecoverBench-Dev-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
