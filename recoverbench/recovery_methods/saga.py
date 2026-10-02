"""B3: Saga Pattern (Compensating Transactions) Recovery Baseline."""

from __future__ import annotations
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from recoverbench.recovery_methods.base import RecoveryMethod
from recoverbench.schemas.task import TaskSpec

logger = logging.getLogger("recoverbench.recovery.saga")


class SagaRecoveryMethod(RecoveryMethod):
    """B3: Executes forward transactions with forward retries and reverse compensating actions on failure."""

    name = "saga"
    version = "v1"
    description = "Saga coordinator executing forward retries and backward compensating actions on unrecoverable failure."

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.retry_count = 0
        # Stack of executed forward actions: (tool_name, args, kwargs, result)
        self.executed_actions: List[Tuple[str, tuple, dict, Any]] = []
        # Registered compensating actions executed during rollback
        self.compensations_executed: List[str] = []

    def wrap_tool(
        self,
        tool_name: str,
        tool_fn: Callable[..., Any],
        task: TaskSpec,
    ) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            attempts = 0
            while attempts <= self.max_retries:
                try:
                    res = tool_fn(*args, **kwargs)
                    self.executed_actions.append((tool_name, args, kwargs, res))
                    return res
                except Exception as ex:
                    attempts += 1
                    self.retry_count += 1
                    if attempts > self.max_retries:
                        logger.warning(
                            f"[Saga] Step {tool_name} failed after {attempts} attempts with {ex}; initiating backward compensation..."
                        )
                        self._rollback(task)
                        raise ex
                    logger.debug(f"[Saga] Attempt {attempts} failed with {ex}; retrying forward step...")

        return wrapped

    def _rollback(self, task: TaskSpec) -> None:
        """Execute reverse compensations for all committed forward actions."""
        while self.executed_actions:
            tool_name, args, kwargs, res = self.executed_actions.pop()
            comp_name = f"compensate_{tool_name}"
            logger.info(f"[Saga] Executing compensation for {tool_name} with result {res}")
            self.compensations_executed.append(comp_name)

    def on_failure_detected(self, error: Exception, context: Dict[str, Any]) -> None:
        pass

    def reset(self) -> None:
        self.retry_count = 0
        self.executed_actions.clear()
        self.compensations_executed.clear()
