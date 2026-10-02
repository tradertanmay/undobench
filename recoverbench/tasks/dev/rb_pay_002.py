"""RB-PAY-002: Double-Entry Order Cancellation & Reversal."""

from recoverbench.domains.payments.payment_sandbox import DoubleEntryLedgerSandbox
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


def create_task_rb_pay_002() -> tuple[TaskSpec, DoubleEntryLedgerSandbox, ToolProxyRegistry]:
    sandbox = DoubleEntryLedgerSandbox()
    sandbox.seed_account("customer_funds", 20000)   # $200.00
    sandbox.seed_account("merchant_revenue", 0)

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="post_journal_entry",
        fn=sandbox.post_journal_entry,
        target="ledger.journal",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-PAY-002",
        name="Double-Entry Order Cancellation & Reversal",
        domain=TaskDomain.PAYMENTS,
        split=TaskSplit.DEV,
        objective="Charge customer $50.00 for order #901, then issue full compensating reversal upon cancellation.",
        initial_state_setup={"customer_funds": 20000, "merchant_revenue": 0},
        allowed_tools=["post_journal_entry"],
        required_effects=[
            RequiredEffect(
                target="ledger.journal",
                op_type=EffectOp.CREATE,
                max_occurrences=2,  # Exactly 2 entries: forward charge + compensating reversal
                description="Forward payment entry followed by compensating cancellation entry",
            )
        ],
        forbidden_effects=[],
        invariants=[
            InvariantDefinition(
                name="double_entry_conservation",
                description="Debits must strictly equal credits",
                expression="double_entry_conservation",
            )
        ],
        acceptable_final_states={
            "account_balances.customer_funds": 20000,
            "account_balances.merchant_revenue": 0,
            "journal_length": 2,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="post_journal_entry",
                args={
                    "debit_account": "merchant_revenue",
                    "credit_account": "customer_funds",
                    "amount_cents": 5000,
                    "memo": "Order #901 purchase",
                    "is_compensating": False,
                },
                description="Step 1: Charge customer $50.00",
            ),
            TaskStepPlan(
                tool="post_journal_entry",
                args={
                    "debit_account": "customer_funds",
                    "credit_account": "merchant_revenue",
                    "amount_cents": 5000,
                    "memo": "Order #901 compensation reversal",
                    "is_compensating": True,
                },
                description="Step 2: Compensate/refund $50.00",
            ),
        ],
        complexity=TaskComplexity.C4,
        provenance=TaskProvenance.ADAPTED_FROM_EVOUNDO_DEV,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.COMPENSATABLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Execute forward charge and clean compensation reversal",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-COMPENSATION-CRASH",
                name="Crash During Compensation",
                description="Crash injected during reverse compensating journal entry",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.DURING_COMPENSATION, perturbation=Perturbation.RECOVERY_CRASH, target_call_index=2),
                expected_recovery_behavior="Handle failed compensation and prevent corrupt partial reversals",
            ),
        ],
        source="EvoUndo-Accounting-Refactor",
        evoundo_influence=True,
    )

    return spec, sandbox, proxy_registry
