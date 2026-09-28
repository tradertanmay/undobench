"""Base Agent interface for RecoverBench."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List
from recoverbench.schemas.task import TaskSpec


class Agent(ABC):
    """Abstract agent interface."""

    @abstractmethod
    def run_task(
        self,
        task: TaskSpec,
        tools: Dict[str, Callable[..., Any]],
    ) -> Dict[str, Any]:
        """Execute task using provided tools and return execution telemetry."""
        pass
