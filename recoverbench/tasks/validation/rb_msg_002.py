"""RB-MSG-002: Incident Notification Blast with SMS Fallback."""

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


def create_task_rb_msg_002() -> tuple[TaskSpec, MessagingNotificationSandbox, ToolProxyRegistry]:
    sandbox = MessagingNotificationSandbox()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="send_slack_alert",
        fn=sandbox.send_slack_alert,
        target="messaging.slack.#incidents",
        op_type=EffectOp.CREATE,
    )
    proxy_registry.register_tool(
        name="broadcast_sms_notification",
        fn=sandbox.broadcast_sms_notification,
        target="messaging.sms.+15550199",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-MSG-002",
        name="Incident Notification Blast with SMS Fallback",
        domain=TaskDomain.MESSAGING,
        split=TaskSplit.VALIDATION,
        objective="Dispatch high-priority incident blast to Slack channel #incidents and send urgent SMS alert to lead engineer.",
        initial_state_setup={},
        allowed_tools=["send_slack_alert", "broadcast_sms_notification"],
        required_effects=[
            RequiredEffect(
                target="messaging.slack.#incidents",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Post incident alert to #incidents channel",
            ),
            RequiredEffect(
                target="messaging.sms.+15550199",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Send urgent SMS alert to engineer phone",
            ),
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="messaging.sms.+15550199",
                reason="Duplicate SMS alert dispatched to phone due to blind retry",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "total_sent_notifications": 2,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="send_slack_alert",
                args={"channel": "#incidents", "message": "SEV1 Alert: Core API Cluster Latency Degraded"},
                description="Step 1: Broadcast Slack alert",
            ),
            TaskStepPlan(
                tool="broadcast_sms_notification",
                args={"phone_number": "+15550199", "text": "URGENT: Core API Cluster latency degraded. Join war room."},
                description="Step 2: Dispatch SMS alert",
            ),
        ],
        complexity=TaskComplexity.C2,
        provenance=TaskProvenance.NEW_FOR_RECOVERBENCH,
        outcome_observability=OutcomeObservability.KNOWN_EXECUTED,
        effect_reversibility=EffectReversibility.IRREVERSIBLE,
        supported_fault_scenarios=[
            FaultScenarioSpec(
                scenario_id="SCN-NO-FAULT",
                name="Failure-Free Control",
                description="Normal execution under zero faults",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE),
                expected_recovery_behavior="Broadcast Slack and SMS alerts cleanly",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on SMS Dispatch",
                description="SMS dispatched to cellular gateway but ACK dropped",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=2),
                expected_recovery_behavior="Check SMS provider delivery witness before sending duplicate text",
            ),
        ],
        source="RecoverBench-Messaging-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
