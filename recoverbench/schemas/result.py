"""Evaluation result and trajectory schemas with decomposed oracle clauses, failure taxonomy, and tripartite counting."""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OracleVerdict(BaseModel):
    """Detailed verdict produced by the State & Effect History Oracle with explicit clause decomposition."""
    task_id: str
    method: str
    boundary: str
    perturbation: str
    fault_scenario_id: Optional[str] = None

    # 8 Decomposed Clauses (Phase RB-1 & RB-2 Specification)
    goal_satisfied: bool
    final_state_correct: bool
    invariant_satisfied: bool
    required_effects_satisfied: bool
    effect_multiplicity_correct: bool
    forbidden_effects_absent: bool
    ordering_correct: bool
    overall_recovery_correct: bool

    # Backwards-compatibility fields
    is_safe_and_successful: bool = True
    objective_satisfied: bool = True
    final_state_valid: bool = True
    invariants_held: bool = True
    no_forbidden_effects: bool = True
    exactly_once_satisfied: bool = True

    # Recovery Outcome Taxonomy
    primary_failure_classification: Optional[str] = None
    secondary_failure_classifications: List[str] = Field(default_factory=list)

    # Tripartite Counting (Phase RB-2)
    physical_invocation_count: int = 0      # Physical calls dispatched over the wire
    committed_mutation_count: int = 0       # External physical mutations committed
    semantic_effect_count: int = 0          # Observable business effects matching goal
    exactly_once_semantic_effect_rate: float = 1.0

    # Counts
    required_effects_count: int = 0
    matched_effects_count: int = 0
    duplicate_effects_count: int = 0
    missing_effects_count: int = 0
    forbidden_effects_count: int = 0

    violations: List[str] = Field(default_factory=list)
    observed_effects: List[Dict[str, Any]] = Field(default_factory=list)
    final_state: Dict[str, Any] = Field(default_factory=dict)

    @property
    def recovery_success(self) -> bool:
        return self.overall_recovery_correct


class BenchmarkRunResult(BaseModel):
    """Result of a single benchmark episode run under a specific recovery method and fault scenario."""
    task_id: str
    domain: str
    split: str
    method: str
    method_version: str = "v1"
    boundary: str
    perturbation: str
    fault_scenario_id: Optional[str] = None
    is_control_run: bool = False
    applicability: str = "APPLICABLE"

    success: bool
    verdict: OracleVerdict

    primary_failure_classification: Optional[str] = None
    secondary_failure_classifications: List[str] = Field(default_factory=list)

    # Tripartite Counting
    physical_invocation_count: int = 0
    committed_mutation_count: int = 0
    semantic_effect_count: int = 0
    exactly_once_semantic_effect_rate: float = 1.0

    # Cost & Telemetry
    tool_calls_count: int = 0
    recovery_attempts: int = 0
    duration_ms: float = 0.0
    tokens_used: int = 0

    timestamp: float = Field(default_factory=time.time)


class TrajectoryRecord(BaseModel):
    """Line-delimited JSONL record of an execution trajectory."""
    run_id: str
    task_id: str
    method: str
    method_version: str = "v1"
    step_index: int
    tool_name: str
    arguments: Dict[str, Any]
    output: Any
    status: str
    error: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
