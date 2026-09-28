"""RB-MSG-003: Batch Email Campaign Dispatch under Lost ACK."""

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


def create_task_rb_msg_003() -> tuple[TaskSpec, MessagingNotificationSandbox, ToolProxyRegistry]:
    sandbox = MessagingNotificationSandbox()

    proxy_registry = ToolProxyRegistry()
    proxy_registry.register_tool(
        name="send_batch_email",
        fn=sandbox.send_batch_email,
        target="messaging.email.batch.camp_q3_newsletter",
        op_type=EffectOp.CREATE,
    )

    spec = TaskSpec(
        task_id="RB-MSG-003",
        name="Batch Email Campaign Dispatch with Rate Limits",
        domain=TaskDomain.MESSAGING,
        split=TaskSplit.DEV,
        objective="Dispatch Q3 product newsletter batch email campaign to 3 subscribers.",
        initial_state_setup={},
        allowed_tools=["send_batch_email"],
        required_effects=[
            RequiredEffect(
                target="messaging.email.batch.camp_q3_newsletter",
                op_type=EffectOp.CREATE,
                max_occurrences=1,
                description="Dispatch exactly one batch email campaign",
            )
        ],
        forbidden_effects=[
            ForbiddenEffect(
                target="messaging.email.batch.camp_q3_newsletter",
                reason="Spamming duplicate email batches to customer subscriber list",
            )
        ],
        invariants=[],
        acceptable_final_states={
            "total_sent_notifications": 3,
        },
        scripted_plan=[
            TaskStepPlan(
                tool="send_batch_email",
                args={
                    "campaign_id": "camp_q3_newsletter",
                    "recipients": ["user1@domain.com", "user2@domain.com", "user3@domain.com"],
                    "template_id": "tmpl_newsletter_v3",
                },
                description="Step 1: Send batch newsletter",
            )
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
                expected_recovery_behavior="Send batch email campaign cleanly without retries",
            ),
            FaultScenarioSpec(
                scenario_id="SCN-LOST-ACK",
                name="Lost-ACK on Email Batch",
                description="Email batch dispatched to provider queue but ACK lost",
                fault_spec=FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS, target_call_index=1),
                expected_recovery_behavior="Use campaign idempotency key or witness provider campaign status",
            ),
        ],
        source="RecoverBench-Messaging-Original",
        evoundo_influence=False,
    )

    return spec, sandbox, proxy_registry
