"""B2: Idempotency-Key Strategy recovery baseline."""

from __future__ import annotations
import hashlib
import inspect
import json
import logging
from typing import Any, Callable, Dict, Optional
from recoverbench.recovery_methods.base import RecoveryMethod
from recoverbench.schemas.task import TaskSpec

logger = logging.getLogger("recoverbench.recovery.idempotency")


class IdempotencyKeyMethod(RecoveryMethod):
    """B2: Attaches deterministic idempotency keys to mutating operations and retries safely."""

    name = "idempotency"
    version = "v1"
    description = "Computes deterministic idempotency keys and forwards them to supporting tools."

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.generated_keys: Dict[str, str] = {}
        self.retry_count = 0

    def _compute_key(self, task_id: str, tool_name: str, args: tuple, kwargs: dict) -> str:
        # Filter internal kwargs
        clean_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("__") and k != "idempotency_key"}
        raw = f"{task_id}:{tool_name}:{str(args)}:{json.dumps(clean_kwargs, sort_keys=True, default=str)}"
        return "idem_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def wrap_tool(
        self,
        tool_name: str,
        tool_fn: Callable[..., Any],
        task: TaskSpec,
    ) -> Callable[..., Any]:
        target_fn = getattr(tool_fn, "__wrapped__", tool_fn)
        sig = inspect.signature(target_fn)
        accepts_idem = "idempotency_key" in sig.parameters

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            key = self._compute_key(task.task_id, tool_name, args, kwargs)
            self.generated_keys[tool_name] = key

            # Pass key if tool function accepts it
            call_kwargs = kwargs.copy()
            if accepts_idem and "idempotency_key" not in call_kwargs:
                call_kwargs["idempotency_key"] = key

            attempts = 0
            while attempts <= self.max_retries:
                try:
                    try:
                        return tool_fn(*args, **call_kwargs)
                    except TypeError as te:
                        if "unexpected keyword argument 'idempotency_key'" in str(te):
                            return tool_fn(*args, **kwargs)
                        raise te
                except Exception as ex:
                    attempts += 1
                    self.retry_count += 1
                    if attempts > self.max_retries:
                        raise ex
                    logger.debug(f"[Idempotency] Attempt {attempts} failed with {ex}; retrying with key {key}...")

        return wrapped

    def on_failure_detected(self, error: Exception, context: Dict[str, Any]) -> None:
        pass

    def reset(self) -> None:
        self.generated_keys.clear()
        self.retry_count = 0
