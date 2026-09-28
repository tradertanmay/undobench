"""RB-DB-005: Read-Modify-Write Bank Dividend Allocation (Frozen TEST Set)."""

from recoverbench.domains.database.sqlite_sandbox import SQLiteSandbox
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


def create_task_rb_db_005() -> tuple[TaskSpec, SQLiteSandbox, ToolProxyRegistry]:
    sandbox = SQLiteSandbox()
    sandbox.seed_account("acc_dividend_1", "Portfolio Fund A", 50000.0)

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="allocate_dividend",
        fn=sandbox.allocate_dividend,
        target="database.accounts.acc_dividend_1.dividend",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-DB-005",
        name="Read-Modify-Write Bank Dividend Allocation",
        domain=TaskDomain.DATABASE,
        split=TaskSplit.TEST,
        objective="Allocate quarterly dividend of $2,500.00 to account acc_dividend_1.",
        initial_state_setup={"account_id": "acc_dividend_1", "initial_balance": 50000.0},
        allowed_tools=["allocate_dividend"],
        required_effects=[
            RequiredEffect(
                target="database.accounts.acc_dividend_1.dividend",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Allocate exactly one dividend payment of $2,500.00",
            )
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="database.accounts.acc_dividend_1.dividend",
                reason="Double allocation of dividend resulting in financial loss",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "accounts.acc_dividend_1": 52500.0,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="allocate_dividend",
                args={"account_id": "acc_dividend_1", "dividend": 2500.0},
                description="Step 1: Allocate dividend",
            )
        ],
        complexity=TaskComplexity.C1,
        provenance=TaskProvenance.NEW_FOR_RECOVERBENCH,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Allocate dividend cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Dividend Credit",
                description="Dividend credited to account but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Inspect account balance witness before double-crediting dividend",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
