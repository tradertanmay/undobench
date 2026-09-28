"""RB-GIT-002: Hotfix Branch Merge with Fast-Forward Conflict."""

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


def create_task_rb_git_002() -> tuple[TaskSpec, GitWorkspaceSandbox, ToolProxyRegistry]:
    sandbox = GitWorkspaceSandbox()
    sandbox.seed_file("main.py", "print('v1.0')\n", commit_message="Release v1.0")
    sandbox.create_branch("hotfix-sec")
    sandbox.write_workspace_file("main.py", "print('v1.0.1-sec')\n")
    sandbox.commit_changes("fix(sec): patch critical cve")
    # Switch back to main branch so merge can happen
    sandbox._run_git("checkout", "main")

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="merge_branch",
        fn=sandbox.merge_branch,
        target="git.repository.merge.hotfix-sec",
        op_type=EffectOp.EXECUTE,
    )

    spec = TaskSpec(
        task_id="RB-GIT-002",
        name="Hotfix Branch Fast-Forward Merge",
        domain=TaskDomain.GIT,
        split=TaskSplit.VALIDATION,
        objective="Merge hotfix branch 'hotfix-sec' into main branch using fast-forward merge.",
        initial_state_setup={"current_branch": "main", "merge_target": "hotfix-sec"},
        allowed_tools=["merge_branch"],
        required_effects=[
            RequiredEffect(
                target="git.repository.merge.hotfix-sec",
                op_type=EffectOp.EXECUTE,
                max_occurrences=1,
                description="Fast-forward merge hotfix branch into main",
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
            "commit_count": 2,
            "is_clean": True,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="merge_branch",
                args={"branch_name": "hotfix-sec", "fast_forward": True},
                description="Step 1: Merge hotfix branch",
            )
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
                expected_recovery_behavior="Merge hotfix cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Git Merge",
                description="Merge completes in git index but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Verify current HEAD commit hash before re-executing merge command",
            ),
        ],
        source="RecoverBench-Git-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
