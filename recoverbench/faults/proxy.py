"""Method-agnostic Tool Proxy and Effect Event Logger."""

from __future__ import annotations
import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from recoverbench.faults.injector import DeterministicFaultInjector
from recoverbench.schemas.fault import ExecutionBoundary
from recoverbench.schemas.task import EffectOp


@dataclass
class WireEffectEvent:
    """Immutable record of an external tool call observed at the transport boundary."""
    call_index: int
    tool_name: str
    target: str
    op_type: EffectOp
    arguments: Dict[str, Any]
    output: Any = None
    committed_externally: bool = False
    acknowledged_to_agent: bool = False
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_index": self.call_index,
            "tool_name": self.tool_name,
            "target": self.target,
            "op_type": self.op_type.value if hasattr(self.op_type, "value") else str(self.op_type),
            "arguments": copy.deepcopy(self.arguments),
            "output": copy.deepcopy(self.output),
            "committed_externally": self.committed_externally,
            "acknowledged_to_agent": self.acknowledged_to_agent,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class ToolProxyRegistry:
    """Registry wrapping domain tool functions with boundary interception and wire effect logging."""

    def __init__(self, injector: Optional[DeterministicFaultInjector] = None):
        self.injector = injector or DeterministicFaultInjector()
        self.effect_log: List[WireEffectEvent] = []
        self._call_counters: Dict[str, int] = {}
        self._raw_tools: Dict[str, Callable[..., Any]] = {}
        self._tool_targets: Dict[str, str] = {}
        self._tool_op_types: Dict[str, EffectOp] = {}

    def register_tool(
        self,
        name: str,
        fn: Callable[..., Any],
        target: str,
        op_type: EffectOp = EffectOp.UPDATE,
    ) -> None:
        self._raw_tools[name] = fn
        self._tool_targets[name] = target
        self._tool_op_types[name] = op_type
        self._call_counters[name] = 0

    def reset(self) -> None:
        self.effect_log.clear()
        self._call_counters = {k: 0 for k in self._raw_tools}

    def get_proxied_tool(self, name: str) -> Callable[..., Any]:
        """Wrap tool with deterministic lifecycle boundary hooks."""
        if name not in self._raw_tools:
            raise KeyError(f"Tool '{name}' not found in proxy registry")

        raw_fn = self._raw_tools[name]
        target = self._tool_targets[name]
        op_type = self._tool_op_types[name]

        def proxied_call(*args: Any, **kwargs: Any) -> Any:
            self._call_counters[name] += 1
            call_idx = self._call_counters[name]

            # 1. Boundary: PRE_MUTATION
            if self.injector.should_trigger(ExecutionBoundary.PRE_MUTATION, name, call_idx):
                event = WireEffectEvent(
                    call_index=call_idx,
                    tool_name=name,
                    target=target,
                    op_type=op_type,
                    arguments={"args": args, "kwargs": kwargs},
                    committed_externally=False,
                    acknowledged_to_agent=False,
                    error="FaultInjected:PRE_MUTATION",
                )
                self.effect_log.append(event)
                self.injector.trigger(ExecutionBoundary.PRE_MUTATION, name, {"args": args, "kwargs": kwargs})

            # 2. Boundary: DURING_MUTATION (simulated timeout/partial write before commit)
            if self.injector.should_trigger(ExecutionBoundary.DURING_MUTATION, name, call_idx):
                event = WireEffectEvent(
                    call_index=call_idx,
                    tool_name=name,
                    target=target,
                    op_type=op_type,
                    arguments={"args": args, "kwargs": kwargs},
                    committed_externally=False,
                    acknowledged_to_agent=False,
                    error="FaultInjected:DURING_MUTATION",
                )
                self.effect_log.append(event)
                self.injector.trigger(ExecutionBoundary.DURING_MUTATION, name, {"args": args, "kwargs": kwargs})

            # Boundary: DURING_COMPENSATION
            if self.injector.should_trigger(ExecutionBoundary.DURING_COMPENSATION, name, call_idx):
                event = WireEffectEvent(
                    call_index=call_idx,
                    tool_name=name,
                    target=target,
                    op_type=op_type,
                    arguments={"args": args, "kwargs": kwargs},
                    committed_externally=False,
                    acknowledged_to_agent=False,
                    error="FaultInjected:DURING_COMPENSATION",
                )
                self.effect_log.append(event)
                self.injector.trigger(ExecutionBoundary.DURING_COMPENSATION, name, {"args": args, "kwargs": kwargs})

            # Boundary: DURING_RECOVERY
            if self.injector.should_trigger(ExecutionBoundary.DURING_RECOVERY, name, call_idx):
                event = WireEffectEvent(
                    call_index=call_idx,
                    tool_name=name,
                    target=target,
                    op_type=op_type,
                    arguments={"args": args, "kwargs": kwargs},
                    committed_externally=False,
                    acknowledged_to_agent=False,
                    error="FaultInjected:DURING_RECOVERY",
                )
                self.effect_log.append(event)
                self.injector.trigger(ExecutionBoundary.DURING_RECOVERY, name, {"args": args, "kwargs": kwargs})

            # 3. External Physical Execution
            res = None
            try:
                res = raw_fn(*args, **kwargs)
            except Exception as ex:
                event = WireEffectEvent(
                    call_index=call_idx,
                    tool_name=name,
                    target=target,
                    op_type=op_type,
                    arguments={"args": args, "kwargs": kwargs},
                    committed_externally=False,
                    acknowledged_to_agent=False,
                    error=str(ex),
                )
                self.effect_log.append(event)
                raise ex

            # Mutation successfully committed on external system!
            # 4. Boundary: POST_MUTATION_PRE_ACK (The Lost-ACK Window)
            if self.injector.should_trigger(ExecutionBoundary.POST_MUTATION_PRE_ACK, name, call_idx):
                event = WireEffectEvent(
                    call_index=call_idx,
                    tool_name=name,
                    target=target,
                    op_type=op_type,
                    arguments={"args": args, "kwargs": kwargs},
                    output=res,
                    committed_externally=True,
                    acknowledged_to_agent=False,
                    error="FaultInjected:POST_MUTATION_PRE_ACK",
                )
                self.effect_log.append(event)
                # Crash / drop ACK so agent never receives 'res'
                self.injector.trigger(ExecutionBoundary.POST_MUTATION_PRE_ACK, name, {"output": res})
                return res

            # 5. Boundary: POST_ACK_PRE_CHECKPOINT
            if self.injector.should_trigger(ExecutionBoundary.POST_ACK_PRE_CHECKPOINT, name, call_idx):
                event = WireEffectEvent(
                    call_index=call_idx,
                    tool_name=name,
                    target=target,
                    op_type=op_type,
                    arguments={"args": args, "kwargs": kwargs},
                    output=res,
                    committed_externally=True,
                    acknowledged_to_agent=True,
                    error="FaultInjected:POST_ACK_PRE_CHECKPOINT",
                )
                self.effect_log.append(event)
                self.injector.trigger(ExecutionBoundary.POST_ACK_PRE_CHECKPOINT, name, {"output": res})
                return res

            # Normal clean execution path: effect committed and ACK returned
            is_mutation_replayed = False
            if isinstance(res, dict):
                if res.get("idempotent_replay") or res.get("status") == "RECONCILED_DUPLICATE_SUPPRESSED":
                    is_mutation_replayed = True

            event = WireEffectEvent(
                call_index=call_idx,
                tool_name=name,
                target=target,
                op_type=op_type,
                arguments={"args": args, "kwargs": kwargs},
                output=res,
                committed_externally=not is_mutation_replayed,
                acknowledged_to_agent=True,
            )
            self.effect_log.append(event)
            return res

        proxied_call.__wrapped__ = raw_fn
        return proxied_call
