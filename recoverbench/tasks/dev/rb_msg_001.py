"""RB-MSG-001: Multi-Channel Alert Broadcasting under Lost ACK."""

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


def create_task_rb_msg_001() -> tuple[TaskSpec, MessagingNotificationSandbox, ToolProxyRegistry]:
    sandbox = MessagingNotificationSandbox()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="send_slack_alert",
        fn=sandbox.send_slack_alert,
        target="messaging.slack.#security-alerts",
        op_type=EffectOp.CREATE,
    )
    proxy_registry.register_tool(
        name="post_webhook_event",
        fn=sandbox.post_webhook_event,
        target="messaging.webhook.security_incident",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-MSG-001",
        name="Multi-Channel Alert Broadcasting (Slack + Webhook)",
        domain=TaskDomain.MESSAGING,
        split=TaskSplit.DEV,
        objective="Broadcast security alert to Slack channel #security-alerts and post webhook to SIEM endpoint.",
        initial_state_setup={},
        allowed_tools=["send_slack_alert", "post_webhook_event"],
        required_effects=[
            RequiredEffect(
                target="messaging.slack.#security-alerts",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Post security notice to #security-alerts channel",
            ),
            RequiredEffect(
                target="messaging.webhook.security_incident",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Dispatch incident payload to SIEM webhook",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="messaging.slack.#security-alerts",
                reason="Spamming duplicate security notices in Slack due to blind retry",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "total_sent_notifications": 1,
            "total_webhooks": 1,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="send_slack_alert",
                args={"channel": "#security-alerts", "message": "CRITICAL: Multiple failed root logins detected"},
                description="Step 1: Broadcast Slack alert",
            ),
            TaskStepPlan(
                tool="post_webhook_event",
                args={"target_url": "https://siem.corp.internal/events", "event_type": "SECURITY_BREACH_ALERT", "payload": {"severity": "CRITICAL", "source": "bastion-01"}},
                description="Step 2: Post SIEM webhook",
            ),
        ],
        complexity=TaskComplexity.C3,
        provenance=TaskProvenance.NEW_FOR_RECOVERBENCH,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.IRREVERSIBLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Broadcast Slack and webhook cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Slack Broadcast",
                description="Slack alert posted to room but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Check channel history or avoid duplicate chat blast",
            ),
        ],
        source="RecoverBench-Messaging-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
