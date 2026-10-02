"""Method Applicability Registry for RecoverBench Phase RB-1.

Categorizes the structural applicability of each baseline recovery method across tasks and fault modes:
- APPLICABLE: The method was designed to handle this fault mode and task domain.
- PARTIALLY_APPLICABLE: The method applies only under specific assumptions (e.g. downstream idempotency support, observable read probes).
- NOT_APPLICABLE: The method structurally does not apply (e.g. local snapshot/restore on non-reversible external bank wires).
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Tuple
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec
from recoverbench.schemas.task import TaskDomain, TaskSpec


class Applicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    PARTIALLY_APPLICABLE = "PARTIALLY_APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ApplicabilityRegistry:
    """Evaluates whether a recovery baseline is applicable to a specific task and fault mode."""

    @classmethod
    def get_applicability(
        cls,
        method_name: str,
        task_id: str,
        domain: TaskDomain,
        boundary: ExecutionBoundary,
    ) -> Applicability:
        # Under failure-free control, all capable baselines are applicable
        if boundary == ExecutionBoundary.NO_FAULT:
            return Applicability.APPLICABLE

        normalized_method = method_name.lower()

        # B0: Naive Retry
        if "naive" in normalized_method:
            # Clean failure before mutation (e.g. timeout during network call before write) is retry-safe
            if boundary in (ExecutionBoundary.PRE_MUTATION, ExecutionBoundary.DURING_MUTATION):
                return Applicability.APPLICABLE
            # Lost-ACK after mutation on non-idempotent side effects is structurally unsafe
            return Applicability.NOT_APPLICABLE

        # B1: Checkpoint / Local Restore
        if "checkpoint" in normalized_method:
            # Checkpoint/snapshot rollback applies only to reversible local state (SQLite, local Git)
            if domain in (TaskDomain.DATABASE, TaskDomain.GIT):
                return Applicability.APPLICABLE
            # Cannot snapshot external webhooks, payment gateways, or cloud providers
            return Applicability.NOT_APPLICABLE

        # B2: Idempotency Key
        if "idempotency" in normalized_method:
            # Native idempotency key supported by API (Payments, CRM, Ticketing)
            if domain in (TaskDomain.PAYMENTS, TaskDomain.CRM, TaskDomain.TICKETING):
                return Applicability.APPLICABLE
            # Raw SQL updates or Git commits without unique key constraints
            if domain in (TaskDomain.DATABASE, TaskDomain.GIT, TaskDomain.CLOUD):
                return Applicability.NOT_APPLICABLE
            return Applicability.PARTIALLY_APPLICABLE

        # B3: Saga Pattern (Compensating Transactions)
        if "saga" in normalized_method:
            if domain in (TaskDomain.MESSAGING,):
                return Applicability.NOT_APPLICABLE
            if boundary == ExecutionBoundary.DURING_COMPENSATION:
                return Applicability.PARTIALLY_APPLICABLE
            if domain in (TaskDomain.DATABASE, TaskDomain.PAYMENTS, TaskDomain.STORAGE, TaskDomain.GIT, TaskDomain.CLOUD):
                return Applicability.APPLICABLE
            return Applicability.PARTIALLY_APPLICABLE

        # B4: LangGraph-Native
        if "langgraph" in normalized_method:
            if boundary in (ExecutionBoundary.PRE_MUTATION, ExecutionBoundary.DURING_MUTATION):
                return Applicability.APPLICABLE
            if domain in (TaskDomain.PAYMENTS, TaskDomain.CRM) and boundary == ExecutionBoundary.POST_MUTATION_PRE_ACK:
                return Applicability.PARTIALLY_APPLICABLE
            return Applicability.NOT_APPLICABLE

        # B5: EvoUndo Reconciler
        if "evoundo" in normalized_method:
            # Observable domains with explicit state representations
            if domain in (TaskDomain.DATABASE, TaskDomain.PAYMENTS, TaskDomain.GIT):
                return Applicability.APPLICABLE
            # Complex distributed compensation crashes or unprobed systems
            if boundary == ExecutionBoundary.DURING_COMPENSATION:
                return Applicability.PARTIALLY_APPLICABLE
            return Applicability.PARTIALLY_APPLICABLE

        return Applicability.PARTIALLY_APPLICABLE
