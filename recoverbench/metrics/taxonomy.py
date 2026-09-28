"""Recovery Outcome Taxonomy for RecoverBench Phase RB-1.

Categorizes recovery failures into 11 actionable, structural classes rather than binary pass/fail.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RecoveryOutcomeClassification(str, Enum):
    """The 11 Recovery Outcome failure categories + SUCCESS."""
    SUCCESS = "SUCCESS"
    DUPLICATE_EFFECT = "DUPLICATE_EFFECT"
    MISSING_EFFECT = "MISSING_EFFECT"
    FORBIDDEN_EFFECT = "FORBIDDEN_EFFECT"
    STALE_AGENT_STATE = "STALE_AGENT_STATE"
    EXTERNAL_STATE_DIVERGENCE = "EXTERNAL_STATE_DIVERGENCE"
    UNSAFE_RETRY = "UNSAFE_RETRY"
    FAILED_COMPENSATION = "FAILED_COMPENSATION"
    CONCURRENT_CONFLICT_LOSS = "CONCURRENT_CONFLICT_LOSS"
    RECOVERY_ABORT = "RECOVERY_ABORT"
    TASK_FAILURE = "TASK_FAILURE"
    ORACLE_VIOLATION = "ORACLE_VIOLATION"


class RecoveryOutcomeClassifier:
    """Classifies a trial run's verdict and effect history into primary and secondary classifications."""

    @classmethod
    def classify(
        cls,
        verdict_data: Dict[str, Any],
        boundary: str,
        perturbation: str,
        agent_succeeded: bool = True,
        agent_error: Optional[str] = None,
    ) -> Tuple[str, List[str]]:
        """Determine primary and secondary classifications."""
        if verdict_data.get("overall_recovery_correct") or verdict_data.get("is_safe_and_successful"):
            return RecoveryOutcomeClassification.SUCCESS.value, []

        secondary: List[str] = []
        primary: Optional[str] = None

        # Check for compensation failure first
        if "COMPENSATION" in boundary.upper() or "RECOVERY_CRASH" in perturbation.upper():
            if not verdict_data.get("final_state_correct", True) or not verdict_data.get("goal_satisfied", True):
                primary = RecoveryOutcomeClassification.FAILED_COMPENSATION.value

        # Check for duplicate effects & unsafe retry
        dup_count = verdict_data.get("duplicate_effects_count", 0)
        if dup_count > 0:
            if boundary in ("POST_MUTATION_PRE_ACK", "DURING_MUTATION"):
                chosen_primary = RecoveryOutcomeClassification.UNSAFE_RETRY.value
                sec = RecoveryOutcomeClassification.DUPLICATE_EFFECT.value
            else:
                chosen_primary = RecoveryOutcomeClassification.DUPLICATE_EFFECT.value
                sec = RecoveryOutcomeClassification.UNSAFE_RETRY.value

            if not primary:
                primary = chosen_primary
            else:
                secondary.append(chosen_primary)
            if sec not in secondary:
                secondary.append(sec)

        # Check for forbidden effects
        if not verdict_data.get("forbidden_effects_absent", True) or verdict_data.get("forbidden_effects_count", 0) > 0:
            if not primary:
                primary = RecoveryOutcomeClassification.FORBIDDEN_EFFECT.value
            else:
                secondary.append(RecoveryOutcomeClassification.FORBIDDEN_EFFECT.value)

        # Check for missing effects
        if not verdict_data.get("required_effects_satisfied", True) or verdict_data.get("missing_effects_count", 0) > 0:
            if not primary:
                primary = RecoveryOutcomeClassification.MISSING_EFFECT.value
            else:
                secondary.append(RecoveryOutcomeClassification.MISSING_EFFECT.value)

        # Check for concurrent conflict loss
        if perturbation in ("CONCURRENT_WRITE",) or "conflict" in str(verdict_data.get("violations", [])).lower():
            if not verdict_data.get("final_state_correct", True) or not verdict_data.get("goal_satisfied", True):
                if not primary:
                    primary = RecoveryOutcomeClassification.CONCURRENT_CONFLICT_LOSS.value
                else:
                    secondary.append(RecoveryOutcomeClassification.CONCURRENT_CONFLICT_LOSS.value)

        # Check for external state divergence
        if not verdict_data.get("final_state_correct", True):
            if not primary:
                primary = RecoveryOutcomeClassification.EXTERNAL_STATE_DIVERGENCE.value
            else:
                secondary.append(RecoveryOutcomeClassification.EXTERNAL_STATE_DIVERGENCE.value)

        # Check for invariant violation
        if not verdict_data.get("invariant_satisfied", True):
            if not primary:
                primary = RecoveryOutcomeClassification.ORACLE_VIOLATION.value
            else:
                secondary.append(RecoveryOutcomeClassification.ORACLE_VIOLATION.value)

        # Check for unhandled abort / crash
        if not agent_succeeded or agent_error:
            if not primary:
                primary = RecoveryOutcomeClassification.RECOVERY_ABORT.value
            else:
                secondary.append(RecoveryOutcomeClassification.RECOVERY_ABORT.value)

        # Default fallback
        if not primary:
            primary = RecoveryOutcomeClassification.TASK_FAILURE.value

        # Deduplicate secondary and exclude primary
        secondary = [s for s in list(dict.fromkeys(secondary)) if s != primary]

        return primary, secondary
