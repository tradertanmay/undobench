"""Benchmark execution runner and orchestrator."""

from __future__ import annotations
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional
from recoverbench.agents.script_agent import ScriptedAgent
from recoverbench.faults.injector import DeterministicFaultInjector
from recoverbench.metrics.evaluator import BenchmarkEvaluator
from recoverbench.oracle.state_oracle import StateOracle
from recoverbench.recovery_methods import RECOVERY_METHOD_REGISTRY, RecoveryMethod
from recoverbench.recovery_methods.applicability import ApplicabilityRegistry
from recoverbench.recovery_methods.naive_retry import NaiveRetryMethod
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.schemas.result import BenchmarkRunResult, TrajectoryRecord
from recoverbench.schemas.task import TaskSpec
from recoverbench.tasks.registry import TaskRegistry

logger = logging.getLogger("recoverbench.runner")


class TestQuarantineError(RuntimeError):
    """Raised when an attempt is made to evaluate recovery methods on frozen TEST tasks without explicit authorization."""
    __test__ = False


class BenchmarkRunner:
    """Orchestrates test executions across tasks, faults, and recovery methods."""

    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        self.trajectories_dir = os.path.join(output_dir, "trajectories")
        os.makedirs(self.trajectories_dir, exist_ok=True)

    def run_trial(
        self,
        task_id: str,
        method_name: str,
        fault_spec: FaultSpec,
        is_control_run: bool = False,
        allow_frozen_test_execution: bool = False,
    ) -> BenchmarkRunResult:
        """Execute a single trial for a task under a specific recovery method and fault condition."""
        # 1. Instantiate clean task, sandbox, and tool proxy
        task_spec, sandbox, proxy_registry = TaskRegistry.load_task(task_id)

        # Enforce TEST quarantine: no recovery method may be evaluated against frozen TEST tasks without explicit authorization
        if task_spec.split.value.lower() == "test" and not allow_frozen_test_execution:
            raise TestQuarantineError(
                f"TEST QUARANTINE ENFORCED: Task '{task_id}' belongs to the FROZEN TEST SET "
                "and is quarantined against recovery method execution during development. "
                "Do not consume the TEST set during development."
            )

        # 2. Instantiate recovery method
        method_cls = RECOVERY_METHOD_REGISTRY.get(method_name.lower())
        if not method_cls:
            raise KeyError(f"Recovery method '{method_name}' not found. Available: {list(RECOVERY_METHOD_REGISTRY.keys())}")
        recovery_method: RecoveryMethod = method_cls()
        recovery_method.reset()

        # 3. Configure fault injector in the tool proxy
        injector = DeterministicFaultInjector(fault_spec=fault_spec)
        proxy_registry.injector = injector
        proxy_registry.reset()

        # 4. Wrap tools with Recovery Method
        wrapped_tools = {}
        for tool_name in task_spec.allowed_tools:
            proxied_fn = proxy_registry.get_proxied_tool(tool_name)
            wrapped_tools[tool_name] = recovery_method.wrap_tool(tool_name, proxied_fn, task_spec)

        # 5. Execute with Scripted Agent for Phase RB-0
        agent = ScriptedAgent()
        start_time = time.time()
        agent_telemetry = agent.run_task(task_spec, wrapped_tools)
        elapsed_ms = (time.time() - start_time) * 1000

        # 6. Evaluate with State & Effect History Oracle
        verdict = StateOracle.evaluate(
            task=task_spec,
            sandbox=sandbox,
            proxy_registry=proxy_registry,
            method_name=recovery_method.name,
            boundary_name=fault_spec.boundary.value,
            perturbation_name=fault_spec.perturbation.value,
            agent_succeeded=agent_telemetry.get("agent_succeeded", True),
            agent_error=agent_telemetry.get("error_msg"),
        )

        run_id = f"run_{uuid.uuid4().hex[:10]}"

        # 7. Write Trajectory Log (JSONL)
        traj_path = os.path.join(self.trajectories_dir, f"{task_id}_{recovery_method.name}_{run_id}.jsonl")
        with open(traj_path, "w", encoding="utf-8") as f:
            for step in agent_telemetry.get("step_records", []):
                rec = TrajectoryRecord(
                    run_id=run_id,
                    task_id=task_id,
                    method=recovery_method.name,
                    step_index=step["step_index"],
                    tool_name=step["tool_name"],
                    arguments=step["args"],
                    output=step.get("output"),
                    status=step["status"],
                    error=step.get("error"),
                )
                f.write(rec.model_dump_json() + "\n")

        # 8. Clean up sandbox
        if hasattr(sandbox, "cleanup"):
            sandbox.cleanup()

        applicability = ApplicabilityRegistry.get_applicability(
            method_name=recovery_method.name,
            task_id=task_id,
            domain=task_spec.domain,
            boundary=fault_spec.boundary,
        )

        return BenchmarkRunResult(
            task_id=task_id,
            domain=task_spec.domain.value,
            split=task_spec.split.value,
            method=recovery_method.name,
            boundary=fault_spec.boundary.value,
            perturbation=fault_spec.perturbation.value,
            is_control_run=is_control_run,
            applicability=applicability.value,
            success=verdict.overall_recovery_correct,
            verdict=verdict,
            primary_failure_classification=verdict.primary_failure_classification,
            secondary_failure_classifications=verdict.secondary_failure_classifications,
            tool_calls_count=len(proxy_registry.effect_log),
            recovery_attempts=getattr(recovery_method, "retry_count", 0),
            duration_ms=elapsed_ms,
        )

    def run_suite(
        self,
        task_ids: List[str],
        recovery_methods: List[str],
        include_controls: bool = True,
        trials: int = 1,
        allow_frozen_test_execution: bool = False,
    ) -> Dict[str, Any]:
        """Execute a full matrix of tasks, methods, and trials, including NO_FAULT controls."""
        all_results: List[BenchmarkRunResult] = []

        for task_id in task_ids:
            spec, _, _ = TaskRegistry.load_task(task_id)

            # Quarantine check
            if spec.split.value.lower() == "test" and not allow_frozen_test_execution:
                raise TestQuarantineError(
                    f"TEST QUARANTINE ENFORCED: Task '{task_id}' belongs to the FROZEN TEST SET "
                    "and is quarantined against recovery method execution during development."
                )

            # Assign designated fault for task from task specification
            active_scenarios = [s for s in spec.supported_fault_scenarios if s.boundary != ExecutionBoundary.NO_FAULT]
            if active_scenarios:
                fs = active_scenarios[0]
                if fs.fault_spec and fs.fault_spec.boundary != ExecutionBoundary.NO_FAULT:
                    designated_fault = fs.fault_spec
                else:
                    designated_fault = FaultSpec(
                        boundary=fs.boundary,
                        perturbation=fs.perturbation,
                        target_tool=fs.target_tool,
                        target_call_index=fs.target_call_index,
                        concurrent_state_delta=fs.concurrent_state_delta,
                    )
            else:
                designated_fault = FaultSpec.from_alias("F2")  # Default Lost-ACK

            for method in recovery_methods:
                # 1. Failure-Free Control (NO_FAULT)
                if include_controls:
                    control_fault = FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)
                    ctrl_res = self.run_trial(
                        task_id, method, control_fault,
                        is_control_run=True,
                        allow_frozen_test_execution=allow_frozen_test_execution,
                    )
                    all_results.append(ctrl_res)

                # 2. Injected Fault Condition (Trials)
                for _ in range(trials):
                    fault_res = self.run_trial(
                        task_id, method, designated_fault,
                        is_control_run=False,
                        allow_frozen_test_execution=allow_frozen_test_execution,
                    )
                    all_results.append(fault_res)

        summary = BenchmarkEvaluator.evaluate_runs(all_results)

        # Save summary JSON
        summary_path = os.path.join(self.output_dir, "eval_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary
