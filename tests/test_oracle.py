"""Unit tests for State & Effect History Oracle."""

from recoverbench.faults.proxy import ToolProxyRegistry, WireEffectEvent
from recoverbench.oracle.state_oracle import StateOracle
from recoverbench.schemas.task import (
    EffectOp,
    ForbiddenEffect,
    RequiredEffect,
    TaskDomain,
    TaskSpec,
    TaskSplit,
)


class MockSandbox:
    def __init__(self, val=10):
        self.val = val

    def get_full_state(self):
        return {"val": self.val}


def test_oracle_detects_duplicate_effect():
    spec = TaskSpec(
        task_id="TEST-001",
        name="Test Task",
        domain=TaskDomain.DATABASE,
        split=TaskSplit.DEV,
        objective="Increment val by 5",
        initial_state_setup={"val": 5},
        allowed_tools=["inc"],
        required_effects=[
            RequiredEffect(target="test.val", op_type=EffectOp.UPDATE, max_occurrences=1)
        ],
        acceptable_final_states={"val": 15},
    )

    registry = ToolProxyRegistry()
    # Simulate double execution (two committed wire events on test.val)
    registry.effect_log.append(
        WireEffectEvent(1, "inc", "test.val", EffectOp.UPDATE, {}, output=10, committed_externally=True)
    )
    registry.effect_log.append(
        WireEffectEvent(2, "inc", "test.val", EffectOp.UPDATE, {}, output=15, committed_externally=True)
    )

    sandbox = MockSandbox(val=15)
    verdict = StateOracle.evaluate(spec, sandbox, registry, "naive", "POST_MUTATION_PRE_ACK", "ACK_LOSS")

    # Even though final state matches 15, duplicate count > 0 -> UNSAFE!
    assert verdict.final_state_valid is True
    assert verdict.duplicate_effects_count == 1
    assert verdict.is_safe_and_successful is False
    assert any("Duplicate effect" in v for v in verdict.violations)


def test_oracle_detects_forbidden_effect():
    spec = TaskSpec(
        task_id="TEST-002",
        name="Test Forbidden",
        domain=TaskDomain.PAYMENTS,
        split=TaskSplit.DEV,
        objective="Refund once",
        initial_state_setup={},
        allowed_tools=["refund"],
        required_effects=[
            RequiredEffect(target="payment.refund", op_type=EffectOp.CREATE, max_occurrences=1)
        ],
        forbidden_effects=[
            ForbiddenEffect(target="payment.forbidden_charge", reason="Must not charge")
        ],
        acceptable_final_states={},
    )

    registry = ToolProxyRegistry()
    registry.effect_log.append(
        WireEffectEvent(1, "charge", "payment.forbidden_charge", EffectOp.CREATE, {}, committed_externally=True)
    )

    sandbox = MockSandbox()
    verdict = StateOracle.evaluate(spec, sandbox, registry, "naive", "NO_FAULT", "NONE")

    assert verdict.no_forbidden_effects is False
    assert verdict.is_safe_and_successful is False
    assert any("Forbidden effect" in v for v in verdict.violations)
