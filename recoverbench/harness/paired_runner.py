"""Paired Experiment Runner for RecoverBench RB-3 Evaluations."""

from __future__ import annotations
import copy
import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional
from recoverbench.harness.canonical import (
    format_return_envelope,
    format_user_prompt,
    load_canonical_system_prompt,
)
from recoverbench.harness.direct_agent import DirectToolCallingAgent
from recoverbench.harness.langgraph_agent import LangGraphRuntimeAgent
from recoverbench.oracle.state_oracle import StateOracle
from recoverbench.recovery_methods import RECOVERY_METHOD_REGISTRY, RecoveryMethod
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.schemas.task import TaskSpec
from recoverbench.tasks.registry import TaskRegistry


@dataclass
class PairedTrialVerdict:
    pair_id: str
    task_id: str
    domain: str
    model_code: str
    model_id: str
    framework_code: str
    framework_id: str
    recovery_code: str
    recovery_method: str
    trial_index: int
    
    # Layer A: Control (NO_FAULT)
    ctrl_success: bool
    agent_outcome: str
    ctrl_duration_ms: float
    ctrl_prompt_tokens: int
    ctrl_completion_tokens: int
    ctrl_tool_calls: int
    ctrl_llm_calls: int
    
    # Layer B: Fault (Active Injection)
    fault_success: bool
    recovery_outcome: str
    fault_duration_ms: float
    fault_prompt_tokens: int
    fault_completion_tokens: int
    fault_tool_calls: int
    fault_llm_calls: int
    
    # Failure classifications and conditional metrics
    ctrl_failure_class: Optional[str] = None
    fault_failure_class: Optional[str] = None
    is_agent_capable: bool = False
    conditional_recovery_success: Optional[bool] = None

    # Wire Effects Summary (Fault Run)
    committed_mutations: int = 0
    duplicate_effects: int = 0
    missing_effects: int = 0


class PairedExperimentRunner:
    """Manages paired NO_FAULT vs. FAULT executions for RB-3 evaluations."""

    def __init__(
        self,
        output_dir: str = "results",
        trajectories_file: str = "results/rb3a_trajectories.jsonl",
    ):
        self.output_dir = output_dir
        self.trajectories_file = trajectories_file
        os.makedirs(self.output_dir, exist_ok=True)

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

    def _instantiate_agent(
        self,
        framework_code: str,
        model_id: str,
        framework_id: Optional[str] = None,
        api_base: str = "http://localhost:11434/v1",
        temperature: float = 0.2,
        top_p: float = 1.0,
        seed: Optional[int] = 42,
    ) -> Any:
        if framework_code == "F1":
            return DirectToolCallingAgent(
                model_id=model_id,
                api_base=api_base,
                temperature=temperature,
                top_p=top_p,
                seed=seed,
                framework_id=framework_id or "direct_tool_calling:v3",
            )
        elif framework_code == "F2":
            return LangGraphRuntimeAgent(
                model_id=model_id,
                api_base=api_base,
                temperature=temperature,
                top_p=top_p,
                seed=seed,
                framework_id=framework_id or "langgraph_agent:v3",
            )
        else:
            raise ValueError(f"Unknown framework code: {framework_code}")

    def run_single_condition(
        self,
        task_id: str,
        recovery_method_name: str,
        fault_spec: FaultSpec,
        is_control: bool,
        agent_executor: Optional[Any] = None,
        use_scripted: bool = False,
    ) -> Dict[str, Any]:
        """Execute a single trial under a specific fault condition."""
        task_spec, sandbox, proxy_reg = TaskRegistry.load_task(task_id)

        # Configure deterministic fault injector
        proxy_reg.injector.configure(fault_spec)
        proxy_reg.reset()

        # Instantiate recovery method
        if recovery_method_name not in RECOVERY_METHOD_REGISTRY:
            raise ValueError(f"Unknown recovery method '{recovery_method_name}'")
        method_cls = RECOVERY_METHOD_REGISTRY[recovery_method_name]
        recovery_method: RecoveryMethod = method_cls()

        # Wrap tools with recovery substrate
        wrapped_tools: Dict[str, Callable[..., Any]] = {}
        for tool_name in task_spec.allowed_tools:
            proxied_fn = proxy_reg.get_proxied_tool(tool_name)
            wrapped_tools[tool_name] = recovery_method.wrap_tool(tool_name, proxied_fn, task_spec)

        start_time = time.time()
        agent_telemetry: Dict[str, Any] = {}

        if use_scripted:
            # Deterministic scripted shadow path
            step_records = []
            scripted_success = True
            err_msg = None
            for idx, step in enumerate(task_spec.scripted_plan):
                tool_fn = wrapped_tools.get(step.tool)
                if not tool_fn:
                    scripted_success = False
                    err_msg = f"Tool '{step.tool}' not found"
                    break
                try:
                    out = tool_fn(**step.args)
                    step_records.append({"step_index": idx + 1, "tool_name": step.tool, "args": step.args, "output": out, "status": "SUCCESS"})
                except Exception as ex:
                    step_records.append({"step_index": idx + 1, "tool_name": step.tool, "args": step.args, "error": str(ex), "status": "FAILED"})
                    scripted_success = False
                    err_msg = str(ex)
                    break
            elapsed_ms = (time.time() - start_time) * 1000.0
            agent_telemetry = {
                "agent_outcome": "AGENT_SUCCESS" if scripted_success else "AGENT_PLANNING_FAILURE",
                "tool_invocations_count": len(step_records),
                "llm_calls_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "latency_ms": elapsed_ms,
                "messages": [],
                "turns": [],
                "error": err_msg,
            }
        else:
            # LLM Agent execution path
            assert agent_executor is not None
            agent_res = agent_executor.run(task_spec, wrapped_tools)
            agent_telemetry = {
                "agent_outcome": agent_res.agent_outcome,
                "tool_invocations_count": agent_res.tool_invocations_count,
                "llm_calls_count": agent_res.llm_calls_count,
                "prompt_tokens": agent_res.total_prompt_tokens,
                "completion_tokens": agent_res.total_completion_tokens,
                "latency_ms": agent_res.total_latency_ms,
                "messages": agent_res.messages,
                "turns": [asdict(t) for t in agent_res.turns],
                "error": agent_res.error,
            }

        elapsed_ms = (time.time() - start_time) * 1000.0

        # Evaluate external sandbox state and effect log via StateOracle
        verdict = StateOracle.evaluate(
            task=task_spec,
            sandbox=sandbox,
            proxy_registry=proxy_reg,
            method_name=recovery_method.name,
            boundary_name=fault_spec.boundary.value,
            perturbation_name=fault_spec.perturbation.value,
            agent_succeeded=agent_telemetry.get("error") is None,
            agent_error=agent_telemetry.get("error"),
        )

        # Deconstruct Layer A vs Layer B classification
        if is_control:
            if verdict.overall_recovery_correct:
                agent_outcome = "AGENT_SUCCESS"
            elif agent_telemetry.get("agent_outcome") != "AGENT_SUCCESS":
                agent_outcome = agent_telemetry["agent_outcome"]
            elif verdict.missing_effects_count > 0:
                agent_outcome = "AGENT_PREMATURE_TERMINATION"
            else:
                agent_outcome = "AGENT_ARGUMENT_FAILURE"
            recovery_outcome = "CONTROL_RUN"
        else:
            agent_outcome = agent_telemetry.get("agent_outcome", "AGENT_SUCCESS")
            if verdict.overall_recovery_correct:
                recovery_outcome = "SUCCESS"
            else:
                recovery_outcome = verdict.primary_failure_classification or "RECOVERY_FAILURE"

        # Capture hidden benchmark trace
        hidden_trace = {
            "effect_log": [e.to_dict() for e in proxy_reg.effect_log],
            "injection_log": proxy_reg.injector.injection_log,
            "final_state": verdict.final_state,
            "oracle_violations": verdict.violations,
            "oracle_verdict": {
                "success": verdict.overall_recovery_correct,
                "goal_satisfied": verdict.goal_satisfied,
                "final_state_correct": verdict.final_state_correct,
                "invariant_satisfied": verdict.invariant_satisfied,
                "required_effects_satisfied": verdict.required_effects_satisfied,
                "effect_multiplicity_correct": verdict.effect_multiplicity_correct,
                "forbidden_effects_absent": verdict.forbidden_effects_absent,
                "ordering_correct": verdict.ordering_correct,
            },
        }

        # Cleanup sandbox
        if hasattr(sandbox, "cleanup"):
            sandbox.cleanup()

        return {
            "success": verdict.overall_recovery_correct,
            "agent_outcome": agent_outcome,
            "recovery_outcome": recovery_outcome,
            "failure_classification": verdict.primary_failure_classification,
            "duration_ms": elapsed_ms,
            "prompt_tokens": agent_telemetry.get("prompt_tokens", 0),
            "completion_tokens": agent_telemetry.get("completion_tokens", 0),
            "tool_calls": agent_telemetry.get("tool_invocations_count", 0),
            "llm_calls": agent_telemetry.get("llm_calls_count", 0),
            "committed_mutations": verdict.committed_mutation_count,
            "duplicate_effects": verdict.duplicate_effects_count,
            "missing_effects": verdict.missing_effects_count,
            "agent_visible_trace": {
                "messages": agent_telemetry.get("messages", []),
                "turns": agent_telemetry.get("turns", []),
            },
            "benchmark_hidden_trace": hidden_trace,
        }

    def run_paired_trial(
        self,
        task_id: str,
        model_code: str,
        model_id: str,
        framework_code: str,
        framework_id: str,
        recovery_code: str,
        recovery_method: str,
        trial_index: int,
        use_scripted: bool = False,
        seed: Optional[int] = None,
    ) -> PairedTrialVerdict:
        """Run paired NO_FAULT vs FAULT executions under common pair_id."""
        pair_id = f"pair_{task_id}_{model_code}_{framework_code}_{recovery_code}_t{trial_index}_{uuid.uuid4().hex[:6]}"
        task_spec = TaskRegistry.get_task_spec(task_id)

        ctrl_fault = FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)
        active_fault = self._get_active_fault_spec(task_spec)

        agent_executor = None if use_scripted else self._instantiate_agent(framework_code, model_id, framework_id=framework_id, seed=seed)

        # 1. Condition A: NO_FAULT Control (Layer A)
        ctrl_result = self.run_single_condition(
            task_id=task_id,
            recovery_method_name=recovery_method,
            fault_spec=ctrl_fault,
            is_control=True,
            agent_executor=agent_executor,
            use_scripted=use_scripted,
        )

        # 2. Condition B: Injected FAULT (Layer B)
        # Instantiate fresh agent executor with identical seed to match paired stochastic starting state
        agent_executor_fault = None if use_scripted else self._instantiate_agent(framework_code, model_id, framework_id=framework_id, seed=seed)
        fault_result = self.run_single_condition(
            task_id=task_id,
            recovery_method_name=recovery_method,
            fault_spec=active_fault,
            is_control=False,
            agent_executor=agent_executor_fault,
            use_scripted=use_scripted,
        )

        # Evaluate paired competence
        is_capable = (ctrl_result["agent_outcome"] == "AGENT_SUCCESS")
        cr_success: Optional[bool] = None
        if is_capable:
            cr_success = (fault_result["recovery_outcome"] == "SUCCESS")

        verdict = PairedTrialVerdict(
            pair_id=pair_id,
            task_id=task_id,
            domain=task_spec.domain.value,
            model_code=model_code,
            model_id=model_id,
            framework_code=framework_code,
            framework_id=framework_id,
            recovery_code=recovery_code,
            recovery_method=recovery_method,
            trial_index=trial_index,
            ctrl_success=ctrl_result["success"],
            agent_outcome=ctrl_result["agent_outcome"],
            ctrl_duration_ms=ctrl_result["duration_ms"],
            ctrl_prompt_tokens=ctrl_result["prompt_tokens"],
            ctrl_completion_tokens=ctrl_result["completion_tokens"],
            ctrl_tool_calls=ctrl_result["tool_calls"],
            ctrl_llm_calls=ctrl_result["llm_calls"],
            ctrl_failure_class=ctrl_result["failure_classification"],
            fault_success=fault_result["success"],
            recovery_outcome=fault_result["recovery_outcome"],
            fault_duration_ms=fault_result["duration_ms"],
            fault_prompt_tokens=fault_result["prompt_tokens"],
            fault_completion_tokens=fault_result["completion_tokens"],
            fault_tool_calls=fault_result["tool_calls"],
            fault_llm_calls=fault_result["llm_calls"],
            fault_failure_class=fault_result["failure_classification"],
            is_agent_capable=is_capable,
            conditional_recovery_success=cr_success,
            committed_mutations=fault_result["committed_mutations"],
            duplicate_effects=fault_result["duplicate_effects"],
            missing_effects=fault_result["missing_effects"],
        )

        # Append trajectory log to JSONL
        log_entry = {
            "pair_id": pair_id,
            "verdict": asdict(verdict),
            "ctrl_agent_visible": ctrl_result["agent_visible_trace"],
            "ctrl_benchmark_hidden": ctrl_result["benchmark_hidden_trace"],
            "fault_agent_visible": fault_result["agent_visible_trace"],
            "fault_benchmark_hidden": fault_result["benchmark_hidden_trace"],
        }
        with open(self.trajectories_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

        return verdict
