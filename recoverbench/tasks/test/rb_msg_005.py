"""RB-MSG-005: Webhook Fanout with Delivery Confirmation (Frozen TEST Set)."""

from recoverbench.domains.messaging.messaging_sandbox import MessagingNotificationSandbox
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


def create_task_rb_msg_005() -> tuple[TaskSpec, MessagingNotificationSandbox, ToolProxyRegistry]:
    sandbox = MessagingNotificationSandbox()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="post_webhook_event",
        fn=sandbox.post_webhook_event,
        target="messaging.webhook.fanout.partner_gateway",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-MSG-005",
        name="Webhook Fanout with Delivery Confirmation",
        domain=TaskDomain.MESSAGING,
        split=TaskSplit.TEST,
        objective="Dispatch high-volume transaction webhook to partner gateway endpoint.",
        initial_state_setup={},
        allowed_tools=["post_webhook_event"],
        required_effects=[
            RequiredEffect(
                target="messaging.webhook.fanout.partner_gateway",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Post webhook transaction payload to partner endpoint",
            )
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="messaging.webhook.fanout.partner_gateway",
                reason="Duplicate webhook delivery to partner system causing replay bugs",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "total_webhooks": 1,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="post_webhook_event",
                args={
                    "target_url": "https://partner.external-api.com/webhook",
                    "event_type": "ORDER_SETTLED",
                    "payload": {"order_id": "ORD-9901", "amount": 450.00, "status": "SETTLED"},
                },
                description="Step 1: Post webhook event",
            )
        ],
        complexity=TaskComplexity.C1,
        provenance=TaskProvenance.NEW_FOR_RECOVERBENCH,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.IRREVERSIBLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Post webhook event cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Webhook Delivery",
                description="Webhook accepted with HTTP 200 by partner but response ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Attach webhook idempotency signature or query partner receipt status",
            ),
        ],
        source="RecoverBench-Test-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
