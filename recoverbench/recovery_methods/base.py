"""Base recovery method interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
from recoverbench.schemas.task import TaskSpec


class RecoveryMethod(ABC):
    """Abstract interface for all recovery methods under benchmark evaluation."""

    name: str
    version: str = "v1"
    description: str

    @property
    def identifier(self) -> str:
        return f"{self.name}:{self.version}"

    @abstractmethod
    def wrap_tool(
        self,
        tool_name: str,
        tool_fn: Callable[..., Any],
        task: TaskSpec,
    ) -> Callable[..., Any]:
        """Wrap or intercept a tool callable to attach recovery capabilities."""
        pass

    @abstractmethod
    def on_failure_detected(self, error: Exception, context: Dict[str, Any]) -> None:
        """Invoked when an execution error or injected fault occurs."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal buffers, journals, or caches between runs."""
        pass
