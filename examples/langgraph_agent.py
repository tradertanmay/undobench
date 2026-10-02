"""Example 4: LangGraph StateGraph Agent Integration for UndoBench.

Demonstrates wrapping a LangGraph agent into the framework-neutral
UndoBenchAgent interface.

Usage:
    pip install langgraph langchain-core
    undobench run --agent examples/langgraph_agent.py:LangGraphBenchmarkAgent --suite smoke
"""

from __future__ import annotations
import time
from typing import Any, Callable, Dict, List, Optional
from undobench import (
    AgentContext,
    AgentResponse,
    AgentTurn,
    UndoBenchAgent,
)
# PublicTaskSpec imported from undobench


class LangGraphBenchmarkAgent(UndoBenchAgent):
    """LangGraph agent adapter for UndoBench."""

    def __init__(self, model_name: str = "llama3.1:latest"):
        self.model_name = model_name

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
        tool_count = 0
        error_msg = None

        # Check if langgraph is available
        try:
            import langgraph
            # When full langgraph runtime is present, use graph executor
            # For demonstration, execute step-wise loop
        except ImportError:
            pass

        # Execute available public tools to fulfill objective
        for idx, tname in enumerate(task.tools):
            tool_fn = tools.get(tname)
            if not tool_fn:
                continue

            tool_count += 1
            turn_start = time.time()
            try:
                # In real LangGraph, LLM chooses args; here we dispatch default demo invocation
                res = tool_fn()
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"lg_{idx+1}", "function": {"name": tname, "arguments": {}}}],
                    tool_results=[{"tool_call_id": f"lg_{idx+1}", "result": res}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                messages.append({"role": "assistant", "content": f"Invoked {tname} via LangGraph"})
                messages.append({"role": "tool", "name": tname, "content": str(res)})
            except Exception as e:
                error_msg = str(e)
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"lg_{idx+1}", "function": {"name": tname, "arguments": {}}}],
                    tool_results=[{"tool_call_id": f"lg_{idx+1}", "error": error_msg}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                break

        return AgentResponse(
            status="SUCCESS" if error_msg is None else "FAILED",
            final_message=f"LangGraph executed {tool_count} tool calls",
            messages=messages,
            turns=turns,
            tool_invocations_count=tool_count,
            latency_ms=(time.time() - start_time) * 1000.0,
            error=error_msg,
        )
