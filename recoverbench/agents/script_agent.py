"""Deterministic Scripted Agent for Phase RB-0 benchmark validation."""

from __future__ import annotations
import logging
import time
from typing import Any, Callable, Dict, List
from recoverbench.agents.base import Agent
from recoverbench.schemas.task import TaskSpec

logger = logging.getLogger("recoverbench.agent.scripted")


class ScriptedAgent(Agent):
    """Deterministic agent executing task steps sequentially for RB-0 benchmark validation."""

    def __init__(self, name: str = "scripted_agent_rb0"):
        self.name = name

    def run_task(
        self,
        task: TaskSpec,
        tools: Dict[str, Callable[..., Any]],
    ) -> Dict[str, Any]:
        executed_steps: List[Dict[str, Any]] = []
        start_time = time.time()
        agent_succeeded = True
        error_msg = None

        for idx, step_plan in enumerate(task.scripted_plan):
            tool_name = step_plan.tool
            if tool_name not in tools:
                raise KeyError(f"Tool '{tool_name}' required by task '{task.task_id}' is not in allowed tools")

            tool_callable = tools[tool_name]
            step_record: Dict[str, Any] = {
                "step_index": idx + 1,
                "tool_name": tool_name,
                "args": step_plan.args,
                "status": "STARTED",
            }

            try:
                call_args = step_plan.args.copy()
                res = tool_callable(**call_args)
                step_record["status"] = "SUCCESS"
                step_record["output"] = res
            except Exception as ex:
                step_record["status"] = "FAILED"
                step_record["error"] = str(ex)
                error_msg = str(ex)
                agent_succeeded = False
                logger.debug(f"[ScriptedAgent] Step {idx+1} failed: {ex}")
                # In RB-0 scripted agent, an unhandled exception ends the forward plan
                executed_steps.append(step_record)
                break

            executed_steps.append(step_record)

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "agent_name": self.name,
            "task_id": task.task_id,
            "succeeded": agent_succeeded,
            "error": error_msg,
            "steps_executed": len(executed_steps),
            "step_records": executed_steps,
            "elapsed_ms": elapsed_ms,
        }


from recoverbench.agents.adapter import AgentContext, AgentResponse, AgentTurn, RecoverBenchAgent
from recoverbench.schemas.public_task import PublicTaskSpec
from recoverbench.tasks.registry import TaskRegistry


class ScriptedTaskAgent(RecoverBenchAgent):
    """Deterministic agent conforming to RecoverBenchAgent interface for zero-API-key smoke runs."""

    def __init__(self, name: str = "scripted_task_agent"):
        self.name = name

    def run(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        start_time = time.time()
        # Retrieve internal task spec to access nominal scripted plan
        try:
            full_spec = TaskRegistry.get_task_spec(task.task_id)
            plan = full_spec.scripted_plan
        except Exception:
            plan = []

        turns: List[AgentTurn] = []
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": context.system_prompt},
            {"role": "user", "content": context.user_prompt},
        ]
        tool_invocations = 0
        error_msg = None

        for idx, step in enumerate(plan):
            turn_start = time.time()
            tool_name = step.tool
            tool_fn = tools.get(tool_name)
            tool_invocations += 1

            if not tool_fn:
                error_msg = f"Tool '{tool_name}' not available"
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tool_name, "arguments": step.args}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "error": error_msg}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                break

            try:
                res = tool_fn(**step.args)
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tool_name, "arguments": step.args}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "result": res}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                messages.append({"role": "assistant", "content": f"Invoking {tool_name}"})
                messages.append({"role": "tool", "name": tool_name, "content": str(res)})
            except Exception as ex:
                error_msg = str(ex)
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tool_name, "arguments": step.args}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "error": error_msg}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                messages.append({"role": "tool", "name": tool_name, "content": error_msg})
                # Under unhandled exceptions, break
                break

        status = "SUCCESS" if error_msg is None else "FAILED"
        return AgentResponse(
            status=status,
            final_message=f"Completed {len(turns)} steps",
            messages=messages,
            turns=turns,
            tool_invocations_count=tool_invocations,
            llm_calls_count=0,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=(time.time() - start_time) * 1000.0,
            error=error_msg,
        )

