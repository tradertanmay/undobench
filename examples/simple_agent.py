"""simple_agent.py: Minimal zero-dependency agent for RecoverBench.

Runs out-of-the-box without API keys or external model dependencies.
Demonstrates the minimal interface needed to execute benchmark tasks safely.
"""

import time
from typing import Any, Callable, Dict
from recoverbench.agents.adapter import (
    AgentContext,
    AgentResponse,
    AgentTurn,
    RecoverBenchAgent,
)
from recoverbench.schemas.public_task import PublicTaskSpec


class SimpleDeterministicAgent(RecoverBenchAgent):
    """A rule-based deterministic agent with cautious retry suppression."""

    def __init__(self, name: str = "SimpleDeterministicAgent"):
        self.name = name

    def run(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        start_time = time.time()
        turns = []
        messages = [
            {"role": "system", "content": context.system_prompt},
            {"role": "user", "content": context.user_prompt},
        ]
        tool_count = 0
        error_msg = None

        # Execute permissible tools in sequence
        for idx, tool_name in enumerate(task.tools):
            tool_fn = tools.get(tool_name)
            if not tool_fn:
                continue

            tool_count += 1
            turn_start = time.time()

            try:
                # Call tool
                result = tool_fn()
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tool_name, "arguments": {}}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "result": result}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                messages.append({"role": "assistant", "content": f"Called {tool_name}"})
                messages.append({"role": "tool", "name": tool_name, "content": str(result)})
            except Exception as ex:
                error_msg = str(ex)
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tool_name, "arguments": {}}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "error": error_msg}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                # Suppress blind re-execution to protect external state from duplicate mutations
                break

        return AgentResponse(
            status="SUCCESS" if error_msg is None else "FAILED",
            final_message=f"SimpleDeterministicAgent completed with {len(turns)} turns",
            messages=messages,
            turns=turns,
            tool_invocations_count=tool_count,
            latency_ms=(time.time() - start_time) * 1000.0,
            error=error_msg,
        )


if __name__ == "__main__":
    print("SimpleDeterministicAgent class defined and ready.")
