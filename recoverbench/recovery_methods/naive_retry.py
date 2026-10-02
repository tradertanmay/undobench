"""B0: Naive Retry recovery baseline."""

from __future__ import annotations
import logging
from typing import Any, Callable, Dict, Optional
from recoverbench.recovery_methods.base import RecoveryMethod
from recoverbench.schemas.task import TaskSpec

logger = logging.getLogger("recoverbench.recovery.naive")


class NaiveRetryMethod(RecoveryMethod):
    """B0: Blindly retries failed operations without inspecting external state."""

    name = "naive_retry"
    version = "v1"
    description = "Blindly retries failed or unacknowledged operations up to max_retries."

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.retry_count = 0

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
                    return tool_fn(*args, **kwargs)
                except Exception as ex:
                    attempts += 1
                    self.retry_count += 1
                    if attempts > self.max_retries:
                        raise ex
                    # Naive retry: immediately re-execute the same call with same arguments!
                    logger.debug(f"[NaiveRetry] Attempt {attempts} failed with {ex}; blindly retrying...")

        return wrapped

    def on_failure_detected(self, error: Exception, context: Dict[str, Any]) -> None:
        pass

    def reset(self) -> None:
        self.retry_count = 0
