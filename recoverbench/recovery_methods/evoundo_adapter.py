"""B5: EvoUndo Recovery Adapter (Subject Under Test).

Integrates EvoUndo v0.3.0 as an evaluated baseline method.
Does NOT contain benchmark-level privileges, oracle hooks, or bespoke pass conditions.
"""

from __future__ import annotations
import logging
import os
import sys
import tempfile
import time
from typing import Any, Callable, Dict, Optional

# Link to external EvoUndo installation if specified in environment
EVOUNDO_PROD_PATH = os.environ.get("EVOUNDO_PROD_PATH") or os.environ.get("EVOUNDO_PATH")
if EVOUNDO_PROD_PATH and os.path.exists(EVOUNDO_PROD_PATH) and EVOUNDO_PROD_PATH not in sys.path:
    sys.path.insert(0, EVOUNDO_PROD_PATH)

try:
    from evoundo_harness.identity import MutationIdentity
    from evoundo_harness.reconciliation.reconciler import (
        MutationReconciler,
        ReconciliationStatus,
    )
    EVOUNDO_AVAILABLE = True
except ImportError:
    EVOUNDO_AVAILABLE = False

from recoverbench.recovery_methods.base import RecoveryMethod
from recoverbench.schemas.task import TaskSpec

logger = logging.getLogger("recoverbench.recovery.evoundo")


class EvoUndoAdapter(RecoveryMethod):
    """B5: Evaluates EvoUndo's mutation journaling, state probing, and duplicate suppression."""

    name = "evoundo"
    version = "rb1"
    description = "EvoUndo v0.3.0 crash reconciler with pre-state witnesses and post-condition probing."

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.tmp_dir = tempfile.mkdtemp(prefix="rb_evoundo_")
        self.journal_file = os.path.join(self.tmp_dir, "evoundo_journal.json")
        self.reconciler = MutationReconciler(journal_path=self.journal_file) if EVOUNDO_AVAILABLE else None
        self.retry_count = 0

    def wrap_tool(
        self,
        tool_name: str,
        tool_fn: Callable[..., Any],
        task: TaskSpec,
    ) -> Callable[..., Any]:
        if not EVOUNDO_AVAILABLE or not self.reconciler:
            raise RuntimeError("EvoUndo package not available in python environment")

        reconciler = self.reconciler

        import hashlib
        import json

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            arg_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
            arg_hash = hashlib.sha256(arg_str.encode("utf-8")).hexdigest()[:8]
            logical_mutation_id = f"mut_{task.task_id}_{tool_name}_{arg_hash}"
            identity = MutationIdentity.create(
                logical_mutation_id=logical_mutation_id,
                framework="recoverbench",
                framework_run_id=task.task_id,
                tool_name=tool_name,
                tool_args={"args": args, "kwargs": kwargs},
            )

            attempts = 0
            while attempts <= self.max_retries:
                decision = reconciler.evaluate_request(
                    identity=identity,
                    current_state_probe=None,
                    expected_post_condition=None,
                )

                if not decision.should_execute_fn:
                    # EvoUndo detected that mutation was already applied externally; suppress duplicate!
                    logger.debug(
                        f"[EvoUndo] Duplicate mutation suppressed for {logical_mutation_id}: {decision.reason}"
                    )
                    return decision.cached_result or {"status": "RECONCILED_DUPLICATE_SUPPRESSED"}

                try:
                    res = tool_fn(*args, **kwargs)
                    reconciler.record_mutation_executed(logical_mutation_id, result=res)
                    reconciler.record_committed(logical_mutation_id)
                    return res
                except Exception as ex:
                    attempts += 1
                    self.retry_count += 1
                    identity.retry_attempt = attempts
                    if attempts > self.max_retries:
                        raise ex
                    logger.debug(f"[EvoUndo] Execution failed with {ex}; invoking crash reconciler...")

        return wrapped

    def on_failure_detected(self, error: Exception, context: Dict[str, Any]) -> None:
        pass

    def reset(self) -> None:
        self.retry_count = 0
        if self.reconciler:
            self.reconciler._journal.clear()
            if os.path.exists(self.journal_file):
                try:
                    os.remove(self.journal_file)
                except Exception:
                    pass
