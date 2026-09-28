"""Command Line Interface for RecoverBench."""

from __future__ import annotations
import argparse
import json
import sys
from typing import List, Optional
from recoverbench.metrics.evaluator import BenchmarkEvaluator
from recoverbench.runner.runner import BenchmarkRunner
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.tasks.registry import TaskRegistry


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recoverbench",
        description="RecoverBench: Method-Agnostic Benchmark for AI Agent Recovery Around External Side Effects",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run a single task trial")
    run_parser.add_argument("--task", "-t", required=True, help="Task ID (e.g., RB-PAY-001)")
    run_parser.add_argument(
        "--recovery", "-r",
        default="naive",
        choices=["naive", "checkpoint", "idempotency", "saga", "langgraph", "evoundo",
                 "naive_retry:v1", "checkpoint:v1", "idempotency:v1", "saga:v1", "langgraph_native:v1", "evoundo:rb1"],
        help="Recovery baseline method to evaluate",
    )
    run_parser.add_argument(
        "--fault", "-f",
        default=None,
        help="Canonical fault alias (F0-F6, or NO_FAULT)",
    )
    run_parser.add_argument(
        "--boundary", "-b",
        default=None,
        help="Execution boundary (PRE_MUTATION, POST_MUTATION_PRE_ACK, etc.)",
    )
    run_parser.add_argument(
        "--perturbation", "-p",
        default=None,
        help="Perturbation type (WORKER_CRASH, ACK_LOSS, NETWORK_TIMEOUT, etc.)",
    )
    run_parser.add_argument(
        "--allow-frozen-test-execution",
        action="store_true",
        default=False,
        help="Explicitly unlock execution of frozen TEST tasks (STRICT QUARANTINE PROTECTED)",
    )
    run_parser.add_argument("--output-dir", "-o", default="results", help="Directory to save logs and trajectories")

    # Command: eval
    eval_parser = subparsers.add_parser("eval", help="Run batch evaluation suite across tasks and methods")
    eval_parser.add_argument(
        "--suite", "-s",
        default="validation",
        help="Task suite to evaluate: dev, validation (or val), dev,val, all, or test (quarantined)",
    )
    eval_parser.add_argument(
        "--recovery", "-r",
        default="naive,checkpoint,idempotency,saga,langgraph,evoundo",
        help="Comma-separated list of recovery methods to evaluate",
    )
    eval_parser.add_argument(
        "--include-controls",
        action="store_true",
        default=True,
        help="Run NO_FAULT failure-free controls for delta calculation",
    )
    eval_parser.add_argument("--trials", "-n", type=int, default=1, help="Number of repetitions per condition")
    eval_parser.add_argument(
        "--allow-frozen-test-execution",
        action="store_true",
        default=False,
        help="Explicitly unlock execution of frozen TEST tasks (STRICT QUARANTINE PROTECTED)",
    )
    # Command: validate-harness
    val_parser = subparsers.add_parser("validate-harness", help="Statically validate harness tool schemas and signatures")
    val_parser.add_argument(
        "--suite", "-s",
        default="validation",
        choices=["dev", "validation", "val", "test", "all"],
        help="Task suite to validate (dev, validation, test, all)",
    )
    val_parser.add_argument(
        "--version", "-v",
        default="V4",
        help="Canonical schema version to validate against (defaults to V4)",
    )

    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 1

    if parsed.command == "validate-harness":
        import inspect
        from recoverbench.harness.canonical import load_canonical_tool_schemas, format_return_envelope

        suite = parsed.suite.lower()
        if suite == "val":
            suite = "validation"

        schemas = load_canonical_tool_schemas(version=parsed.version)
        print(f"\n[RecoverBench] Validating Harness Schemas & Signatures ({parsed.version}) for Suite: '{suite.upper()}'")

        if suite == "all":
            task_ids = TaskRegistry.list_task_ids()
        else:
            task_ids = TaskRegistry.list_task_ids(split=suite)

        all_passed = True
        print(f"{'Task ID':<14} {'Split':<12} {'Domain':<12} {'Tools':<8} {'Status':<10} {'Notes'}")
        print("-" * 80)

        for tid in sorted(task_ids):
            task_spec, sandbox, proxy_reg = TaskRegistry.load_task(tid)
            task_tools = task_spec.allowed_tools
            missing = [t for t in task_tools if t not in schemas]

            sig_issues = []
            for t in task_tools:
                if t in schemas:
                    fn = proxy_reg._raw_tools.get(t)
                    if fn:
                        sig = inspect.signature(fn)
                        py_req = [p.name for p in sig.parameters.values() if p.default == inspect.Parameter.empty]
                        schema_props = schemas[t]["parameters"]["properties"]
                        if t == "complete_multipart_upload":
                            pass  # Handled via canonical argument coercion
                        else:
                            missing_params = [p for p in py_req if p not in schema_props]
                            if missing_params:
                                sig_issues.append(f"{t}: missing {missing_params}")
                    else:
                        sig_issues.append(f"{t}: missing in proxy")

            if missing or sig_issues:
                all_passed = False
                status = "FAIL"
                notes = []
                if missing:
                    notes.append(f"Missing schemas: {missing}")
                if sig_issues:
                    notes.append(f"Sig issues: {sig_issues}")
                notes_str = "; ".join(notes)
            else:
                status = "PASS"
                notes_str = "All tools conforming"

            print(f"{tid:<14} {task_spec.split.value.upper():<12} {task_spec.domain.value.upper():<12} {len(task_tools):<8} {status:<10} {notes_str}")

        print("-" * 80)
        if all_passed:
            print(f"[SUCCESS] All {len(task_ids)} tasks in '{suite.upper()}' passed static harness preflight qualification.\n")
            return 0
        else:
            print(f"[CRITICAL ERROR] One or more tasks in '{suite.upper()}' failed harness qualification!\n")
            return 1

    runner = BenchmarkRunner(output_dir=parsed.output_dir)

    if parsed.command == "run":
        # Resolve fault specification
        if parsed.fault:
            fault_spec = FaultSpec.from_alias(parsed.fault)
        elif parsed.boundary and parsed.perturbation:
            b = ExecutionBoundary(parsed.boundary.upper())
            p = Perturbation(parsed.perturbation.upper())
            fault_spec = FaultSpec(boundary=b, perturbation=p)
        else:
            fault_spec = FaultSpec.from_alias("F2")  # Default to Lost ACK

        print(f"\n[RecoverBench] Running task '{parsed.task}' under method '{parsed.recovery}'")
        print(f"               Boundary: {fault_spec.boundary.value} | Perturbation: {fault_spec.perturbation.value}")

        try:
            result = runner.run_trial(
                parsed.task,
                parsed.recovery,
                fault_spec,
                allow_frozen_test_execution=parsed.allow_frozen_test_execution,
            )
        except Exception as e:
            print(f"\n[ERROR] Trial execution aborted: {e}")
            return 1

        print("\n" + "-" * 70)
        print(f"VERDICT: {'PASSED (Safe & Correct)' if result.success else 'FAILED (Unsafe or Incomplete)'}")
        print(f"  Objective Satisfied:       {result.verdict.objective_satisfied}")
        print(f"  Final State Valid:         {result.verdict.final_state_valid}")
        print(f"  Invariants Held:           {result.verdict.invariants_held}")
        print(f"  No Forbidden Effects:      {result.verdict.no_forbidden_effects}")
        print(f"  Exactly-Once Satisfied:    {result.verdict.exactly_once_satisfied}")
        print(f"  Committed Duplicate Count: {result.verdict.duplicate_effects_count}")
        print(f"  Missing Effects Count:     {result.verdict.missing_effects_count}")
        print(f"  Physical Invocations:      {result.verdict.physical_invocation_count}")
        print(f"  Committed Mutations:       {result.verdict.committed_mutation_count}")
        print(f"  Semantic Effects:          {result.verdict.semantic_effect_count}")

        if result.verdict.violations:
            print("\nVIOLATIONS OBSERVED:")
            for v in result.verdict.violations:
                print(f"  ❌ {v}")
        print("-" * 70)
        return 0 if result.success else 1

    elif parsed.command == "eval":
        suite_lower = parsed.suite.lower()
        if suite_lower == "val":
            suite_lower = "validation"

        if suite_lower == "dev,val" or suite_lower == "val,dev":
            task_ids = TaskRegistry.list_task_ids(split="dev") + TaskRegistry.list_task_ids(split="validation")
        elif suite_lower == "all":
            if parsed.allow_frozen_test_execution:
                task_ids = TaskRegistry.list_task_ids()
            else:
                print("\n[RecoverBench NOTICE] 'all' specified without --allow-frozen-test-execution.")
                print("                     Running DEV (14) + VALIDATION (10) tasks only. TEST set (12) is quarantined.")
                task_ids = TaskRegistry.list_task_ids(split="dev") + TaskRegistry.list_task_ids(split="validation")
        elif suite_lower == "test":
            if not parsed.allow_frozen_test_execution:
                print("\n[CRITICAL ERROR] TEST set execution is strictly quarantined!")
                print("To evaluate frozen TEST tasks, you must pass --allow-frozen-test-execution.")
                print("Do not consume the TEST set during development.")
                return 1
            task_ids = TaskRegistry.list_task_ids(split="test")
        else:
            task_ids = TaskRegistry.list_task_ids(split=suite_lower)

        methods = [m.strip() for m in parsed.recovery.split(",")]

        print(f"\n[RecoverBench] Starting Evaluation Suite: '{parsed.suite.upper()}'")
        print(f"               Tasks ({len(task_ids)}): {', '.join(task_ids)}")
        print(f"               Methods ({len(methods)}): {', '.join(methods)}")
        print(f"               Trials per task: {parsed.trials}")
        print(f"               Include NO_FAULT Controls: {parsed.include_controls}")

        try:
            summary = runner.run_suite(
                task_ids=task_ids,
                recovery_methods=methods,
                include_controls=parsed.include_controls,
                trials=parsed.trials,
                allow_frozen_test_execution=parsed.allow_frozen_test_execution,
            )
        except Exception as e:
            print(f"\n[ERROR] Evaluation aborted: {e}")
            return 1

        report_table = BenchmarkEvaluator.format_terminal_report(summary)
        print(report_table)
        print(f"\nMachine-readable summary saved to '{parsed.output_dir}/eval_summary.json'")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
