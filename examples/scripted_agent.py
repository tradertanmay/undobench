"""Example 1: Deterministic Scripted Agent for RecoverBench.

A minimal, zero-dependency reference implementation conforming to the
RecoverBenchAgent interface. Requires no external model or API keys.

Usage:
    recoverbench run --agent examples/scripted_agent.py:ScriptedReferenceAgent --suite smoke
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


class ScriptedReferenceAgent(RecoverBenchAgent):
    """Reference scripted agent executing nominal task plans deterministically."""

    def __init__(self, name: str = "ScriptedReferenceAgent"):
        self.name = name

    def run(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        start_time = time.time()
        # Look up nominal scripted steps for demonstration
        try:
            internal_spec = TaskRegistry.get_task_spec(task.task_id)
            plan = internal_spec.scripted_plan
        except Exception:
            plan = []

        turns: List[AgentTurn] = []
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": context.system_prompt},
            {"role": "user", "content": context.user_prompt},
        ]
        tool_count = 0
        error_msg = None

        for idx, step in enumerate(plan):
            turn_start = time.time()
            tname = step.tool
            tool_fn = tools.get(tname)
            tool_count += 1

            if not tool_fn:
                error_msg = f"Tool '{tname}' not provided"
                break

            try:
                res = tool_fn(**step.args)
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tname, "arguments": step.args}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "result": res}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                messages.append({"role": "assistant", "content": f"Calling {tname}"})
                messages.append({"role": "tool", "name": tname, "content": str(res)})
            except Exception as ex:
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
            final_message=f"Executed {len(turns)} steps",
            messages=messages,
            turns=turns,
            tool_invocations_count=tool_count,
            latency_ms=(time.time() - start_time) * 1000.0,
            error=error_msg,
        )


if __name__ == "__main__":
    import recoverbench
    res = recoverbench.run(
        agent="examples/scripted_agent.py:ScriptedReferenceAgent",
        suite="smoke",
    )
    print("Smoke Result:", res)
