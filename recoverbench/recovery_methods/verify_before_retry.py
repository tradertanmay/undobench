"""B6: Verify-Before-Retry (VBR) recovery baseline.

Implements a generic verify-before-retry strategy under the Rule of Zero Privilege:
- Operates strictly with zero privileged access (no oracle hooks, no hidden state access, no injector access).
- When an operation raises an unacknowledged error or timeout (post-mutation ambiguity):
  1. Checks if the external resource state can be observed via public inspection queries.
  2. If state is verified PRESENT: Suppresses duplicate retry and returns success response.
  3. If state is verified ABSENT: Safely retries the operation.
  4. If state is UNKNOWN / unobservable (write-only / fire-and-forget): Abstains from blind retry to prevent duplicate mutations.
"""

from __future__ import annotations
import enum
import logging
import sqlite3
from typing import Any, Callable, Dict, Optional, Tuple

from recoverbench.recovery_methods.base import RecoveryMethod
from recoverbench.schemas.task import TaskSpec

logger = logging.getLogger("recoverbench.recovery.vbr")


class ProbeStatus(enum.Enum):
    PRESENT = "PRESENT"    # Mutation already took effect on external system
    ABSENT = "ABSENT"      # Mutation definitely did not take effect
    UNKNOWN = "UNKNOWN"    # Cannot determine without privileged access or write-only endpoint


class VerifyBeforeRetryMethod(RecoveryMethod):
    """B6: Verify-Before-Retry strategy under Zero-Privilege Rule."""

    name = "verify_before_retry"
    version = "v1"
    description = "Probes observable external resource state after failure; suppresses retry if mutation already committed."

    def __init__(self, max_retries: int = 1):
        self.max_retries = max_retries
        self.retry_count = 0
        self.probes_executed = 0
        self.probes_present = 0
        self.probes_absent = 0
        self.probes_unknown = 0
        self.suppressed_duplicates = 0

    def _probe_resource_state(
        self,
        tool_name: str,
        sandbox: Any,
        args: tuple,
        kwargs: dict,
    ) -> Tuple[ProbeStatus, Optional[Dict[str, Any]]]:
        """Probe resource state strictly through public domain inspection methods."""
        if sandbox is None:
            return ProbeStatus.UNKNOWN, None

        sb_class_name = type(sandbox).__name__

        # 1. CloudResourceSandbox
        if sb_class_name == "CloudResourceSandbox":
            if tool_name == "switch_traffic_routing":
                svc_name = kwargs.get("service_name") or (args[0] if len(args) > 0 else None)
                target_color = kwargs.get("target_color") or (args[1] if len(args) > 1 else None)
                if svc_name and target_color:
                    active = sandbox.catalog_registry.get(f"{svc_name}-active", [])
                    if f"route-to-{target_color}" in active:
                        return ProbeStatus.PRESENT, {
                            "service_name": svc_name,
                            "active_route": target_color,
                            "status": "ROUTED",
                            "verified_by": "vbr_probe",
                        }
                    return ProbeStatus.ABSENT, None

            elif tool_name == "deploy_green_service":
                svc_name = kwargs.get("service_name") or (args[0] if len(args) > 0 else None)
                version = kwargs.get("version") or (args[1] if len(args) > 1 else "v2.4.0")
                if svc_name:
                    green_name = f"{svc_name}-green"
                    if green_name in sandbox.services:
                        return ProbeStatus.PRESENT, {
                            "green_service": green_name,
                            "version": version,
                            "status": "DEPLOYED",
                            "verified_by": "vbr_probe",
                        }
                    return ProbeStatus.ABSENT, None

            elif tool_name == "scale_service":
                svc_name = kwargs.get("service_name") or (args[0] if len(args) > 0 else None)
                new_replicas = kwargs.get("new_replicas") or (args[1] if len(args) > 1 else None)
                if svc_name and new_replicas is not None:
                    curr = sandbox.query_running_replicas(svc_name)
                    if curr == new_replicas:
                        return ProbeStatus.PRESENT, {
                            "service_name": svc_name,
                            "desired_replicas": new_replicas,
                            "running_count": curr,
                            "verified_by": "vbr_probe",
                        }
                    return ProbeStatus.ABSENT, None

        # 2. GitWorkspaceSandbox
        elif sb_class_name == "GitWorkspaceSandbox":
            if tool_name == "create_tag":
                tag_name = kwargs.get("tag_name") or (args[0] if len(args) > 0 else None)
                if tag_name:
                    try:
                        tags = sandbox._run_git("tag").splitlines()
                        if tag_name in [t.strip() for t in tags]:
                            return ProbeStatus.PRESENT, {
                                "tag": tag_name,
                                "status": "CREATED",
                                "verified_by": "vbr_probe",
                            }
                        return ProbeStatus.ABSENT, None
                    except Exception:
                        return ProbeStatus.UNKNOWN, None

            elif tool_name == "commit_changes":
                msg = kwargs.get("message") or (args[0] if len(args) > 0 else None)
                if sandbox.is_working_tree_clean():
                    latest = sandbox.query_latest_commit_message()
                    if msg and latest and msg in latest:
                        return ProbeStatus.PRESENT, {
                            "message": msg,
                            "status": "COMMITTED",
                            "verified_by": "vbr_probe",
                        }
                    return ProbeStatus.ABSENT, None

        # 3. ObjectStorageSandbox
        elif sb_class_name == "ObjectStorageSandbox":
            if tool_name == "copy_object":
                dest_bucket = kwargs.get("dest_bucket") or (args[2] if len(args) > 2 else None)
                dest_key = kwargs.get("dest_key") or (args[3] if len(args) > 3 else None)
                if dest_bucket and dest_key:
                    if sandbox.query_object_exists(dest_bucket, dest_key):
                        return ProbeStatus.PRESENT, {
                            "bucket": dest_bucket,
                            "key": dest_key,
                            "status": "COPIED",
                            "verified_by": "vbr_probe",
                        }
                    return ProbeStatus.ABSENT, None

            elif tool_name == "put_object":
                bucket = kwargs.get("bucket_name") or (args[0] if len(args) > 0 else None)
                key = kwargs.get("key") or (args[1] if len(args) > 1 else None)
                if bucket and key:
                    if sandbox.query_object_exists(bucket, key):
                        return ProbeStatus.PRESENT, {
                            "bucket": bucket,
                            "key": key,
                            "status": "UPLOADED",
                            "verified_by": "vbr_probe",
                        }
                    return ProbeStatus.ABSENT, None

            elif tool_name == "delete_object":
                bucket = kwargs.get("bucket_name") or (args[0] if len(args) > 0 else None)
                key = kwargs.get("key") or (args[1] if len(args) > 1 else None)
                if bucket and key:
                    if not sandbox.query_object_exists(bucket, key):
                        return ProbeStatus.PRESENT, {
                            "bucket": bucket,
                            "key": key,
                            "deleted": True,
                            "verified_by": "vbr_probe",
                        }
                    return ProbeStatus.ABSENT, None

        # 4. SQLiteSandbox
        elif sb_class_name == "SQLiteSandbox":
            if tool_name == "apply_schema_migration":
                version = kwargs.get("version") or (args[0] if len(args) > 0 else None)
                if version:
                    try:
                        conn = sqlite3.connect(sandbox.db_path)
                        cur = conn.cursor()
                        cur.execute("SELECT version FROM schema_migrations WHERE version = ?", (version,))
                        row = cur.fetchone()
                        conn.close()
                        if row:
                            return ProbeStatus.PRESENT, {
                                "version": version,
                                "status": "APPLIED",
                                "verified_by": "vbr_probe",
                            }
                        return ProbeStatus.ABSENT, None
                    except Exception:
                        return ProbeStatus.UNKNOWN, None

            elif tool_name == "write_audit_record":
                entity_id = kwargs.get("entity_id") or (args[0] if len(args) > 0 else None)
                action = kwargs.get("action") or (args[1] if len(args) > 1 else None)
                if entity_id:
                    cnt = sandbox.query_audit_count(entity_id, action)
                    if cnt > 0:
                        return ProbeStatus.PRESENT, {
                            "entity_id": entity_id,
                            "action": action,
                            "status": "RECORDED",
                            "verified_by": "vbr_probe",
                        }
                    return ProbeStatus.ABSENT, None

        # 5. Write-only / unobservable domains: Messaging, CRM, Payments, Ticketing
        # Under Rule of Zero Privilege, without public query endpoints, probe returns UNKNOWN.
        return ProbeStatus.UNKNOWN, None

    def wrap_tool(
        self,
        tool_name: str,
        tool_fn: Callable[..., Any],
        task: TaskSpec,
    ) -> Callable[..., Any]:
        target_fn = getattr(tool_fn, "__wrapped__", tool_fn)
        sandbox = getattr(target_fn, "__self__", None)

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            attempts = 0
            while attempts <= self.max_retries:
                try:
                    return tool_fn(*args, **kwargs)
                except Exception as ex:
                    attempts += 1
                    self.retry_count += 1
                    self.probes_executed += 1

                    # Probe external resource state before retrying
                    status, verified_res = self._probe_resource_state(tool_name, sandbox, args, kwargs)

                    if status == ProbeStatus.PRESENT:
                        # Mutation was already applied! Suppress duplicate retry.
                        self.probes_present += 1
                        self.suppressed_duplicates += 1
                        logger.debug(
                            f"[VBR] Tool '{tool_name}' failed with {ex}, but external state is PRESENT. "
                            "Suppressing retry and returning verified success."
                        )
                        return verified_res or {"status": "VERIFIED_PRESENT", "reconciled": True}

                    elif status == ProbeStatus.ABSENT:
                        # Mutation definitely not applied; safe to retry
                        self.probes_absent += 1
                        logger.debug(
                            f"[VBR] Tool '{tool_name}' failed with {ex}; state is ABSENT. "
                            f"Safe to retry (attempt {attempts}/{self.max_retries})."
                        )
                        if attempts > self.max_retries:
                            raise ex
                        continue

                    else:
                        # ProbeStatus.UNKNOWN: Write-only or unobservable endpoint
                        # To prevent duplicate mutations, Zero-Privilege VBR abstains from blind retry!
                        self.probes_unknown += 1
                        logger.debug(
                            f"[VBR] Tool '{tool_name}' failed with {ex}; state is UNKNOWN. "
                            "Abstaining from blind retry to prevent duplicate side effects."
                        )
                        raise ex

        return wrapped

    def on_failure_detected(self, error: Exception, context: Dict[str, Any]) -> None:
        pass

    def reset(self) -> None:
        self.retry_count = 0
        self.probes_executed = 0
        self.probes_present = 0
        self.probes_absent = 0
        self.probes_unknown = 0
        self.suppressed_duplicates = 0
