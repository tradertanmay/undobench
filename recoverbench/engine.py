"""RecoverBench Unified Execution and Evaluation Engine (Phase RB-6).

Orchestrates clean-room benchmark execution, paired control/fault conditions,
offline trajectory evaluation, report generation, concurrency, and resume.
"""

from __future__ import annotations
import concurrent.futures
import csv
import datetime
import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from recoverbench.agents.adapter import (
    AgentContext,
    AgentResponse,
    RecoverBenchAgent,
    resolve_agent,
    resolve_agent_identity,
)
from recoverbench.harness.canonical import (
    format_user_prompt,
    load_canonical_system_prompt,
)
from recoverbench.oracle.state_oracle import StateOracle
from recoverbench.recovery_methods import RECOVERY_METHOD_REGISTRY, RecoveryMethod
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.schemas.public_task import PublicTaskSpec
from recoverbench.schemas.task import TaskSpec
from recoverbench.schemas.trajectory import ExecutionTrajectory, validate_trajectory
from recoverbench.tasks.registry import TASK_FACTORIES, TaskRegistry

logger = logging.getLogger("recoverbench.engine")

BENCHMARK_VERSION = "1.0.1"
PROTOCOL_VERSION = "V4"
SDK_VERSION = "1.0.0"

# Canonical Smoke Suite: 4 diverse, representative workflows across domains
SMOKE_SUITE_TASKS = ["RB-PAY-003", "RB-DB-001", "RB-GIT-001", "RB-CLOUD-002"]

# Canonical 8-Domain Qualification Suite (DEV/VAL only): 1 workflow per enterprise domain
QUALIFICATION_SUITE_TASKS = [
    "RB-CLOUD-001",
    "RB-CRM-001",
    "RB-DB-001",
    "RB-GIT-001",
    "RB-MSG-001",
    "RB-PAY-001",
    "RB-STOR-001",
    "RB-TICK-001",
]


def get_git_commit() -> Optional[str]:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


@dataclass
class RunResult:
    """Structured result of a RecoverBench benchmark execution run."""
    run_id: str
    status: str
    summary: Dict[str, Any]
    run_dir: str
    trajectories_path: str
    summary_path: str
    report_path: str

    def __getitem__(self, item: str) -> Any:
        return self.summary[item]

    def get(self, item: str, default: Any = None) -> Any:
        return self.summary.get(item, default)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunConfig:
    run_id: str
    benchmark_version: str = BENCHMARK_VERSION
    protocol_version: str = PROTOCOL_VERSION
    sdk_version: str = SDK_VERSION
    model: Optional[str] = None
    agent_spec: Optional[str] = None
    agent_url: Optional[str] = None
    split: Optional[str] = None
    suite: Optional[str] = None
    task_id: Optional[str] = None
    recovery: str = "naive"
    workers: int = 1
    resume: bool = False
    dry_run: bool = False
    output_dir: str = "runs"
    seeds: List[int] = field(default_factory=lambda: [42])
    allow_frozen_test_execution: bool = False


class BenchmarkEngine:
    """Core execution and evaluation engine for RecoverBench."""

    def __init__(self, config: RunConfig):
        self.config = config
        self.run_dir = os.path.join(config.output_dir, config.run_id)
        self.trajectories_path = os.path.join(self.run_dir, "trajectories.jsonl")
        self.manifest_path = os.path.join(self.run_dir, "manifest.json")
        self.config_path = os.path.join(self.run_dir, "config.json")
        self.summary_json_path = os.path.join(self.run_dir, "summary.json")
        self.summary_csv_path = os.path.join(self.run_dir, "summary.csv")
        self.report_md_path = os.path.join(self.run_dir, "report.md")
        self.state_path = os.path.join(self.run_dir, ".state.json")
        self.logs_dir = os.path.join(self.run_dir, "logs")

        os.makedirs(self.run_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

    def resolve_tasks(self) -> List[str]:
        """Resolve target task list from configuration."""
        if self.config.task_id:
            if "," in self.config.task_id:
                tids = [t.strip().upper() for t in self.config.task_id.split(",") if t.strip()]
                for tid in tids:
                    if tid not in TASK_FACTORIES:
                        raise KeyError(f"Task '{tid}' not found in registry.")
                return tids
            tid = self.config.task_id.upper()
            if tid not in TASK_FACTORIES:
                raise KeyError(f"Task '{self.config.task_id}' not found in registry.")
            return [tid]

        if self.config.suite:
            s = self.config.suite.lower()
            if s == "smoke":
                return list(SMOKE_SUITE_TASKS)
            elif s in ["domain", "domains", "qualification"]:
                return list(QUALIFICATION_SUITE_TASKS)
            elif s in ["dev", "validation", "val", "test"]:
                split_name = "validation" if s == "val" else s
                if split_name == "test" and not self.config.allow_frozen_test_execution:
                    raise PermissionError(
                        "TEST suite is strictly quarantined. Pass --allow-frozen-test-execution to unlock."
                    )
                return TaskRegistry.list_task_ids(split=split_name)
            elif s == "all":
                if not self.config.allow_frozen_test_execution:
                    logger.warning("Suite 'all' requested without test unlock. Evaluating DEV + VALIDATION.")
                    return TaskRegistry.list_task_ids(split="dev") + TaskRegistry.list_task_ids(split="validation")
                return TaskRegistry.list_task_ids()

        if self.config.split:
            sp = self.config.split.lower()
            split_name = "validation" if sp == "val" else sp
            if split_name == "test" and not self.config.allow_frozen_test_execution:
                raise PermissionError(
                    "TEST suite is strictly quarantined. Pass --allow-frozen-test-execution to unlock."
                )
            return TaskRegistry.list_task_ids(split=split_name)

        # Default fallback: dev split
        return TaskRegistry.list_task_ids(split="dev")

    def _get_active_fault_spec(self, spec: TaskSpec) -> FaultSpec:
        active = [s for s in spec.supported_fault_scenarios if s.boundary != ExecutionBoundary.NO_FAULT]
        if active and active[0].fault_spec:
            return active[0].fault_spec
        elif active:
            fs = active[0]
            return FaultSpec(
                boundary=fs.boundary,
                perturbation=fs.perturbation,
                target_tool=fs.target_tool,
                target_call_index=fs.target_call_index,
                concurrent_state_delta=fs.concurrent_state_delta,
            )
        return FaultSpec.from_alias("F2")

    def execute_single_condition(
        self,
        task_id: str,
        condition: str,  # "CONTROL" or "FAULT"
        seed: Optional[int],
        pair_id: str,
        agent: RecoverBenchAgent,
        recovery_method_name: str,
    ) -> ExecutionTrajectory:
        """Run a single task trial under specified failure condition."""
        task_spec, sandbox, proxy_reg = TaskRegistry.load_task(task_id)
        public_task = PublicTaskSpec.from_task_spec(task_spec, version=self.config.protocol_version)

        # Determine fault spec
        if condition == "CONTROL":
            fault_spec = FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)
        else:
            fault_spec = self._get_active_fault_spec(task_spec)

        proxy_reg.injector.configure(fault_spec)
        proxy_reg.reset()

        # Wrap tools if recovery method specified and available
        wrapped_tools: Dict[str, Callable[..., Any]] = {}
        recovery_obj: Optional[RecoveryMethod] = None
        if recovery_method_name and recovery_method_name.lower() not in ["none", "native", "direct"]:
            # Normalization
            alias_map = {
                "naive": "naive_retry:v1",
                "checkpoint": "checkpoint:v1",
                "idempotency": "idempotency:v1",
                "saga": "saga:v1",
                "langgraph": "langgraph_native:v1",
                "evoundo": "evoundo:rb1",
                "vbr": "verify_before_retry:v1",
                "verify_before_retry": "verify_before_retry:v1",
            }
            resolved_method = alias_map.get(recovery_method_name.lower(), recovery_method_name)
            if resolved_method in RECOVERY_METHOD_REGISTRY:
                recovery_obj = RECOVERY_METHOD_REGISTRY[resolved_method]()

        for tname in task_spec.allowed_tools:
            raw_fn = proxy_reg.get_proxied_tool(tname)
            if recovery_obj:
                wrapped_tools[tname] = recovery_obj.wrap_tool(tname, raw_fn, task_spec)
            else:
                wrapped_tools[tname] = raw_fn

        # Prepare context
        context = AgentContext(
            system_prompt=load_canonical_system_prompt(version=self.config.protocol_version),
            user_prompt=format_user_prompt(task_spec, version=self.config.protocol_version),
            seed=seed,
            max_turns=10,
        )

        start_time = time.time()
        agent_res: AgentResponse = agent.run(public_task, wrapped_tools, context)
        latency_ms = (time.time() - start_time) * 1000.0

        # Evaluate External Sandbox State & Oracle
        verdict = StateOracle.evaluate(
            task=task_spec,
            sandbox=sandbox,
            proxy_registry=proxy_reg,
            method_name=recovery_obj.name if recovery_obj else "none",
            boundary_name=fault_spec.boundary.value,
            perturbation_name=fault_spec.perturbation.value,
            agent_succeeded=(agent_res.status == "SUCCESS" and agent_res.error is None),
            agent_error=agent_res.error,
        )

        hidden_trace = {
            "effect_log": [e.to_dict() for e in proxy_reg.effect_log],
            "injection_log": proxy_reg.injector.injection_log,
            "final_state": verdict.final_state,
            "oracle_violations": verdict.violations,
            "oracle_verdict": {
                "overall_success": verdict.overall_recovery_correct,
                "goal_satisfied": verdict.goal_satisfied,
                "final_state_correct": verdict.final_state_correct,
                "invariant_satisfied": verdict.invariant_satisfied,
                "required_effects_satisfied": verdict.required_effects_satisfied,
                "effect_multiplicity_correct": verdict.effect_multiplicity_correct,
                "forbidden_effects_absent": verdict.forbidden_effects_absent,
                "ordering_correct": verdict.ordering_correct,
                "committed_mutation_count": verdict.committed_mutation_count,
                "duplicate_effects_count": verdict.duplicate_effects_count,
                "missing_effects_count": verdict.missing_effects_count,
                "failure_classification": verdict.primary_failure_classification or ("SUCCESS" if verdict.overall_recovery_correct else "UNKNOWN_FAILURE"),
            },
        }

        # Cleanup sandbox
        if hasattr(sandbox, "cleanup"):
            try:
                sandbox.cleanup()
            except Exception:
                pass

        # Flatten tool calls and results
        tool_calls = []
        tool_results = []
        for turn in agent_res.turns:
            if turn.tool_calls:
                tool_calls.extend(turn.tool_calls)
            if turn.tool_results:
                tool_results.extend(turn.tool_results)

        agent_name = (
            self.config.model
            or self.config.agent_spec
            or self.config.agent_url
            or getattr(agent, "name", "RecoverBenchAgent")
        )

        trajectory = ExecutionTrajectory(
            run_id=self.config.run_id,
            benchmark_version=self.config.benchmark_version,
            task_id=task_id,
            split=task_spec.split.value,
            condition=condition,
            agent_name=agent_name,
            final_status="SUCCESS" if verdict.overall_recovery_correct else "FAILED",
            messages=agent_res.messages,
            tool_calls=tool_calls,
            tool_results=tool_results,
            pair_id=pair_id,
            domain=task_spec.domain.value,
            agent_version=self.config.sdk_version,
            model_name=self.config.model,
            framework="recoverbench_adapter",
            recovery_method=recovery_method_name,
            seed=seed,
            latency_ms=latency_ms,
            token_usage={
                "prompt_tokens": agent_res.prompt_tokens,
                "completion_tokens": agent_res.completion_tokens,
                "total_tokens": agent_res.prompt_tokens + agent_res.completion_tokens,
            },
            fault_visible_observations=[agent_res.error] if agent_res.error else [],
            benchmark_hidden_trace=hidden_trace,
        )
        return trajectory

    def run_benchmark(self, progress_callback: Optional[Callable[[str], None]] = None) -> RunResult:
        """Execute full benchmark schedule: paired CONTROL and FAULT runs across tasks and seeds."""
        tasks = self.resolve_tasks()
        seeds = self.config.seeds
        agent = resolve_agent(
            model=self.config.model,
            agent_spec=self.config.agent_spec,
            agent_url=self.config.agent_url,
        )

        if self.config.dry_run:
            agent_identity = resolve_agent_identity(
                model=self.config.model,
                agent_spec=self.config.agent_spec,
                agent_url=self.config.agent_url,
            )
            dry_run_tasks = []
            for tid in tasks:
                raw_spec = TaskRegistry.get_task_spec(tid)
                pub_spec = PublicTaskSpec.from_task_spec(raw_spec)
                tool_specs = pub_spec.get_tool_specs()
                dry_run_tasks.append({
                    "task_id": tid,
                    "name": pub_spec.name,
                    "domain": pub_spec.domain,
                    "tool_count": len(tool_specs),
                    "tools": pub_spec.tools,
                })

            dry_run_summary = {
                "dry_run": True,
                "status": "VALIDATED",
                "run_id": self.config.run_id,
                "agent_identity": agent_identity,
                "tasks_count": len(tasks),
                "tasks": dry_run_tasks,
                "seeds": self.config.seeds,
                "recovery": self.config.recovery,
                "total_pairs": len(tasks) * len(self.config.seeds),
                "control_rate": 0.0,
                "rsr": 0.0,
                "crsr": None,
                "eor": None,
                "der": 0.0,
                "mer": 0.0,
            }
            return RunResult(
                run_id=self.config.run_id,
                status="DRY_RUN",
                summary=dry_run_summary,
                run_dir=self.run_dir,
                trajectories_path=self.trajectories_path,
                summary_path=self.summary_json_path,
                report_path=self.report_md_path,
            )

        # Write initial manifest and config
        self._write_manifest(tasks)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.config), f, indent=2)

        # Load completed cells if resuming
        completed_cells: Set[str] = set()
        if self.config.resume and os.path.exists(self.trajectories_path):
            with open(self.trajectories_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        k = f"{record.get('task_id')}_{record.get('seed')}_{record.get('condition')}"
                        completed_cells.add(k)
                    except Exception:
                        pass
            if progress_callback:
                progress_callback(f"Resuming run. Found {len(completed_cells)} existing completed trials.")

        # Construct paired work units
        work_units = []
        for task_id in tasks:
            for seed in seeds:
                pair_id = f"pair_{task_id}_s{seed}_{uuid.uuid4().hex[:6]}"
                work_units.append((task_id, seed, pair_id))

        total_trials = len(work_units) * 2
        completed_count = len(completed_cells)

        def _execute_pair(unit: Tuple[str, int, str]) -> Tuple[ExecutionTrajectory, ExecutionTrajectory]:
            task_id, seed, pair_id = unit
            # 1. Control Run
            ctrl_key = f"{task_id}_{seed}_CONTROL"
            if ctrl_key in completed_cells:
                ctrl_traj = None
            else:
                ctrl_traj = self.execute_single_condition(
                    task_id=task_id,
                    condition="CONTROL",
                    seed=seed,
                    pair_id=pair_id,
                    agent=agent,
                    recovery_method_name=self.config.recovery,
                )

            # 2. Fault Run
            fault_key = f"{task_id}_{seed}_FAULT"
            if fault_key in completed_cells:
                fault_traj = None
            else:
                fault_traj = self.execute_single_condition(
                    task_id=task_id,
                    condition="FAULT",
                    seed=seed,
                    pair_id=pair_id,
                    agent=agent,
                    recovery_method_name=self.config.recovery,
                )
            return ctrl_traj, fault_traj

        # Execute units
        with open(self.trajectories_path, "a", encoding="utf-8") as out_f:
            if self.config.workers > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.workers) as executor:
                    futures = {executor.submit(_execute_pair, wu): wu for wu in work_units}
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            ctrl, fault = future.result()
                            if ctrl:
                                out_f.write(ctrl.to_json() + "\n")
                                out_f.flush()
                                completed_count += 1
                            if fault:
                                out_f.write(fault.to_json() + "\n")
                                out_f.flush()
                                completed_count += 1
                            if progress_callback:
                                progress_callback(f"Progress: {completed_count}/{total_trials} runs completed.")
                        except Exception as ex:
                            logger.error(f"Error executing pair: {ex}")
            else:
                for wu in work_units:
                    try:
                        ctrl, fault = _execute_pair(wu)
                        if ctrl:
                            out_f.write(ctrl.to_json() + "\n")
                            out_f.flush()
                            completed_count += 1
                        if fault:
                            out_f.write(fault.to_json() + "\n")
                            out_f.flush()
                            completed_count += 1
                        if progress_callback:
                            progress_callback(f"Progress: {completed_count}/{total_trials} runs completed.")
                    except Exception as ex:
                        logger.error(f"Error executing pair: {ex}")

        # Post-process evaluation metrics offline
        summary = BenchmarkEngine.evaluate_trajectories_file(self.trajectories_path)
        self._write_reports(summary)
        return RunResult(
            run_id=self.config.run_id,
            status="SUCCESS" if summary.get("total_pairs", 0) > 0 else "EMPTY",
            summary=summary,
            run_dir=self.run_dir,
            trajectories_path=self.trajectories_path,
            summary_path=self.summary_json_path,
            report_path=self.report_md_path,
        )

    def _write_manifest(self, tasks: List[str]) -> None:
        agent_identity = resolve_agent_identity(
            model=self.config.model,
            agent_spec=self.config.agent_spec,
            agent_url=self.config.agent_url,
        )
        manifest = {
            "benchmark_name": "RecoverBench",
            "benchmark_version": self.config.benchmark_version,
            "protocol_version": self.config.protocol_version,
            "sdk_version": self.config.sdk_version,
            "run_id": self.config.run_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "git_commit": get_git_commit(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "python_version": platform.python_version(),
            },
            "config": asdict(self.config),
            "agent_identity": agent_identity,
            "tasks": tasks,
            "seeds": self.config.seeds,
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def _write_reports(self, summary: Dict[str, Any]) -> None:
        # Write summary.json
        with open(self.summary_json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Write summary.csv
        with open(self.summary_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value", "Numerator", "Denominator", "Description"])
            writer.writerow(["Control Success Rate", f"{summary['control_rate']:.2%}", summary['control_passed'], summary['total_pairs'], "Failure-free task competence"])
            writer.writerow(["Recovery Success Rate (RSR)", f"{summary['rsr']:.2%}", summary['fault_passed'], summary['total_pairs'], "Unconditional recovery under fault"])
            writer.writerow(["Conditional Recovery Rate (CRSR)", f"{summary['crsr']:.2%}" if summary['crsr'] is not None else "N/A", summary['crsr_passed'], summary['control_passed'], "Recovery conditioned on nominal competence"])
            writer.writerow(["Exactly-Once Semantic Rate (EOR)", f"{summary['eor']:.2%}" if summary['eor'] is not None else "N/A", summary['eor_passed'], summary['control_passed'], "Goal achieved with zero duplicate or missing effects"])
            writer.writerow(["Duplicate Effect Rate (DER)", f"{summary['der']:.2%}", summary['duplicate_effects_count'], summary['total_pairs'], "Trials causing duplicate mutations"])
            writer.writerow(["Missing Effect Rate (MER)", f"{summary['mer']:.2%}", summary['missing_effects_count'], summary['total_pairs'], "Trials with unapplied mutations"])

        # Write report.md
        with open(self.report_md_path, "w", encoding="utf-8") as f:
            f.write(f"# RecoverBench Evaluation Report\n\n")
            f.write(f"**Run ID**: `{self.config.run_id}`  \n")
            f.write(f"**Benchmark Version**: `{self.config.benchmark_version}` (Protocol `{self.config.protocol_version}`)  \n")
            f.write(f"**Date**: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  \n")
            f.write(f"**Evaluated Agent / Model**: `{self.config.model or self.config.agent_spec or self.config.agent_url or 'Agent'}`  \n\n")
            f.write(f"---\n\n")
            f.write(f"## Primary Benchmark Metrics\n\n")
            f.write(f"| Metric | Percentage | Ratio | Description |\n")
            f.write(f"| :--- | :---: | :---: | :--- |\n")
            f.write(f"| **Control Success Rate** | **{summary['control_rate']:.2%}** | {summary['control_passed']} / {summary['total_pairs']} | Failure-free baseline competence (Layer A) |\n")
            f.write(f"| **Recovery Success Rate (RSR)** | **{summary['rsr']:.2%}** | {summary['fault_passed']} / {summary['total_pairs']} | Unconditional recovery under fault injection |\n")
            crsr_str = f"**{summary['crsr']:.2%}**" if summary['crsr'] is not None else "N/A"
            f.write(f"| **Conditional Recovery (CRSR)** | {crsr_str} | {summary['crsr_passed']} / {summary['control_passed']} | Recovery conditioned on demonstrated competence |\n")
            eor_str = f"**{summary['eor']:.2%}**" if summary['eor'] is not None else "N/A"
            f.write(f"| **Exactly-Once Rate (EOR)** | {eor_str} | {summary['eor_passed']} / {summary['control_passed']} | Required effects satisfied with zero duplicates |\n")
            f.write(f"| **Duplicate Effect Rate (DER)** | **{summary['der']:.2%}** | {summary['duplicate_effects_count']} / {summary['total_pairs']} | Trials committing duplicate side effects |\n")
            f.write(f"| **Missing Effect Rate (MER)** | **{summary['mer']:.2%}** | {summary['missing_effects_count']} / {summary['total_pairs']} | Trials failing to commit required mutations |\n\n")

            if summary.get("task_breakdown"):
                f.write(f"## Task-Level Performance Breakdown\n\n")
                f.write(f"| Task ID | Domain | Pairs | Control | Fault | CRSR | DER |\n")
                f.write(f"| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n")
                for tid, tinfo in summary["task_breakdown"].items():
                    c_str = f"{tinfo['control_rate']:.1%}"
                    f_str = f"{tinfo['fault_rate']:.1%}"
                    cr_str = f"{tinfo['crsr']:.1%}" if tinfo['crsr'] is not None else "N/A"
                    d_str = f"{tinfo['der']:.1%}"
                    f.write(f"| `{tid}` | {tinfo.get('domain', '')} | {tinfo['total_pairs']} | {c_str} | {f_str} | {cr_str} | {d_str} |\n")

    @classmethod
    def evaluate_trajectories_file(cls, path_or_dir: str) -> Dict[str, Any]:
        """Offline evaluation: recomputes all metrics directly from trajectory records without model calls."""
        if os.path.isdir(path_or_dir):
            file_path = os.path.join(path_or_dir, "trajectories.jsonl")
            if not os.path.exists(file_path):
                # Check for subdirectories containing trajectories.jsonl (e.g. run_*)
                for entry in sorted(os.listdir(path_or_dir), reverse=True):
                    sub_p = os.path.join(path_or_dir, entry)
                    if os.path.isdir(sub_p):
                        cand = os.path.join(sub_p, "trajectories.jsonl")
                        if os.path.exists(cand):
                            file_path = cand
                            break
                if not os.path.exists(file_path):
                    # Search for any jsonl
                    candidates = [f for f in os.listdir(path_or_dir) if f.endswith(".jsonl")]
                    if candidates:
                        file_path = os.path.join(path_or_dir, candidates[0])
                    else:
                        raise FileNotFoundError(f"No trajectory .jsonl found in directory '{path_or_dir}'")
        else:
            file_path = path_or_dir

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Trajectory file '{file_path}' does not exist.")

        # Group records by pair_id or (task_id, seed)
        ctrl_map: Dict[str, Dict[str, Any]] = {}
        fault_map: Dict[str, Dict[str, Any]] = {}
        paired_keys: Set[str] = set()

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue

                # Handle legacy RB-3 paired logs vs canonical trajectory format
                if "pair_id" in record and "verdict" in record and "ctrl_benchmark_hidden" in record:
                    # Legacy RB-3 JSONL line
                    pid = record["pair_id"]
                    v = record["verdict"]
                    ctrl_map[pid] = {
                        "task_id": v["task_id"],
                        "domain": v["domain"],
                        "success": v["ctrl_success"],
                        "oracle_verdict": record["ctrl_benchmark_hidden"]["oracle_verdict"],
                    }
                    fault_map[pid] = {
                        "task_id": v["task_id"],
                        "domain": v["domain"],
                        "success": v["fault_success"],
                        "oracle_verdict": record["fault_benchmark_hidden"]["oracle_verdict"],
                    }
                    paired_keys.add(pid)
                else:
                    # Standard ExecutionTrajectory format
                    tid = record.get("task_id")
                    seed = record.get("seed", 0)
                    pid = record.get("pair_id") or f"{tid}_s{seed}"
                    paired_keys.add(pid)

                    cond = record.get("condition", "CONTROL").upper()
                    is_success = record.get("final_status") == "SUCCESS"
                    hidden = record.get("benchmark_hidden_trace") or {}
                    overdict = hidden.get("oracle_verdict") or {"overall_success": is_success}

                    data = {
                        "task_id": tid,
                        "domain": record.get("domain", "general"),
                        "success": is_success,
                        "oracle_verdict": overdict,
                    }
                    if cond == "CONTROL":
                        ctrl_map[pid] = data
                    else:
                        fault_map[pid] = data

        total_pairs = len(paired_keys)
        if total_pairs == 0:
            return {"error": "No valid execution pairs found in trajectory file."}

        control_passed = 0
        fault_passed = 0
        crsr_passed = 0
        eor_passed = 0
        duplicate_effects_count = 0
        missing_effects_count = 0

        task_breakdown: Dict[str, Dict[str, Any]] = {}

        for pid in paired_keys:
            ctrl = ctrl_map.get(pid)
            fault = fault_map.get(pid)

            ctrl_succ = ctrl.get("success", False) if ctrl else False
            fault_succ = fault.get("success", False) if fault else False

            tid = (ctrl.get("task_id") if ctrl else None) or (fault.get("task_id") if fault else "unknown")
            dom = (ctrl.get("domain") if ctrl else None) or (fault.get("domain") if fault else "general")

            if tid not in task_breakdown:
                task_breakdown[tid] = {
                    "domain": dom,
                    "total_pairs": 0,
                    "control_passed": 0,
                    "fault_passed": 0,
                    "crsr_passed": 0,
                    "eor_passed": 0,
                    "duplicate_count": 0,
                }
            task_breakdown[tid]["total_pairs"] += 1

            if ctrl_succ:
                control_passed += 1
                task_breakdown[tid]["control_passed"] += 1

            if fault_succ:
                fault_passed += 1
                task_breakdown[tid]["fault_passed"] += 1

            if ctrl_succ and fault_succ:
                crsr_passed += 1
                task_breakdown[tid]["crsr_passed"] += 1

            # Check side effects from oracle verdict if available
            if fault:
                ov = fault.get("oracle_verdict", {})
                dups = ov.get("duplicate_effects_count", 0)
                miss = ov.get("missing_effects_count", 0)
                if dups > 0:
                    duplicate_effects_count += 1
                    task_breakdown[tid]["duplicate_count"] += 1
                if miss > 0:
                    missing_effects_count += 1
                # EOR definition: goal satisfied + final state correct + required effects satisfied + no duplicate mutations
                if ctrl_succ and fault_succ and dups == 0 and miss == 0:
                    eor_passed += 1
                    task_breakdown[tid]["eor_passed"] += 1

        control_rate = control_passed / total_pairs if total_pairs > 0 else 0.0
        rsr = fault_passed / total_pairs if total_pairs > 0 else 0.0
        crsr = (crsr_passed / control_passed) if control_passed > 0 else None
        eor = (eor_passed / control_passed) if control_passed > 0 else None
        der = duplicate_effects_count / total_pairs if total_pairs > 0 else 0.0
        mer = missing_effects_count / total_pairs if total_pairs > 0 else 0.0

        for tid, tinfo in task_breakdown.items():
            t_pairs = tinfo["total_pairs"]
            t_ctrl = tinfo["control_passed"]
            tinfo["control_rate"] = t_ctrl / t_pairs if t_pairs > 0 else 0.0
            tinfo["fault_rate"] = tinfo["fault_passed"] / t_pairs if t_pairs > 0 else 0.0
            tinfo["crsr"] = (tinfo["crsr_passed"] / t_ctrl) if t_ctrl > 0 else None
            tinfo["der"] = tinfo["duplicate_count"] / t_pairs if t_pairs > 0 else 0.0

        return {
            "total_pairs": total_pairs,
            "control_passed": control_passed,
            "fault_passed": fault_passed,
            "crsr_passed": crsr_passed,
            "eor_passed": eor_passed,
            "duplicate_effects_count": duplicate_effects_count,
            "missing_effects_count": missing_effects_count,
            "control_rate": control_rate,
            "rsr": rsr,
            "crsr": crsr,
            "eor": eor,
            "der": der,
            "mer": mer,
            "task_breakdown": task_breakdown,
        }
