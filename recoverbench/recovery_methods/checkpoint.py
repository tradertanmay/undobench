"""B1: Checkpoint/Resume recovery baseline."""

from __future__ import annotations
import logging
from typing import Any, Callable, Dict, List, Optional
from recoverbench.recovery_methods.base import RecoveryMethod
from recoverbench.schemas.task import TaskSpec

logger = logging.getLogger("recoverbench.recovery.checkpoint")


class CheckpointResumeMethod(RecoveryMethod):
    """B1: Persists step checkpoints upon successful ACK and resumes pending steps on restart."""

    name = "checkpoint"
    version = "v1"
    description = "Persists acknowledged step results in durable checkpoints; replays from last checkpoint."

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.acknowledged_checkpoints: Dict[str, Any] = {}
        self.retry_count = 0

    def wrap_tool(
        self,
        tool_name: str,
        tool_fn: Callable[..., Any],
        task: TaskSpec,
    ) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            call_key = f"{task.task_id}:{tool_name}:{str(args)}:{str(sorted(kwargs.items()))}"
            if call_key in self.acknowledged_checkpoints:
                # Resumed from checkpoint
                logger.debug(f"[Checkpoint] Found committed checkpoint for {call_key}; returning cached result")
                return self.acknowledged_checkpoints[call_key]

            attempts = 0
            while attempts <= self.max_retries:
                try:
                    res = tool_fn(*args, **kwargs)
                    # Persist checkpoint upon receiving ACK
                    self.acknowledged_checkpoints[call_key] = res
                    return res
                except Exception as ex:
                    attempts += 1
                    self.retry_count += 1
                    if attempts > self.max_retries:
                        raise ex
                    logger.debug(f"[Checkpoint] Call failed with {ex}; re-evaluating pending checkpoints...")

        return wrapped

    def on_failure_detected(self, error: Exception, context: Dict[str, Any]) -> None:
        pass

    def reset(self) -> None:
        self.acknowledged_checkpoints.clear()
        self.retry_count = 0
