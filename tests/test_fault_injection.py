"""Unit tests for deterministic fault injection at execution boundaries."""

import pytest
from recoverbench.faults.injector import (
    DeterministicFaultInjector,
    InjectedAckLoss,
    InjectedWorkerCrash,
)
from recoverbench.faults.proxy import ToolProxyRegistry
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.schemas.task import EffectOp


def test_pre_mutation_crash():
    registry = ToolProxyRegistry()
    called = []

    def mock_tool(val):
        called.append(val)
        return val * 2

    registry.register_tool("mock", mock_tool, "test.resource", EffectOp.UPDATE)
    injector = DeterministicFaultInjector(
        FaultSpec(boundary=ExecutionBoundary.PRE_MUTATION, perturbation=Perturbation.WORKER_CRASH)
    )
    registry.injector = injector

    tool = registry.get_proxied_tool("mock")
    with pytest.raises(InjectedWorkerCrash):
        tool(5)

    # Tool body was NEVER executed
    assert len(called) == 0
    assert len(registry.effect_log) == 1
    assert registry.effect_log[0].committed_externally is False


def test_post_mutation_pre_ack_loss():
    registry = ToolProxyRegistry()
    called = []

    def mock_tool(val):
        called.append(val)
        return val * 2

    registry.register_tool("mock", mock_tool, "test.resource", EffectOp.UPDATE)
    injector = DeterministicFaultInjector(
        FaultSpec(boundary=ExecutionBoundary.POST_MUTATION_PRE_ACK, perturbation=Perturbation.ACK_LOSS)
    )
    registry.injector = injector

    tool = registry.get_proxied_tool("mock")
    with pytest.raises(InjectedAckLoss):
        tool(10)

    # External effect committed, but ACK dropped!
    assert len(called) == 1
    assert called[0] == 10
    assert len(registry.effect_log) == 1
    assert registry.effect_log[0].committed_externally is True
    assert registry.effect_log[0].acknowledged_to_agent is False
