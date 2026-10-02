"""Declarative task specification schemas with Phase RB-2 metadata extensions."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation


class TaskDomain(str, Enum):
    DATABASE = "database"
    PAYMENTS = "payments"
    GIT = "git"
    TICKETING = "ticketing"
    CLOUD = "cloud"
    CRM = "crm"
    MESSAGING = "messaging"
    STORAGE = "storage"


class TaskSplit(str, Enum):
    DEV = "dev"
    VALIDATION = "validation"
    TEST = "test"


class EffectOp(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"


class TaskProvenance(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    REALISTIC_TEMPLATE = "REALISTIC_TEMPLATE"
    DERIVED_FROM_EXISTING_SYSTEM_PATTERN = "DERIVED_FROM_EXISTING_SYSTEM_PATTERN"
    ADAPTED_FROM_EVOUNDO_DEV = "ADAPTED_FROM_EVOUNDO_DEV"
    NEW_FOR_RECOVERBENCH = "NEW_FOR_RECOVERBENCH"


class TaskComplexity(str, Enum):
    C1 = "C1"  # Single effect
    C2 = "C2"  # Multi-effect single resource
    C3 = "C3"  # Multi-resource workflow
    C4 = "C4"  # Multi-resource + recovery/compensation
    C5 = "C5"  # Concurrent or ambiguous long workflow


class OutcomeObservability(str, Enum):
    KNOWN_NOT_EXECUTED = "KNOWN_NOT_EXECUTED"
    KNOWN_EXECUTED = "KNOWN_EXECUTED"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
    PARTIALLY_OBSERVED = "PARTIALLY_OBSERVED"


class EffectReversibility(str, Enum):
    REVERSIBLE = "REVERSIBLE"
    COMPENSATABLE = "COMPENSATABLE"
    IRREVERSIBLE = "IRREVERSIBLE"


class FaultScenarioSpec(BaseModel):
    """Specification of a concrete fault scenario supported by a base task."""
    scenario_id: str
    name: str
    boundary: ExecutionBoundary = ExecutionBoundary.NO_FAULT
    perturbation: Perturbation = Perturbation.NONE
    target_tool: Optional[str] = None
    target_call_index: int = 1
    observability: OutcomeObservability = OutcomeObservability.UNKNOWN_OUTCOME
    concurrent_state_delta: Optional[Dict[str, Any]] = None
    description: str = ""
    expected_recovery_behavior: Optional[str] = None
    fault_spec: Optional[FaultSpec] = None

    def model_post_init(self, __context: Any) -> None:
        if self.fault_spec is not None:
            self.boundary = self.fault_spec.boundary
            self.perturbation = self.fault_spec.perturbation
            self.target_tool = self.fault_spec.target_tool
            self.target_call_index = self.fault_spec.target_call_index
            self.concurrent_state_delta = self.fault_spec.concurrent_state_delta
        else:
            self.fault_spec = FaultSpec(
                boundary=self.boundary,
                perturbation=self.perturbation,
                target_tool=self.target_tool,
                target_call_index=self.target_call_index,
                concurrent_state_delta=self.concurrent_state_delta,
            )


class RequiredEffect(BaseModel):
    """An external mutation that must occur for the task to be successfully executed."""
    target: str
    op_type: EffectOp = EffectOp.UPDATE
    expected_value: Optional[Any] = None
    max_occurrences: int = 1
    reversibility: EffectReversibility = EffectReversibility.REVERSIBLE
    description: str = ""


class ForbiddenEffect(BaseModel):
    """An external mutation that must NEVER occur during execution or recovery."""
    target: str
    op_type: Optional[EffectOp] = None
    forbidden_value: Optional[Any] = None
    reason: str = ""


class InvariantDefinition(BaseModel):
    """A domain rule that must hold true before and after recovery."""
    name: str
    description: str
    expression: str  # Rule identifier or Python expression evaluated by Oracle


class TaskStepPlan(BaseModel):
    """Step definition for deterministic scripted agent execution."""
    tool: str
    args: Dict[str, Any]
    description: str = ""


class TaskSpec(BaseModel):
    """Declarative task specification."""
    task_id: str
    name: str
    domain: TaskDomain
    split: TaskSplit
    version: str = "0.2.0"

    objective: str
    initial_state_setup: Dict[str, Any]
    allowed_tools: List[str]

    required_effects: List[RequiredEffect]
    forbidden_effects: List[ForbiddenEffect] = Field(default_factory=list)
    invariants: List[InvariantDefinition] = Field(default_factory=list)
    acceptable_final_states: Dict[str, Any]

    # Scripted plan for deterministic baseline evaluation
    scripted_plan: List[TaskStepPlan] = Field(default_factory=list)

    # Supported fault scenarios generating BenchmarkEpisodes
    supported_fault_scenarios: List[FaultScenarioSpec] = Field(default_factory=list)

    # Stratified Metadata (Phase RB-2)
    provenance: TaskProvenance = TaskProvenance.NEW_FOR_RECOVERBENCH
    complexity: TaskComplexity = TaskComplexity.C1
    observability: OutcomeObservability = OutcomeObservability.UNKNOWN_OUTCOME
    reversibility: EffectReversibility = EffectReversibility.REVERSIBLE
    outcome_observability: Optional[OutcomeObservability] = None
    effect_reversibility: Optional[EffectReversibility] = None
    possible_compensations: List[str] = Field(default_factory=list)
    idempotency_support: bool = False
    concurrency_present: bool = False
    cross_system_transaction: bool = False

    def model_post_init(self, __context: Any) -> None:
        if self.outcome_observability is not None:
            self.observability = self.outcome_observability
        elif self.observability is not None:
            self.outcome_observability = self.observability

        if self.effect_reversibility is not None:
            self.reversibility = self.effect_reversibility
        elif self.reversibility is not None:
            self.effect_reversibility = self.reversibility

    source: str = "RecoverBench"
    author: str = "RecoverBench Team"
    created_date: str = "2026-09-22"
    evoundo_influence: bool = False


FaultScenarioSpec.model_rebuild()
TaskSpec.model_rebuild()
