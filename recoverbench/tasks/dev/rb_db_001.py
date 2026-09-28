"""RB-DB-001: Account Balance Transfer under Lost ACK."""

from recoverbench.domains.database.sqlite_sandbox import SQLiteSandbox
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


def create_task_rb_db_001() -> tuple[TaskSpec, SQLiteSandbox, ToolProxyRegistry]:
    sandbox = SQLiteSandbox()
    # Seed Alice with $100, Bob with $50
    sandbox.seed_account("acc_alice", "Alice", 100.0)
    sandbox.seed_account("acc_bob", "Bob", 50.0)

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="deduct_account_balance",
        fn=sandbox.deduct_account_balance,
        target="accounts.acc_alice.balance",
        op_type=EffectOp.UPDATE,
    )
    proxy_registry.register_tool(
        name="credit_account_balance",
        fn=sandbox.credit_account_balance,
        target="accounts.acc_bob.balance",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-DB-001",
        name="Account Balance Transfer under Lost ACK",
        domain=TaskDomain.DATABASE,
        split=TaskSplit.DEV,
        objective="Transfer $30 from Alice's account (acc_alice) to Bob's account (acc_bob).",
        initial_state_setup={"accounts": {"acc_alice": 100.0, "acc_bob": 50.0}},
        allowed_tools=["deduct_account_balance", "credit_account_balance"],
        required_effects=[
            RequiredEffect(
                target="accounts.acc_alice.balance",
                op_type=EffectOp.UPDATE,
                expected_value=70.0,
                max_occurrences=1,
                description="Deduct $30 from Alice's account",
            ),
            RequiredEffect(
                target="accounts.acc_bob.balance",
                op_type=EffectOp.UPDATE,
                expected_value=80.0,
                max_occurrences=1,
                description="Credit $30 to Bob's account",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="accounts.acc_alice.balance",
                forbidden_value=40.0,
                reason="Double deduction from Alice's account due to unsafe retry",
            )
        ],
        invariants=[
            InvariantDefinition(
                name="non_negative_alice",
                description="Alice balance must not be negative",
                expression="non_negative_balance",
            )
        ],
        acceptable_final_states={
            "accounts.acc_alice": 70.0,
            "accounts.acc_bob": 80.0,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="deduct_account_balance",
                args={"account_id": "acc_alice", "amount": 30.0},
                description="Step 1: Deduct 30 from Alice",
            ),
            TaskStepPlan(
                tool="credit_account_balance",
                args={"account_id": "acc_bob", "amount": 30.0},
                description="Step 2: Credit 30 to Bob",
            ),
        ],
        complexity=TaskComplexity.C2,
        provenance=TaskProvenance.ADAPTED_FROM_EVOUNDO_DEV,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Complete transfer without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Debit",
                description="Deduct succeeds externally but ACK is dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Detect external state witness before retrying debit",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-PRE-MUT-DROP",
                name="Transient Drop before Debit",
                description="Network drop before debit executes",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.PRE_MUTATION, perturbation=Perturbation.NETWORK_TIMEOUT, target_call_index=1),
                expected_recovery_behavior="Safe retry on initial debit",
            ),
        ],
        source="EvoUndo-Dogfood-Refactor",
        evoundo_influence=True,
    )

    return spec, sandbox, proxy_registry
