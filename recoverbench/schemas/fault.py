"""Two-dimensional fault specification schemas."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class ExecutionBoundary(str, Enum):
    """Lifecycle boundaries where faults can be injected."""
    NO_FAULT = "NO_FAULT"
    PRE_MUTATION = "PRE_MUTATION"
    DURING_MUTATION = "DURING_MUTATION"
    POST_MUTATION_PRE_ACK = "POST_MUTATION_PRE_ACK"
    POST_ACK_PRE_CHECKPOINT = "POST_ACK_PRE_CHECKPOINT"
    DURING_COMPENSATION = "DURING_COMPENSATION"
    DURING_RECOVERY = "DURING_RECOVERY"

    # Backward-compatibility aliases for legacy internal references
    PRE_INVOCATION = "PRE_MUTATION"
    DURING_INVOCATION = "DURING_MUTATION"
    POST_ACK = "POST_ACK_PRE_CHECKPOINT"


class Perturbation(str, Enum):
    """Physical perturbations injected at an execution boundary."""
    NONE = "NONE"
    WORKER_CRASH = "WORKER_CRASH"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    ACK_LOSS = "ACK_LOSS"
    PARTIAL_WRITE = "PARTIAL_WRITE"
    DUPLICATE_DELIVERY = "DUPLICATE_DELIVERY"
    CONCURRENT_WRITE = "CONCURRENT_WRITE"
    RECOVERY_CRASH = "RECOVERY_CRASH"


class FaultSpec(BaseModel):
    """Strongly-typed 2D fault specification."""
    boundary: ExecutionBoundary = ExecutionBoundary.NO_FAULT
    perturbation: Perturbation = Perturbation.NONE
    target_tool: Optional[str] = None
    target_call_index: int = 1
    injected_count: int = 1
    concurrent_state_delta: Optional[Dict[str, Any]] = None

    @field_validator("boundary", mode="before")
    @classmethod
    def resolve_boundary_aliases(cls, v: Any) -> Any:
        """Resolve legacy internal enum aliases to canonical scientific names."""
        aliases = {
            "PRE_INVOCATION": ExecutionBoundary.PRE_MUTATION,
            "DURING_INVOCATION": ExecutionBoundary.DURING_MUTATION,
            "POST_ACK": ExecutionBoundary.POST_ACK_PRE_CHECKPOINT,
        }
        if isinstance(v, str) and v in aliases:
            return aliases[v]
        return v

    @classmethod
    def from_alias(cls, alias: str, target_tool: Optional[str] = None) -> "FaultSpec":
        """Convert canonical F0-F6 aliases to 2D FaultSpec."""
        mapping = {
            "F0": (ExecutionBoundary.PRE_MUTATION, Perturbation.WORKER_CRASH),
            "F1": (ExecutionBoundary.DURING_MUTATION, Perturbation.NETWORK_TIMEOUT),
            "F2": (ExecutionBoundary.POST_MUTATION_PRE_ACK, Perturbation.ACK_LOSS),
            "F3": (ExecutionBoundary.POST_ACK_PRE_CHECKPOINT, Perturbation.WORKER_CRASH),
            "F4": (ExecutionBoundary.DURING_COMPENSATION, Perturbation.RECOVERY_CRASH),
            "F5": (ExecutionBoundary.DURING_RECOVERY, Perturbation.CONCURRENT_WRITE),
            "F6": (ExecutionBoundary.PRE_MUTATION, Perturbation.DUPLICATE_DELIVERY),
            "NO_FAULT": (ExecutionBoundary.NO_FAULT, Perturbation.NONE),
        }
        b, p = mapping.get(alias.upper(), (ExecutionBoundary.NO_FAULT, Perturbation.NONE))
        return cls(boundary=b, perturbation=p, target_tool=target_tool)

    @property
    def is_active(self) -> bool:
        return self.boundary != ExecutionBoundary.NO_FAULT and self.perturbation != Perturbation.NONE
