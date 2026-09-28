"""State & Effect History Oracle for RecoverBench Phase RB-1.

Implements rigorous evaluation against external physical ground truth and wire effect history,
decomposed into 8 explicit clauses with structured taxonomy classification.
"""

from __future__ import annotations
import copy
from typing import Any, Dict, List, Optional
from recoverbench.faults.proxy import ToolProxyRegistry, WireEffectEvent
from recoverbench.metrics.taxonomy import RecoveryOutcomeClassifier
from recoverbench.oracle.invariants import INVARIANT_REGISTRY
from recoverbench.schemas.result import OracleVerdict
from recoverbench.schemas.task import EffectOp, TaskSpec


class StateOracle:
    """Evaluates task execution against external physical ground truth and wire effect history."""

    @classmethod
    def _resolve_nested_key(cls, curr: Any, remaining_path: str) -> tuple[bool, Any]:
        """Resolves nested keys within nested dictionaries, correctly handling keys containing dots."""
        if not remaining_path:
            return True, curr
        if not isinstance(curr, dict):
            return False, None
        if remaining_path in curr:
            return True, curr[remaining_path]
        parts = remaining_path.split(".")
        for i in range(len(parts), 0, -1):
            prefix = ".".join(parts[:i])
            if prefix in curr:
                suffix = ".".join(parts[i:])
                found, res = cls._resolve_nested_key(curr[prefix], suffix)
                if found:
                    return True, res
        return False, None

    @classmethod
    def evaluate(
        cls,
        task: TaskSpec,
        sandbox: Any,
        proxy_registry: ToolProxyRegistry,
        method_name: str,
        boundary_name: str,
        perturbation_name: str,
        agent_succeeded: bool = True,
        agent_error: Optional[str] = None,
    ) -> OracleVerdict:
        violations: List[str] = []
        effect_log = proxy_registry.effect_log
        observed_effects = [e.to_dict() for e in effect_log]

        # -------------------------------------------------------------
        # 1. Goal / Agent Success Check
        # -------------------------------------------------------------
        goal_satisfied = agent_succeeded and agent_error is None
        if not goal_satisfied:
            violations.append(f"Agent execution terminated with error: {agent_error}")

        # -------------------------------------------------------------
        # 2. Effect History Validation (Required & Forbidden Effects)
        # -------------------------------------------------------------
        required_effects_satisfied = True
        effect_multiplicity_correct = True
        matched_effects_count = 0
        duplicate_effects_count = 0
        missing_effects_count = 0
        exactly_once_satisfied = True

        for req in task.required_effects:
            matching_events = [
                e for e in proxy_registry.effect_log
                if e.target == req.target and (req.op_type is None or e.op_type == req.op_type) and e.committed_externally
            ]
            count = len(matching_events)
            if count == 0:
                required_effects_satisfied = False
                missing_effects_count += 1
                violations.append(f"Missing required effect on target '{req.target}' ({req.description})")
                exactly_once_satisfied = False
            elif count > req.max_occurrences:
                effect_multiplicity_correct = False
                duplicate_effects_count += (count - req.max_occurrences)
                violations.append(
                    f"Duplicate effect violation on '{req.target}': committed {count} times (max allowed: {req.max_occurrences})"
                )
                exactly_once_satisfied = False
            else:
                matched_effects_count += 1

        forbidden_effects_absent = True
        forbidden_effects_count = 0

        for forb in task.forbidden_effects:
            matching_events = [
                e for e in proxy_registry.effect_log
                if e.target == forb.target and (forb.op_type is None or e.op_type == forb.op_type) and e.committed_externally
            ]
            req_match = next((r for r in task.required_effects if r.target == forb.target), None)

            if req_match:
                if forb.forbidden_value is not None:
                    val_matches = [e for e in matching_events if e.output == forb.forbidden_value]
                    if val_matches:
                        forbidden_effects_count += len(val_matches)
                        forbidden_effects_absent = False
                        violations.append(
                            f"Forbidden value occurred on '{forb.target}': ({forb.reason})"
                        )
                elif len(matching_events) > req_match.max_occurrences:
                    excess = len(matching_events) - req_match.max_occurrences
                    forbidden_effects_count += excess
                    forbidden_effects_absent = False
                    violations.append(
                        f"Forbidden duplicate occurred on '{forb.target}': committed {len(matching_events)} times (max allowed: {req_match.max_occurrences}) ({forb.reason})"
                    )
            else:
                if matching_events:
                    forbidden_effects_count += len(matching_events)
                    forbidden_effects_absent = False
                    violations.append(
                        f"Forbidden effect occurred on '{forb.target}': committed {len(matching_events)} times ({forb.reason})"
                    )

        # -------------------------------------------------------------
        # 3. Final External State Assertion
        # -------------------------------------------------------------
        final_state_correct = True
        actual_state: Dict[str, Any] = {}

        if hasattr(sandbox, "get_full_state"):
            actual_state = sandbox.get_full_state()

        for state_key, expected_val in task.acceptable_final_states.items():
            val = None
            found, resolved_val = cls._resolve_nested_key(actual_state, state_key)
            if found:
                val = resolved_val
            elif hasattr(sandbox, f"query_{state_key}"):
                method = getattr(sandbox, f"query_{state_key}")
                try:
                    val = method()
                except TypeError:
                    val = None

            if val != expected_val:
                # Handle float rounding
                if isinstance(val, (int, float)) and isinstance(expected_val, (int, float)):
                    if abs(val - expected_val) > 1e-4:
                        final_state_correct = False
                        violations.append(
                            f"State mismatch on '{state_key}': expected {expected_val}, found {val}"
                        )
                else:
                    final_state_correct = False
                    violations.append(
                        f"State mismatch on '{state_key}': expected {expected_val}, found {val}"
                    )

        # -------------------------------------------------------------
        # 4. Invariant Verification
        # -------------------------------------------------------------
        invariant_satisfied = True
        for inv in task.invariants:
            checker = INVARIANT_REGISTRY.get(inv.expression)
            if checker:
                ok, msg = checker(sandbox)
                if not ok:
                    invariant_satisfied = False
                    violations.append(f"Invariant '{inv.name}' violated: {msg}")

        # -------------------------------------------------------------
        # 5. Ordering Verification
        # -------------------------------------------------------------
        ordering_correct = True
        if len(task.required_effects) > 1:
            first_seen_indices = []
            for req in task.required_effects:
                matching = [e.call_index for e in effect_log if e.target == req.target and e.committed_externally]
                first_seen_indices.append(min(matching) if matching else float("inf"))

            for i in range(len(first_seen_indices) - 1):
                if first_seen_indices[i] > first_seen_indices[i + 1] and first_seen_indices[i + 1] != float("inf"):
                    ordering_correct = False
                    violations.append(
                        f"Effect ordering violation: target '{task.required_effects[i+1].target}' committed before '{task.required_effects[i].target}'"
                    )

        # -------------------------------------------------------------
        # 6. Decomposed Clauses & Overall Recovery Verdict
        # -------------------------------------------------------------
        required_effects_satisfied = (missing_effects_count == 0)
        effect_multiplicity_correct = (duplicate_effects_count == 0 and exactly_once_satisfied)
        goal_satisfied = (final_state_correct and required_effects_satisfied)

        overall_recovery_correct = (
            goal_satisfied
            and final_state_correct
            and invariant_satisfied
            and required_effects_satisfied
            and effect_multiplicity_correct
            and forbidden_effects_absent
            and ordering_correct
        )

        # -------------------------------------------------------------
        # 7. Recovery Outcome Taxonomy Classification
        # -------------------------------------------------------------
        classification_data = {
            "overall_recovery_correct": overall_recovery_correct,
            "final_state_correct": final_state_correct,
            "goal_satisfied": goal_satisfied,
            "duplicate_effects_count": duplicate_effects_count,
            "missing_effects_count": missing_effects_count,
            "forbidden_effects_count": forbidden_effects_count,
            "forbidden_effects_absent": forbidden_effects_absent,
            "invariant_satisfied": invariant_satisfied,
            "ordering_correct": ordering_correct,
        }
        primary_classification, secondary_classifications = RecoveryOutcomeClassifier.classify(
            verdict_data=classification_data,
            boundary=boundary_name,
            perturbation=perturbation_name,
            agent_succeeded=agent_succeeded,
            agent_error=agent_error,
        )

        return OracleVerdict(
            task_id=task.task_id,
            method=method_name,
            boundary=boundary_name,
            perturbation=perturbation_name,
            # 8 Decomposed Clauses
            goal_satisfied=goal_satisfied,
            final_state_correct=final_state_correct,
            invariant_satisfied=invariant_satisfied,
            required_effects_satisfied=required_effects_satisfied,
            effect_multiplicity_correct=effect_multiplicity_correct,
            forbidden_effects_absent=forbidden_effects_absent,
            ordering_correct=ordering_correct,
            overall_recovery_correct=overall_recovery_correct,
            # Compatibility aliases
            is_safe_and_successful=overall_recovery_correct,
            objective_satisfied=goal_satisfied,
            final_state_valid=final_state_correct,
            invariants_held=invariant_satisfied,
            no_forbidden_effects=forbidden_effects_absent,
            exactly_once_satisfied=effect_multiplicity_correct,
            # Classification
            primary_failure_classification=primary_classification,
            secondary_failure_classifications=secondary_classifications,
            # Counts & Audit
            required_effects_count=len(task.required_effects),
            matched_effects_count=matched_effects_count,
            duplicate_effects_count=duplicate_effects_count,
            missing_effects_count=missing_effects_count,
            forbidden_effects_count=forbidden_effects_count,
            violations=violations,
            observed_effects=[e.to_dict() for e in effect_log],
            final_state=actual_state,
        )
