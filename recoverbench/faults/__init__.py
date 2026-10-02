"""Fault injection and tool proxy module."""

from recoverbench.faults.injector import (
    DeterministicFaultInjector,
    InjectedWorkerCrash,
    InjectedNetworkTimeout,
    InjectedAckLoss,
    InjectedRecoveryFailure,
    InjectedPartialWrite,
)
from recoverbench.faults.proxy import ToolProxyRegistry, WireEffectEvent

__all__ = [
    "DeterministicFaultInjector",
    "InjectedWorkerCrash",
    "InjectedNetworkTimeout",
    "InjectedAckLoss",
    "InjectedRecoveryFailure",
    "InjectedPartialWrite",
    "ToolProxyRegistry",
    "WireEffectEvent",
]
