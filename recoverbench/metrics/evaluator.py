"""Metrics and evaluation aggregator for RecoverBench Phase RB-1.

Calculates standard benchmark recovery metrics:
- TSR (Task Success Rate)
- RSR (Recovery Success Rate)
- Recovery Delta (RSR - Control)
- EOR (Exactly-Once Effect Rate)
- DER (Duplicate Effect Rate)
- MER (Missing Effect Rate)
- Invariant Pass Rate
- Dual Reporting: Benchmark-Wide vs Applicable-Tasks-Only
- Recovery Outcome Taxonomy Distribution
"""

from __future__ import annotations
from typing import Any, Dict, List
from recoverbench.schemas.result import BenchmarkRunResult


class BenchmarkEvaluator:
    """Aggregates and computes formal recovery metrics across benchmark execution runs."""

    @classmethod
    def _compute_method_metrics(cls, runs: List[BenchmarkRunResult]) -> Dict[str, Any]:
        control_runs = [r for r in runs if r.is_control_run]
        fault_runs = [r for r in runs if not r.is_control_run]

        control_count = len(control_runs)
        control_success_count = sum(1 for r in control_runs if r.success)
        control_success_rate = (control_success_count / control_count) if control_count > 0 else 1.0

        fault_count = len(fault_runs)
        fault_success_count = sum(1 for r in fault_runs if r.success)
        recovery_success_rate = (fault_success_count / fault_count) if fault_count > 0 else 0.0

        recovery_delta = recovery_success_rate - control_success_rate

        total_required_effects = sum(r.verdict.required_effects_count for r in fault_runs)
        total_matched_effects = sum(r.verdict.matched_effects_count for r in fault_runs)
        total_duplicates = sum(r.verdict.duplicate_effects_count for r in fault_runs)
        total_missing = sum(r.verdict.missing_effects_count for r in fault_runs)
        total_forbidden = sum(r.verdict.forbidden_effects_count for r in fault_runs)

        total_mutations_observed = sum(
            len(r.verdict.observed_effects) for r in fault_runs
        )

        eor = (total_matched_effects / total_required_effects) if total_required_effects > 0 else 1.0
        der = (total_duplicates / total_mutations_observed) if total_mutations_observed > 0 else 0.0
        mer = (total_missing / total_required_effects) if total_required_effects > 0 else 0.0

        invariants_pass_count = sum(1 for r in fault_runs if r.verdict.invariant_satisfied)
        invariants_rate = (invariants_pass_count / fault_count) if fault_count > 0 else 1.0

        avg_tool_calls = sum(r.tool_calls_count for r in fault_runs) / fault_count if fault_count > 0 else 0.0
        avg_duration_ms = sum(r.duration_ms for r in fault_runs) / fault_count if fault_count > 0 else 0.0

        # Taxonomy breakdown
        taxonomy_counts: Dict[str, int] = {}
        for r in fault_runs:
            cat = r.primary_failure_classification or "UNKNOWN"
            taxonomy_counts[cat] = taxonomy_counts.get(cat, 0) + 1

        # Tripartite Counting (Phase RB-2)
        total_physical_invocations = sum(r.verdict.physical_invocation_count for r in fault_runs)
        total_committed_mutations = sum(r.verdict.committed_mutation_count for r in fault_runs)
        total_semantic_effects = sum(r.verdict.semantic_effect_count for r in fault_runs)

        return {
            "total_runs": len(runs),
            "control_runs": control_count,
            "fault_runs": fault_count,
            "control_success_rate": round(control_success_rate, 4),
            "recovery_success_rate": round(recovery_success_rate, 4),
            "recovery_delta": round(recovery_delta, 4),
            "exactly_once_effect_rate": round(eor, 4),
            "exactly_once_semantic_effect_rate": round(eor, 4),
            "duplicate_effect_rate": round(der, 4),
            "missing_effect_rate": round(mer, 4),
            "invariants_rate": round(invariants_rate, 4),
            "total_forbidden_effects": total_forbidden,
            "physical_invocation_count": total_physical_invocations,
            "committed_mutation_count": total_committed_mutations,
            "semantic_effect_count": total_semantic_effects,
            "avg_tool_calls": round(avg_tool_calls, 2),
            "avg_duration_ms": round(avg_duration_ms, 2),
            "failure_taxonomy": taxonomy_counts,
        }

    @classmethod
    def evaluate_runs(cls, runs: List[BenchmarkRunResult]) -> Dict[str, Any]:
        total_runs = len(runs)
        if total_runs == 0:
            return {"total_runs": 0}

        # Partition by method
        by_method: Dict[str, List[BenchmarkRunResult]] = {}
        for r in runs:
            by_method.setdefault(r.method, []).append(r)

        all_summaries: Dict[str, Any] = {}
        applicable_summaries: Dict[str, Any] = {}

        for method_name, method_runs in by_method.items():
            # 1. Benchmark-Wide (All Tasks)
            all_summaries[method_name] = cls._compute_method_metrics(method_runs)
            all_summaries[method_name]["method"] = method_name

            # 2. Applicable Tasks Only
            app_runs = [r for r in method_runs if r.applicability in ("APPLICABLE", "PARTIALLY_APPLICABLE")]
            applicable_summaries[method_name] = cls._compute_method_metrics(app_runs)
            applicable_summaries[method_name]["method"] = method_name

        return {
            "total_runs": total_runs,
            "methods_evaluated": list(by_method.keys()),
            "summaries": all_summaries,
            "applicable_summaries": applicable_summaries,
            "raw_results": [r.model_dump() for r in runs],
        }

    @classmethod
    def format_terminal_report(cls, summary: Dict[str, Any]) -> str:
        """Format a comprehensive human-readable report."""
        lines = [
            "\n" + "=" * 100,
            "                          RECOVERBENCH EVALUATION REPORT                                ",
            "=" * 100,
            "\n--- [1] BENCHMARK-WIDE METRICS (ALL TASKS) ---",
            f"{'Recovery Method':<18} | {'Control':<8} | {'RSR':<8} | {'Delta':<7} | {'EOR':<8} | {'DER':<8} | {'MER':<8} | {'Invariants':<10}",
            "-" * 100,
        ]

        for method_name, s in summary.get("summaries", {}).items():
            ctrl = f"{s['control_success_rate']*100:.1f}%"
            rsr = f"{s['recovery_success_rate']*100:.1f}%"
            delta = f"{s['recovery_delta']:+.2f}"
            eor = f"{s['exactly_once_effect_rate']*100:.1f}%"
            der = f"{s['duplicate_effect_rate']*100:.1f}%"
            mer = f"{s['missing_effect_rate']*100:.1f}%"
            inv = f"{s['invariants_rate']*100:.1f}%"

            lines.append(
                f"{method_name:<18} | {ctrl:<8} | {rsr:<8} | {delta:<7} | {eor:<8} | {der:<8} | {mer:<8} | {inv:<10}"
            )

        lines.extend([
            "\n--- [2] FAIR APPLICABILITY METRICS (APPLICABLE TASKS ONLY) ---",
            f"{'Recovery Method':<18} | {'Control':<8} | {'RSR':<8} | {'Delta':<7} | {'EOR':<8} | {'DER':<8} | {'MER':<8} | {'Invariants':<10}",
            "-" * 100,
        ])

        for method_name, s in summary.get("applicable_summaries", {}).items():
            ctrl = f"{s['control_success_rate']*100:.1f}%"
            rsr = f"{s['recovery_success_rate']*100:.1f}%"
            delta = f"{s['recovery_delta']:+.2f}"
            eor = f"{s['exactly_once_effect_rate']*100:.1f}%"
            der = f"{s['duplicate_effect_rate']*100:.1f}%"
            mer = f"{s['missing_effect_rate']*100:.1f}%"
            inv = f"{s['invariants_rate']*100:.1f}%"

            lines.append(
                f"{method_name:<18} | {ctrl:<8} | {rsr:<8} | {delta:<7} | {eor:<8} | {der:<8} | {mer:<8} | {inv:<10}"
            )

        lines.extend([
            "\n--- [3] RECOVERY OUTCOME TAXONOMY BREAKDOWN (FAULT RUNS) ---",
            f"{'Recovery Method':<18} | {'Failure Classifications'}",
            "-" * 100,
        ])

        for method_name, s in summary.get("summaries", {}).items():
            tax = s.get("failure_taxonomy", {})
            tax_str = ", ".join([f"{k}: {v}" for k, v in tax.items()]) or "No failures observed"
            lines.append(f"{method_name:<18} | {tax_str}")

        lines.append("=" * 100)
        lines.append("Key: RSR=Recovery Success Rate, EOR=Exactly-Once Rate, DER=Duplicate Effect Rate, MER=Missing Rate")
        return "\n".join(lines)
