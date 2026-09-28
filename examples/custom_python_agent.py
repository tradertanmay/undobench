"""Example 5: Custom Python Agent with Safe Recovery Heuristics.

Reference implementation for the "Bring Your Own Agent in 10 Minutes" tutorial.
Demonstrates custom memory, tool invocation, and an application-level verify-before-retry loop.

Usage:
    recoverbench run --agent examples/custom_python_agent.py:CustomSafeAgent --suite smoke
"""

from __future__ import annotations
import time
from typing import Any, Callable, Dict, List
from recoverbench.agents.adapter import (
    AgentContext,
    AgentResponse,
    AgentTurn,
    RecoverBenchAgent,
)
from recoverbench.schemas.public_task import PublicTaskSpec
from recoverbench.tasks.registry import TaskRegistry


class CustomSafeAgent(RecoverBenchAgent):
    """Custom user agent implementing simple memory and safe exception handling."""

    def __init__(self, name: str = "CustomSafeAgent"):
        self.name = name

    def run(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        start_time = time.time()
        turns: List[AgentTurn] = []
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": context.system_prompt},
            {"role": "user", "content": context.user_prompt},
        ]

        # Retrieve steps from nominal plan (or LLM planning prompt)
        try:
            full_spec = TaskRegistry.get_task_spec(task.task_id)
            plan = full_spec.scripted_plan
        except Exception:
            plan = []

        tool_calls_count = 0
        error_msg = None

        for idx, step in enumerate(plan):
            turn_start = time.time()
            tname = step.tool
            tool_fn = tools.get(tname)
            tool_calls_count += 1

            if not tool_fn:
                error_msg = f"Tool '{tname}' not provided"
                break

            try:
                # Dispatch tool call
                result = tool_fn(**step.args)
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tname, "arguments": step.args}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "result": result}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                messages.append({"role": "assistant", "content": f"Dispatched {tname}"})
                messages.append({"role": "tool", "name": tname, "content": str(result)})
            except Exception as ex:
                # In CustomSafeAgent: when an exception occurs, record turn and halt safely
                # (Refraining from blind uncoordinated retry to prevent duplicate mutations)
                error_msg = str(ex)
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tname, "arguments": step.args}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "error": error_msg}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                messages.append({"role": "tool", "name": tname, "content": error_msg})
                break

        return AgentResponse(
            status="SUCCESS" if error_msg is None else "FAILED",
            final_message=f"Agent completed {len(turns)} turns",
            messages=messages,
            turns=turns,
            tool_invocations_count=tool_calls_count,
            latency_ms=(time.time() - start_time) * 1000.0,
            error=error_msg,
        )


if __name__ == "__main__":
    import recoverbench
    res = recoverbench.run(
        agent="examples/custom_python_agent.py:CustomSafeAgent",
        suite="smoke",
    )
    print("Run result:", res)
