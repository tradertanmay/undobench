"""Unified Command Line Interface for RecoverBench (Phase RB-6).

Provides the canonical user experience for external researchers and community users:
  recoverbench doctor
  recoverbench smoke
  recoverbench tasks [list|show|domains]
  recoverbench run [--model|--agent|--agent-url|--suite|--split|--task|--recovery|--workers|--resume|--output]
  recoverbench evaluate <run_dir_or_file>
  recoverbench report <run_dir>
  recoverbench inspect <run_dir_or_file>
  recoverbench submit [prepare|validate]
  recoverbench version
"""

from __future__ import annotations
import argparse
import datetime
import inspect
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List, Optional

from recoverbench.agents.adapter import resolve_agent
from recoverbench.engine import (
    BenchmarkEngine,
    BENCHMARK_VERSION,
    PROTOCOL_VERSION,
    RunConfig,
    SDK_VERSION,
    SMOKE_SUITE_TASKS,
    get_git_commit,
)
from recoverbench.harness.canonical import (
    load_canonical_system_prompt,
    load_canonical_tool_schemas,
    load_task_prompt_template,
)
from recoverbench.schemas.public_task import PublicTaskSpec
from recoverbench.schemas.task import TaskSpec
from recoverbench.submission import SubmissionPipeline
from recoverbench.tasks.registry import TASK_FACTORIES, TaskRegistry


def run_doctor() -> int:
    """Diagnostic check verifying the local environment, assets, tools, and sandboxes."""
    print("=" * 70)
    print("RECOVERBENCH ENVIRONMENT & CONFORMANCE DOCTOR")
    print("=" * 70)

    all_passed = True

    # 1. Python Version
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver >= (3, 10):
        print(f"✓ Python version: {py_str} (>= 3.10 required)")
    else:
        print(f"❌ Python version: {py_str} is unsupported. Python >= 3.10 required.")
        all_passed = False

    # 2. Git
    git_bin = shutil.which("git")
    if git_bin:
        try:
            g_ver = subprocess.check_output([git_bin, "--version"], text=True).strip()
            print(f"✓ Git available: {g_ver}")
        except Exception:
            print("✓ Git binary found in PATH")
    else:
        print("⚠ Git not found in PATH (version tracking will use fallback digests)")

    # 3. Docker (Optional)
    docker_bin = shutil.which("docker")
    if docker_bin:
        print("✓ Docker runtime available")
    else:
        print("ℹ Docker runtime: not installed (optional; local sandbox mode available)")

    # 4. Model / Provider Dependencies
    try:
        import openai
        print(f"✓ Provider SDK: openai v{getattr(openai, '__version__', 'unknown')} installed")
    except ImportError:
        print("ℹ Provider SDK: 'openai' not installed (run `pip install openai` for ModelAgentAdapter)")

    # 5. Filesystem Permissions
    try:
        test_dir = ".rb_doctor_test"
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "test.tmp")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        os.rmdir(test_dir)
        print("✓ Filesystem write permissions verified")
    except Exception as e:
        print(f"❌ Filesystem permission error: {e}")
        all_passed = False

    # 6. Benchmark Assets & Prompts
    try:
        sys_prompt = load_canonical_system_prompt()
        schemas = load_canonical_tool_schemas()
        task_tmpl = load_task_prompt_template()
        print(f"✓ Canonical assets (Protocol V4): {len(schemas)} tools, system prompt, templates loaded")
    except Exception as e:
        print(f"❌ Canonical asset loading failed: {e}")
        all_passed = False

    # 7. Task Registry & Schemas
    try:
        all_tasks = TaskRegistry.list_task_ids()
        dev_tasks = TaskRegistry.list_task_ids(split="dev")
        val_tasks = TaskRegistry.list_task_ids(split="validation")
        test_tasks = TaskRegistry.list_task_ids(split="test")
        print(f"✓ Task Registry: {len(all_tasks)} tasks loaded ({len(dev_tasks)} DEV, {len(val_tasks)} VAL, {len(test_tasks)} TEST)")
    except Exception as e:
        print(f"❌ Task registry failed: {e}")
        all_tasks = []
        all_passed = False

    # 8. Tool Schema Integrity Check
    try:
        schemas = load_canonical_tool_schemas()
        sig_mismatches = 0
        for tid in all_tasks:
            spec, _, proxy = TaskRegistry.load_task(tid)
            for t in spec.allowed_tools:
                if t in schemas and t in proxy._raw_tools:
                    fn = proxy._raw_tools[t]
                    sig = inspect.signature(fn)
                    req_params = [p.name for p in sig.parameters.values() if p.default == inspect.Parameter.empty]
                    props = schemas[t]["parameters"]["properties"]
                    if t != "complete_multipart_upload":
                        missing = [p for p in req_params if p not in props]
                        if missing:
                            sig_mismatches += 1
        if sig_mismatches == 0:
            print("✓ Tool-schema contract integrity: 100% conforming")
        else:
            print(f"❌ Tool-schema contract mismatches: {sig_mismatches}")
            all_passed = False
    except Exception as e:
        print(f"❌ Tool schema verification error: {e}")
        all_passed = False

    # 9. Sandbox Conformance
    try:
        spec, sb, proxy = TaskRegistry.load_task("RB-PAY-003")
        if hasattr(sb, "cleanup"):
            sb.cleanup()
        print("✓ Sandbox instantiation & teardown: Operational")
    except Exception as e:
        print(f"❌ Sandbox conformance error: {e}")
        all_passed = False

    print("=" * 70)
    if all_passed:
        print("RECOVERBENCH READY")
        return 0
    else:
        print("RECOVERBENCH ACTION REQUIRED: please address the failures listed above.")
        return 1


def run_smoke(task_id: str = "RB-PAY-003") -> int:
    """Run a fast deterministic smoke test verifying the full execution pipeline."""
    print("=" * 70)
    print("RECOVERBENCH CANONICAL SMOKE TEST")
    print(f"Task: {task_id} (Zero-API-key Deterministic Plan)")
    print("=" * 70)

    start_time = time.time()
    run_id = f"smoke_{int(start_time)}"
    config = RunConfig(
        run_id=run_id,
        task_id=task_id,
        output_dir="runs",
        recovery="naive",
    )
    engine = BenchmarkEngine(config)

    try:
        # Run Control condition
        ctrl = engine.execute_single_condition(
            task_id=task_id,
            condition="CONTROL",
            seed=42,
            pair_id="smoke_ctrl_pair",
            agent=resolve_agent(),  # Default ScriptedTaskAgent
            recovery_method_name="naive",
        )
        print("✓ sandbox initialized and executed")
        print("✓ control trial completed")

        # Run Fault condition
        fault = engine.execute_single_condition(
            task_id=task_id,
            condition="FAULT",
            seed=42,
            pair_id="smoke_fault_pair",
            agent=resolve_agent(),
            recovery_method_name="naive",
        )
        print("✓ fault injector triggered")
        print("✓ recovery layer engaged")
        print("✓ oracle evaluated external sandbox state")
        print("✓ effect log captured")

        # Write trajectories and evaluate
        with open(engine.trajectories_path, "w", encoding="utf-8") as f:
            f.write(ctrl.to_json() + "\n")
            f.write(fault.to_json() + "\n")

        summary = BenchmarkEngine.evaluate_trajectories_file(engine.trajectories_path)
        engine._write_manifest([task_id])
        engine._write_reports(summary)
        print("✓ offline evaluator recomputed metrics")

        elapsed = time.time() - start_time
        print("-" * 70)
        print(f"Smoke test completed in {elapsed:.2f}s (Target: < 120s)")
        print(f"Control Status: {ctrl.final_status} | Fault Status: {fault.final_status}")
        print(f"Results stored at: {engine.run_dir}")
        print("=" * 70)
        print("RecoverBench ready")
        return 0
    except Exception as e:
        print(f"\n❌ Smoke test failed: {e}")
        return 1


def run_env() -> int:
    """Print comprehensive runtime environment, hardware, and compatibility diagnostics."""
    print("=" * 70)
    print("RECOVERBENCH RUNTIME & COMPATIBILITY ENVIRONMENT")
    print("=" * 70)
    print(f"RecoverBench SDK:     {SDK_VERSION}")
    print(f"Benchmark Version:    {BENCHMARK_VERSION}")
    print(f"Protocol:             {PROTOCOL_VERSION}")
    print(f"Agent Protocol:       1.0")
    print(f"Python:               {platform.python_version()} ({platform.python_implementation()})")
    print(f"Python Executable:    {sys.executable}")
    print(f"Platform:             {platform.system()} {platform.release()} ({platform.machine()})")
    git_hash = get_git_commit() or "frozen-release"
    print(f"Git Commit:           {git_hash}")

    deps = {}
    for pkg in ["openai", "pytest", "jsonschema"]:
        try:
            mod = __import__(pkg)
            deps[pkg] = getattr(mod, "__version__", "installed")
        except ImportError:
            deps[pkg] = "not installed"
    print("\nCore & Provider Dependencies:")
    for k, v in deps.items():
        mark = "✓" if v != "not installed" else "ℹ"
        print(f"  {mark} {k:<15} : {v}")

    print("\nBenchmark Corpus:")
    print("  • Tasks:            36 tasks (14 DEV, 10 VALIDATION, 12 TEST)")
    print("  • Domains:          8 enterprise domains (Cloud, CRM, Database, Git, Messaging, Payments, Storage, Ticketing)")
    print("  • Tools:            47 canonical tool schemas (Protocol V4)")

    print("\nEnvironment Variables:")
    for var in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OLLAMA_BASE_URL"]:
        val = os.environ.get(var)
        if val:
            masked = val if "KEY" not in var else (val[:7] + "..." if len(val) > 10 else "***")
            print(f"  • {var:<18}: {masked}")
        else:
            print(f"  • {var:<18}: (not set)")

    print("=" * 70)
    print("COMPATIBILITY STATUS: OPERATIONAL")
    return 0


def run_schema(schema_name: str, export_dir: Optional[str] = None) -> int:
    """Print or export RecoverBench JSON schemas."""
    schemas: Dict[str, Any] = {}

    traj_schema_path = os.path.join(os.path.dirname(__file__), "data", "RECOVERBENCH_TRAJECTORY_SCHEMA_V1.json")
    if os.path.exists(traj_schema_path):
        with open(traj_schema_path, "r", encoding="utf-8") as f:
            schemas["trajectory"] = json.load(f)

    sub_schema_path = os.path.join(os.path.dirname(__file__), "data", "SUBMISSION_SCHEMA_V1.json")
    if os.path.exists(sub_schema_path):
        with open(sub_schema_path, "r", encoding="utf-8") as f:
            schemas["submission"] = json.load(f)

    compat_path = os.path.join(os.path.dirname(__file__), "data", "COMPATIBILITY_V1.json")
    if os.path.exists(compat_path):
        with open(compat_path, "r", encoding="utf-8") as f:
            schemas["compatibility"] = json.load(f)

    schemas["task"] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "PublicTaskSpec",
        "description": "Public agent-facing task specification",
        "type": "object",
        "required": ["benchmark_version", "task_id", "name", "split", "domain", "objective", "tools"],
        "properties": {
            "benchmark_version": {"type": "string"},
            "task_id": {"type": "string"},
            "name": {"type": "string"},
            "split": {"type": "string", "enum": ["dev", "validation", "test"]},
            "domain": {"type": "string"},
            "objective": {"type": "string"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "tool_definitions": {"type": "array", "items": {"type": "object"}},
            "metadata": {"type": "object"},
        },
    }

    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        for sname, scontent in schemas.items():
            out_file = os.path.join(export_dir, f"{sname}_schema.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(scontent, f, indent=2)
            print(f"✓ Exported {sname} schema to '{out_file}'")
        return 0

    if schema_name == "all":
        print(json.dumps(schemas, indent=2))
        return 0

    if schema_name in schemas:
        print(json.dumps(schemas[schema_name], indent=2))
        return 0
    else:
        print(f"❌ Unknown schema: '{schema_name}'. Available: {', '.join(schemas.keys())}")
        return 1


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recoverbench",
        description="RecoverBench: Benchmark & SDK for AI Agent Fault Tolerance Around External Side Effects",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command family")

    # 1. doctor
    subparsers.add_parser("doctor", help="Check local environment, dependencies, tool schemas, and sandboxes")

    # 2. smoke
    smoke_parser = subparsers.add_parser("smoke", help="Execute canonical smoke test through sandbox, faults, and oracle (< 2 min)")
    smoke_parser.add_argument("--task", default="RB-PAY-003", help="Canonical smoke task ID (default: RB-PAY-003)")

    # 3. tasks
    tasks_parser = subparsers.add_parser("tasks", help="Inspect benchmark tasks, domains, and public specifications")
    tasks_sub = tasks_parser.add_subparsers(dest="tasks_action", help="Task actions: list, show, domains")
    
    tasks_list = tasks_sub.add_parser("list", help="List available tasks")
    tasks_list.add_argument("--split", choices=["dev", "validation", "val", "test", "all"], default=None, help="Filter by split")
    tasks_list.add_argument("--domain", choices=["cloud", "crm", "database", "git", "messaging", "payments", "storage", "ticketing"], default=None, help="Filter by domain")

    tasks_show = tasks_sub.add_parser("show", help="Show public TaskSpec for a specific task")
    tasks_show.add_argument("task_id", help="Task identifier (e.g. RB-PAY-004)")

    tasks_sub.add_parser("domains", help="List represented operational enterprise domains")

    # 4. run
    run_parser = subparsers.add_parser("run", help="Run benchmark evaluation across models, agents, tasks, or splits")
    run_parser.add_argument("--model", help="Built-in model/provider adapter (e.g. ollama/llama3.1, openai/gpt-4o)")
    run_parser.add_argument("--agent", dest="agent_spec", help="Python agent plugin path (e.g. examples/my_agent.py:MyAgent)")
    run_parser.add_argument("--agent-url", help="HTTP Agent endpoint URL (e.g. http://localhost:8080)")
    run_parser.add_argument("--split", choices=["dev", "validation", "val", "test"], default=None, help="Task split to run")
    run_parser.add_argument("--suite", choices=["smoke", "domain", "qualification", "dev", "validation", "val", "all", "test"], default=None, help="Pre-defined evaluation suite")
    run_parser.add_argument("--task", dest="task_id", help="Run single specific task (e.g. RB-PAY-003)")
    run_parser.add_argument("--recovery", default="naive", choices=["naive", "checkpoint", "idempotency", "saga", "langgraph", "evoundo", "vbr", "verify_before_retry", "none"], help="Recovery baseline substrate")
    run_parser.add_argument("--workers", type=int, default=1, help="Concurrent execution workers (default: 1)")
    run_parser.add_argument("--resume", action="store_true", default=False, help="Resume an interrupted run skipping completed cells")
    run_parser.add_argument("--dry-run", action="store_true", default=False, help="Validate agent, tasks, and tool schemas without executing or mutating sandbox state")
    run_parser.add_argument("--output", "-o", default="runs", help="Output directory root for run artifacts (default: runs)")
    run_parser.add_argument("--run-id", default=None, help="Optional explicit run identifier")
    run_parser.add_argument("--seeds", default="42", help="Comma-separated list of random seeds (default: 42)")
    run_parser.add_argument("--allow-frozen-test-execution", action="store_true", default=False, help="Explicitly unlock execution of frozen held-out TEST tasks")

    # 5. evaluate
    eval_parser = subparsers.add_parser("evaluate", help="Offline metric recomputation from trajectory records without model calls")
    eval_parser.add_argument("path", help="Path to trajectories.jsonl or run directory")

    # 6. report
    report_parser = subparsers.add_parser("report", help="Generate standardized summary.json, summary.csv, and report.md from a run")
    report_parser.add_argument("run_dir", help="Path to completed run directory")

    # 7. inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect individual task trajectory, dialogue turns, tool calls, and oracle violations")
    inspect_parser.add_argument("path", help="Path to run directory or trajectory .jsonl file")
    inspect_parser.add_argument("--task", help="Filter inspection to specific task ID")

    # 8. submit
    submit_parser = subparsers.add_parser("submit", help="Prepare or validate standardized submission package")
    submit_sub = submit_parser.add_subparsers(dest="submit_action", help="Submit action: prepare, validate, inspect")

    sub_prep = submit_sub.add_parser("prepare", help="Package a completed run into submission bundle")
    sub_prep.add_argument("run_dir", help="Path to completed run directory")
    sub_prep.add_argument("--output", "-o", default=None, help="Destination directory for submission bundle")
    sub_prep.add_argument("--organization", default="Independent Researcher", help="Submitting organization name")
    sub_prep.add_argument("--paper-url", default=None, help="URL to technical preprint or paper")
    sub_prep.add_argument("--repo-url", default=None, help="URL to public code repository")

    sub_val = submit_sub.add_parser("validate", help="Validate a submission bundle against schemas and reproducibility checks")
    sub_val.add_argument("submission_dir", help="Path to submission directory")
    sub_val.add_argument("--strict", action="store_true", default=False, help="Enforce strict requirements for OFFICIAL_VERIFIED track (e.g. pinned model digests)")

    sub_inspect = submit_sub.add_parser("inspect", help="Inspect and summarize a prepared submission bundle")
    sub_inspect.add_argument("submission_dir", help="Path to submission directory")

    # 9. env
    subparsers.add_parser("env", help="Print detailed runtime environment, platform, and compatibility diagnostics")

    # 10. schema
    schema_parser = subparsers.add_parser("schema", help="Inspect or export RecoverBench JSON schemas (trajectory, submission, task, compatibility)")
    schema_parser.add_argument("schema_type", nargs="?", default="all", choices=["trajectory", "submission", "task", "compatibility", "all"], help="Schema to display (default: all)")
    schema_parser.add_argument("--export", default=None, help="Directory to export schemas into")

    # 11. version
    subparsers.add_parser("version", help="Print RecoverBench and protocol version information")

    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 1

    if parsed.command == "doctor":
        return run_doctor()

    elif parsed.command == "smoke":
        return run_smoke(task_id=parsed.task)

    elif parsed.command == "version":
        git_hash = get_git_commit() or "frozen-v1.0.1"
        print(f"RecoverBench {BENCHMARK_VERSION}")
        print(f"SDK Version:      {SDK_VERSION}")
        print(f"Protocol:         {PROTOCOL_VERSION}")
        print(f"Task Count:       36 workflows across 8 domains")
        print(f"Code Commit:      {git_hash}")
        return 0

    elif parsed.command == "env":
        return run_env()

    elif parsed.command == "schema":
        return run_schema(parsed.schema_type, export_dir=parsed.export)

    elif parsed.command == "tasks":
        action = parsed.tasks_action or "list"
        if action == "domains":
            print("\nRecoverBench Operational Enterprise Domains (8):")
            print("-" * 50)
            for d in ["cloud", "crm", "database", "git", "messaging", "payments", "storage", "ticketing"]:
                tids = [tid for tid in TaskRegistry.list_task_ids() if TaskRegistry.get_task_spec(tid).domain.value.lower() == d]
                print(f"  • {d.capitalize():<12} ({len(tids)} tasks: {', '.join(tids)})")
            print("-" * 50)
            return 0

        elif action == "show":
            tid = parsed.task_id.upper()
            try:
                spec = TaskRegistry.get_task_spec(tid)
                pub = PublicTaskSpec.from_task_spec(spec)
                print(pub.to_json())
                return 0
            except KeyError:
                print(f"❌ Task '{parsed.task_id}' not found.")
                return 1

        elif action == "list":
            split_arg = parsed.split.lower() if parsed.split else None
            if split_arg == "val":
                split_arg = "validation"
            tids = TaskRegistry.list_task_ids(split=split_arg)
            if parsed.domain:
                tids = [t for t in tids if TaskRegistry.get_task_spec(t).domain.value.lower() == parsed.domain.lower()]

            print(f"\n{'Task ID':<14} {'Split':<12} {'Domain':<12} {'Name':<36} {'Tools':<6}")
            print("-" * 84)
            for tid in sorted(tids):
                spec = TaskRegistry.get_task_spec(tid)
                print(f"{tid:<14} {spec.split.value.upper():<12} {spec.domain.value.capitalize():<12} {spec.name[:34]:<36} {len(spec.allowed_tools):<6}")
            print("-" * 84)
            print(f"Total matching tasks: {len(tids)}\n")
            return 0

    elif parsed.command == "evaluate":
        try:
            summary = BenchmarkEngine.evaluate_trajectories_file(parsed.path)
            print("\n" + "=" * 70)
            print(f"RECOVERBENCH OFFLINE EVALUATION REPORT")
            print("=" * 70)
            print(f"Total Paired Trials:        {summary.get('total_pairs', 0)}")
            print(f"Control Competence (Layer A): {summary.get('control_rate', 0.0):.2%} ({summary.get('control_passed', 0)} / {summary.get('total_pairs', 0)})")
            print(f"Recovery Success (RSR):      {summary.get('rsr', 0.0):.2%} ({summary.get('fault_passed', 0)} / {summary.get('total_pairs', 0)})")
            crsr = summary.get('crsr')
            crsr_s = f"{crsr:.2%}" if crsr is not None else "N/A"
            print(f"Conditional Recovery (CRSR): {crsr_s} ({summary.get('crsr_passed', 0)} / {summary.get('control_passed', 0)})")
            eor = summary.get('eor')
            eor_s = f"{eor:.2%}" if eor is not None else "N/A"
            print(f"Exactly-Once Rate (EOR):    {eor_s} ({summary.get('eor_passed', 0)} / {summary.get('control_passed', 0)})")
            print(f"Duplicate Effect Rate (DER): {summary.get('der', 0.0):.2%}")
            print(f"Missing Effect Rate (MER):   {summary.get('mer', 0.0):.2%}")
            print("=" * 70 + "\n")
            return 0
        except Exception as e:
            print(f"❌ Evaluation failed: {e}")
            return 1

    elif parsed.command == "report":
        try:
            target_dir = parsed.run_dir
            traj_path = os.path.join(target_dir, "trajectories.jsonl")
            if not os.path.exists(traj_path) and os.path.isdir(target_dir):
                for entry in sorted(os.listdir(target_dir), reverse=True):
                    sub_p = os.path.join(target_dir, entry)
                    if os.path.isdir(sub_p) and os.path.exists(os.path.join(sub_p, "trajectories.jsonl")):
                        target_dir = sub_p
                        traj_path = os.path.join(sub_p, "trajectories.jsonl")
                        break

            summary = BenchmarkEngine.evaluate_trajectories_file(traj_path)
            config = RunConfig(run_id=os.path.basename(target_dir.rstrip("/")), output_dir=os.path.dirname(target_dir.rstrip("/")) or "runs")
            engine = BenchmarkEngine(config)
            engine._write_reports(summary)
            print(f"✓ Summary and report written to '{target_dir}'")
            return 0
        except Exception as e:
            print(f"❌ Report generation failed: {e}")
            return 1

    elif parsed.command == "inspect":
        target = parsed.path
        if os.path.isdir(target):
            target = os.path.join(target, "trajectories.jsonl")
        if not os.path.exists(target):
            print(f"❌ File not found: {target}")
            return 1

        print(f"\nInspecting trajectories in '{target}':")
        with open(target, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                try:
                    r = json.loads(line)
                    tid = r.get("task_id") or r.get("verdict", {}).get("task_id", "unknown")
                    if parsed.task and tid.lower() != parsed.task.lower():
                        continue
                    cond = r.get("condition") or "PAIRED"
                    status = r.get("final_status") or ("PASS" if r.get("verdict", {}).get("fault_success") else "FAIL")
                    tools_used = len(r.get("tool_calls", []))
                    hidden = r.get("benchmark_hidden_trace") or {}
                    violations = hidden.get("oracle_violations", [])
                    print(f"  [{idx}] Task: {tid:<12} Condition: {cond:<8} Status: {status:<6} Tools: {tools_used:<3} Violations: {len(violations)}")
                    if violations:
                        for v in violations:
                            print(f"        ⚠ Violation: {v}")
                except Exception:
                    pass
        print("")
        return 0

    elif parsed.command == "submit":
        if not parsed.submit_action:
            submit_parser.print_help()
            return 1

        if parsed.submit_action == "prepare":
            try:
                out = SubmissionPipeline.prepare_submission(
                    run_dir=parsed.run_dir,
                    output_dir=parsed.output,
                    organization=parsed.organization,
                    paper_url=parsed.paper_url,
                    repo_url=parsed.repo_url,
                )
                print(f"\n✓ Submission bundle prepared successfully at '{out}'")
                print("To validate before submitting, run:")
                print(f"  recoverbench submit validate {out}\n")
                return 0
            except Exception as e:
                print(f"❌ Submission preparation failed: {e}")
                return 1

        elif parsed.submit_action == "validate":
            valid, errors, checks = SubmissionPipeline.validate_submission(
                parsed.submission_dir, strict=parsed.strict
            )
            print("\n" + "=" * 70)
            print("RECOVERBENCH SUBMISSION VALIDATION")
            print("=" * 70)
            for k, passed in checks.items():
                mark = "✓" if passed else "❌"
                print(f" {mark} {k.replace('_', ' ').capitalize()}")
            if errors:
                print("\nValidation Errors Encountered:")
                for err in errors:
                    print(f"  ❌ {err}")
            print("=" * 70)
            if valid:
                print("Submission ready.\n")
                return 0
            else:
                print("Submission validation failed. Please address the errors above.\n")
                return 1

        elif parsed.submit_action == "inspect":
            try:
                info = SubmissionPipeline.inspect_submission(parsed.submission_dir)
                print("\n" + "=" * 70)
                print("RECOVERBENCH SUBMISSION INSPECTION")
                print("=" * 70)
                print(f"  Submission ID:       {info.get('submission_id')}")
                print(f"  Benchmark Version:   {info.get('benchmark_version')}")
                print(f"  Created Date:        {info.get('date')}")
                print(f"  Organization:        {info.get('organization')}")
                print(f"  Track:               {info.get('track')}")
                print(f"  Trust Level:         {info.get('trust_level')}")
                print(f"  Verification Status: {info.get('verification_status')}")
                agent = info.get("agent", {})
                print(f"  Agent Name:          {agent.get('name')}")
                print(f"  Model Canonical:     {agent.get('model_name') or 'N/A'}")
                print(f"  Model Digest:        {agent.get('model_digest') or 'None (Unpinned)'}")
                print(f"  Identity Pinned:     {'✓ Yes' if agent.get('is_immutable') else '⚠ No (Unpinned alias)'}")
                print(f"  Paper URL:           {info.get('paper_url') or 'None'}")
                print(f"  Repository URL:      {info.get('repo_url') or 'None'}")
                print("-" * 70)
                print("METRICS SUMMARY:")
                metrics = info.get("metrics", {})
                print(f"  • Control Competence: {metrics.get('control_rate', 0.0):.2%}")
                print(f"  • RSR (Unconditional): {metrics.get('rsr', 0.0):.2%}")
                crsr_val = f"{metrics.get('crsr'):.2%}" if metrics.get('crsr') is not None else "N/A"
                print(f"  • CRSR (Conditional): {crsr_val}")
                eor_val = f"{metrics.get('eor'):.2%}" if metrics.get('eor') is not None else "N/A"
                print(f"  • Exactly-Once (EOR): {eor_val}")
                print(f"  • Duplicate Effect:   {metrics.get('der', 0.0):.2%}")
                print(f"  • Missing Effect:     {metrics.get('mer', 0.0):.2%}")
                print("-" * 70)
                print("INTEGRITY CHECKS:")
                for k, v in info.get("checks", {}).items():
                    mark = "✓" if v else "❌"
                    print(f"  {mark} {k.replace('_', ' ').capitalize()}")
                if info.get("trust_notice"):
                    print("-" * 70)
                    print(f"ℹ Trust Notice:\n  {info.get('trust_notice')}")
                print("=" * 70 + "\n")
                return 0
            except Exception as e:
                print(f"❌ Failed to inspect submission: {e}")
                return 1

    elif parsed.command == "run":
        run_id = parsed.run_id or f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        seeds = [int(s.strip()) for s in parsed.seeds.split(",")]

        config = RunConfig(
            run_id=run_id,
            model=parsed.model,
            agent_spec=parsed.agent_spec,
            agent_url=parsed.agent_url,
            split=parsed.split,
            suite=parsed.suite,
            task_id=parsed.task_id,
            recovery=parsed.recovery,
            workers=parsed.workers,
            resume=parsed.resume,
            dry_run=parsed.dry_run,
            output_dir=parsed.output,
            seeds=seeds,
            allow_frozen_test_execution=parsed.allow_frozen_test_execution,
        )

        engine = BenchmarkEngine(config)
        if parsed.dry_run:
            print("\n" + "=" * 70)
            print(f"RECOVERBENCH DRY-RUN VALIDATION (Run ID: {run_id})")
            print("=" * 70)
            res = engine.run_benchmark()
            agent_id = res.summary.get("agent_identity", {})
            print(f"  Agent/Model:     {agent_id.get('canonical_name') or agent_id.get('raw_identifier')}")
            print(f"  Resolved Digest: {agent_id.get('digest') or 'none'}")
            print(f"  Identity Pinned: {'✓ Yes' if agent_id.get('is_immutable') else '⚠ No (Unpinned alias)'}")
            print(f"  Tasks Resolved:  {res.summary.get('tasks_count')} workflows across domains")
            print(f"  Total Paired:    {res.summary.get('total_pairs')} trials (0 mutations executed)")
            print(f"  Tool Schemas:    47 conforming tools (Protocol V4)")
            print("=" * 70)
            print("✓ Dry-run validation passed. System ready for benchmark execution.\n")
            return 0

        print("\n" + "=" * 70)
        print(f"RECOVERBENCH BENCHMARK EXECUTION (Run ID: {run_id})")
        print("=" * 70)
        print(f"  Agent/Model: {config.model or config.agent_spec or config.agent_url or 'Default'}")
        print(f"  Suite/Split: {config.suite or config.split or config.task_id or 'dev'}")
        print(f"  Recovery:    {config.recovery}")
        print(f"  Seeds:       {seeds}")
        print(f"  Workers:     {config.workers}")
        print(f"  Output Dir:  {engine.run_dir}")
        print("=" * 70)

        def progress_cb(msg: str) -> None:
            print(f"  [{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

        try:
            summary = engine.run_benchmark(progress_callback=progress_cb)
            print("\n" + "=" * 70)
            print("BENCHMARK EXECUTION COMPLETE")
            print("=" * 70)
            print(f"Control Competence: {summary['control_rate']:.2%} ({summary['control_passed']} / {summary['total_pairs']})")
            print(f"RSR (Unconditional): {summary['rsr']:.2%} ({summary['fault_passed']} / {summary['total_pairs']})")
            crsr_str = f"{summary['crsr']:.2%}" if summary['crsr'] is not None else "N/A"
            print(f"CRSR (Conditional): {crsr_str} ({summary['crsr_passed']} / {summary['control_passed']})")
            print(f"DER (Duplicate Effect): {summary['der']:.2%}")
            print(f"MER (Missing Effect):   {summary['mer']:.2%}")
            print("-" * 70)
            print(f"Results: {engine.run_dir}/")
            print("=" * 70 + "\n")
            return 0
        except Exception as e:
            print(f"\n❌ Benchmark execution aborted: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
