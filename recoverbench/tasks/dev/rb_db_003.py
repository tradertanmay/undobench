"""RB-DB-003: Multi-Table Order Insertion & Stock Reservation under Lost ACK."""

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


def create_task_rb_db_003() -> tuple[TaskSpec, SQLiteSandbox, ToolProxyRegistry]:
    sandbox = SQLiteSandbox()
    sandbox.seed_inventory("ITEM-GPU-01", 10)

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="create_order",
        fn=sandbox.create_order,
        target="database.orders.ORD-1001",
        op_type=EffectOp.CREATE,
    )
    proxy_registry.register_tool(
        name="reserve_inventory",
        fn=sandbox.reserve_inventory,
        target="database.inventory.ITEM-GPU-01",
        op_type=EffectOp.UPDATE,
    )

    spec = TaskSpec(
        task_id="RB-DB-003",
        name="Multi-Table Order Insertion & Stock Reservation",
        domain=TaskDomain.DATABASE,
        split=TaskSplit.DEV,
        objective="Create customer order ORD-1001 for $1200 and reserve 2 units of ITEM-GPU-01.",
        initial_state_setup={"inventory": {"ITEM-GPU-01": 10}},
        allowed_tools=["create_order", "reserve_inventory"],
        required_effects=[
            RequiredEffect(
                target="database.orders.ORD-1001",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Insert order record ORD-1001",
            ),
            RequiredEffect(
                target="database.inventory.ITEM-GPU-01",
                op_type=EffectOp.UPDATE,
                max_occurrences=1,
                description="Reserve 2 units from inventory (reduce from 10 to 8)",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="database.inventory.ITEM-GPU-01",
                reason="Double reservation of inventory due to blind retry",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "orders.ORD-1001.amount": 1200.0,
            "inventory.ITEM-GPU-01": 8,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="create_order",
                args={"order_id": "ORD-1001", "customer_id": "cust_301", "amount": 1200.0, "status": "CONFIRMED"},
                description="Step 1: Create order ORD-1001",
            ),
            TaskStepPlan(
                tool="reserve_inventory",
                args={"item_id": "ITEM-GPU-01", "quantity": 2},
                description="Step 2: Reserve 2 units from inventory",
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
                expected_recovery_behavior="Create order and reserve inventory cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Inventory Reservation",
                description="Inventory reserved in database but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Witness current stock level before re-decrementing",
            ),
        ],
        source="RecoverBench-Dev-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
