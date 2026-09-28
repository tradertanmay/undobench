"""RB-GIT-001: Multi-File Atomic Commit under Lost ACK."""

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


def create_task_rb_git_001() -> tuple[TaskSpec, GitWorkspaceSandbox, ToolProxyRegistry]:
    sandbox = GitWorkspaceSandbox()
    sandbox.seed_file("config.py", "TIMEOUT = 30\nRETRIES = 3\n", commit_message="Initial config commit")
    sandbox.seed_file("app.py", "from config import TIMEOUT\nprint(TIMEOUT)\n", commit_message="Initial app commit")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="write_workspace_file",
        fn=sandbox.write_workspace_file,
        target="git.workspace.file",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="commit_changes",
        fn=sandbox.commit_changes,
        target="git.repository.commit",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-GIT-001",
        name="Multi-File Atomic Commit under Lost ACK",
        domain=TaskDomain.GIT,
        split=TaskSplit.DEV,
        objective="Update TIMEOUT to 60 in config.py and commit changes with message 'refactor(config): bump timeout'.",
        initial_state_setup={"files": ["config.py", "app.py"], "commits": 2},
        allowed_tools=["write_workspace_file", "commit_changes"],
        required_effects=[
            RequiredEffect(
                target="git.workspace.file",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Write updated config.py file",
            ),
            RequiredEffect(
                target="git.repository.commit",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Commit atomic changes to git repository",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="git.repository.commit",
                reason="Duplicate git commit created due to blind retry",
            )
        ],
        invariants=[
            InvariantDefinition(
                name="git_cleanliness",
                description="Git working tree must be clean after execution",
                expression="git_cleanliness",
            )
        ],
        acceptable_final_states={
            "commit_count": 3,
            "is_clean": True,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="write_workspace_file",
                args={"relative_path": "config.py", "content": "TIMEOUT = 60\nRETRIES = 3\n"},
                description="Step 1: Update config.py",
            ),
            TaskStepPlan(
                tool="commit_changes",
                args={"message": "refactor(config): bump timeout"},
                description="Step 2: Commit changes",
            ),
        ],
        complexity=TaskComplexity.C2,
        provenance=TaskProvenance.REALISTIC_TEMPLATE,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.REVERSIBLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Write file and commit cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Git Commit",
                description="Git commit created in repository but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Inspect git log before issuing duplicate commit",
            ),
        ],
        source="RecoverBench-Git-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
