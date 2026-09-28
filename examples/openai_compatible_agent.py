"""Example 2: OpenAI-Compatible Tool Calling Agent for RecoverBench.

Connects to any OpenAI-compatible API endpoint (OpenAI, vLLM, LiteLLM, Groq, Together, etc.).

Usage:
    export OPENAI_API_KEY="your-key"
    export OPENAI_BASE_URL="https://api.openai.com/v1"
    recoverbench run --agent examples/openai_compatible_agent.py:OpenAICompatibleAgent --task RB-PAY-003
"""

from __future__ import annotations
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional
from openai import OpenAI

from recoverbench.agents.adapter import (
    AgentContext,
    AgentResponse,
    AgentTurn,
    RecoverBenchAgent,
)
from recoverbench.schemas.public_task import PublicTaskSpec


class OpenAICompatibleAgent(RecoverBenchAgent):
    """Generic tool-calling agent using OpenAI-compatible chat completions API."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.2,
    ):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI(
            base_url=base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=api_key or os.environ.get("OPENAI_API_KEY", "dummy_key"),
        )

    def run(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        start_time = time.time()
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": context.system_prompt},
            {"role": "user", "content": context.user_prompt},
        ]
        turns: List[AgentTurn] = []
        prompt_tokens = 0
        comp_tokens = 0
        tool_invocations = 0

        for turn_idx in range(1, context.max_turns + 1):
            turn_start = time.time()
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=task.tool_definitions if task.tool_definitions else None,
                    temperature=self.temperature,
                    seed=context.seed,
                )
            except Exception as e:
                return AgentResponse(
                    status="FAILED",
                    error=f"Model call failed on turn {turn_idx}: {e}",
                    latency_ms=(time.time() - start_time) * 1000.0,
                )

            choice = resp.choices[0]
            msg = choice.message
            if resp.usage:
                prompt_tokens += resp.usage.prompt_tokens
                comp_tokens += resp.usage.completion_tokens

            # Append assistant message
            asst_dict: Dict[str, Any] = {"role": "assistant"}
            if msg.content:
                asst_dict["content"] = msg.content
            if msg.tool_calls:
                asst_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(asst_dict)

            # Check if agent finished without further tool calls
            if not msg.tool_calls:
                turns.append(AgentTurn(
                    turn_index=turn_idx,
                    role="assistant",
                    content=msg.content,
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                break

            # Dispatch tool calls
            turn_results = []
            for tc in msg.tool_calls:
                tool_invocations += 1
                fn_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                except Exception:
                    args = {}

                tool_fn = tools.get(fn_name)
                if not tool_fn:
                    res_val = {"error": f"Tool '{fn_name}' not available"}
                else:
                    try:
                        res_val = tool_fn(**args)
                    except Exception as ex:
                        res_val = {"error": f"Execution error: {ex}"}

                content_str = json.dumps(res_val) if not isinstance(res_val, str) else res_val
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "content": content_str,
                })
                turn_results.append({
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "result": res_val,
                })

            turns.append(AgentTurn(
                turn_index=turn_idx,
                role="assistant",
                content=msg.content,
                tool_calls=asst_dict.get("tool_calls"),
                tool_results=turn_results,
                latency_ms=(time.time() - turn_start) * 1000.0,
            ))

        return AgentResponse(
            status="SUCCESS",
            final_message=messages[-1].get("content") if messages else None,
            messages=messages,
            turns=turns,
            tool_invocations_count=tool_invocations,
            llm_calls_count=len(turns),
            prompt_tokens=prompt_tokens,
            completion_tokens=comp_tokens,
            latency_ms=(time.time() - start_time) * 1000.0,
        )
