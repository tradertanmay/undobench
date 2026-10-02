"""Deterministic fault injector for boundary and perturbation interception."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation


class InjectedWorkerCrash(RuntimeError):
    """Simulated worker process crash."""
    pass


class InjectedNetworkTimeout(TimeoutError):
    """Simulated network timeout during tool call."""
    pass


class InjectedAckLoss(ConnectionResetError):
    """Simulated dropped acknowledgement after external mutation."""
    pass


class InjectedRecoveryFailure(RuntimeError):
    """Simulated failure during recovery or inverse operation."""
    pass


class InjectedPartialWrite(IOError):
    """Simulated partial write corruption."""
    pass


class DeterministicFaultInjector:
    """Controls dynamic fault injection at exact execution boundaries."""

    def __init__(self, fault_spec: Optional[FaultSpec] = None):
        self.fault_spec = fault_spec or FaultSpec()
        self.triggered_count: int = 0
        self.injection_log: List[Dict[str, Any]] = []

    def configure(self, fault_spec: FaultSpec) -> None:
        self.fault_spec = fault_spec
        self.triggered_count = 0
        self.injection_log.clear()

    def should_trigger(self, boundary: ExecutionBoundary, tool_name: str, call_index: int) -> bool:
        """Evaluate if fault should trigger at the given boundary and tool invocation."""
        if not self.fault_spec.is_active:
            return False

        if self.fault_spec.boundary != boundary:
            return False

        if self.fault_spec.target_tool and self.fault_spec.target_tool != tool_name:
            return False

        if self.fault_spec.target_call_index and self.fault_spec.target_call_index != call_index:
            return False

        if self.triggered_count >= self.fault_spec.injected_count:
            return False

        return True

    def trigger(self, boundary: ExecutionBoundary, tool_name: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Inject the designated perturbation at the current boundary."""
        self.triggered_count += 1
        perturbation = self.fault_spec.perturbation

        self.injection_log.append({
            "boundary": boundary.value,
            "perturbation": perturbation.value,
            "tool_name": tool_name,
            "trigger_index": self.triggered_count,
            "context": context or {},
        })

        if perturbation == Perturbation.WORKER_CRASH:
            raise InjectedWorkerCrash(
                f"[RECOVERBENCH INJECTED] Worker crashed at boundary {boundary.value} for tool '{tool_name}'"
            )
        elif perturbation == Perturbation.NETWORK_TIMEOUT:
            raise InjectedNetworkTimeout(
                f"[RECOVERBENCH INJECTED] Network timed out at boundary {boundary.value} for tool '{tool_name}'"
            )
        elif perturbation == Perturbation.ACK_LOSS:
            raise InjectedAckLoss(
                f"[RECOVERBENCH INJECTED] Lost ACK at boundary {boundary.value} for tool '{tool_name}'"
            )
        elif perturbation == Perturbation.RECOVERY_CRASH:
            raise InjectedRecoveryFailure(
                f"[RECOVERBENCH INJECTED] Recovery crashed at boundary {boundary.value} for tool '{tool_name}'"
            )
        elif perturbation == Perturbation.PARTIAL_WRITE:
            raise InjectedPartialWrite(
                f"[RECOVERBENCH INJECTED] Partial write error at boundary {boundary.value} for tool '{tool_name}'"
            )
        elif perturbation == Perturbation.CONCURRENT_WRITE:
            # For concurrent writes, a custom callback or delta is executed without raising fatal exception
            pass
