"""F1: Direct Tool-Calling Agent Harness Adapter."""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
from recoverbench.harness.canonical import (
    coerce_tool_arguments,
    format_return_envelope,
    format_user_prompt,
    get_openai_tools,
    load_canonical_system_prompt,
)
from recoverbench.schemas.task import TaskSpec


@dataclass
class AgentTurnRecord:
    turn_index: int
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_arguments: Optional[Dict[str, Any]] = None
    tool_response: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0


@dataclass
class AgentExecutionResult:
    task_id: str
    model_id: str
    framework_id: str = "direct_tool_calling:v3"
    success_signal: bool = True
    agent_outcome: str = "AGENT_SUCCESS"
    messages: List[Dict[str, Any]] = field(default_factory=list)
    turns: List[AgentTurnRecord] = field(default_factory=list)
    tool_invocations_count: int = 0
    llm_calls_count: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_latency_ms: float = 0.0
    error: Optional[str] = None


class DirectToolCallingAgent:
    """F1: Direct OpenAI-standard tool calling execution loop."""

    def __init__(
        self,
        model_id: str = "llama3.1:latest",
        api_base: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        temperature: float = 0.2,
        top_p: float = 1.0,
        max_output_tokens: int = 512,
        max_agent_turns: int = 6,
        seed: Optional[int] = 42,
        framework_id: str = "direct_tool_calling:v3",
    ):
        self.model_id = model_id
        if OpenAI is None:
            raise ImportError("openai package is required for DirectToolCallingAgent. Install with: pip install openai")
        self.client = OpenAI(base_url=api_base, api_key=api_key)
        self.temperature = temperature
        self.top_p = top_p
        self.max_output_tokens = max_output_tokens
        self.max_agent_turns = max_agent_turns
        self.seed = seed
        self.framework_id = framework_id

    def run(
        self,
        task: TaskSpec,
        tools: Dict[str, Callable[..., Any]],
    ) -> AgentExecutionResult:
        start_time = time.time()
        res = AgentExecutionResult(
            task_id=task.task_id,
            model_id=self.model_id,
            framework_id=self.framework_id,
        )

        system_prompt = load_canonical_system_prompt()
        user_prompt = format_user_prompt(task)
        openai_tools = get_openai_tools(task.allowed_tools)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        turns_record: List[AgentTurnRecord] = []
        turn_count = 0

        while turn_count < self.max_agent_turns:
            turn_count += 1
            call_start = time.time()

            try:
                chat_resp = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    tools=openai_tools if openai_tools else None,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.max_output_tokens,
                    seed=self.seed,
                )
            except Exception as e:
                res.error = f"LLM_CALL_FAILED: {str(e)}"
                res.agent_outcome = "AGENT_PLANNING_FAILURE"
                res.success_signal = False
                break

            call_duration = (time.time() - call_start) * 1000.0
            res.llm_calls_count += 1
            if chat_resp.usage:
                res.total_prompt_tokens += chat_resp.usage.prompt_tokens
                res.total_completion_tokens += chat_resp.usage.completion_tokens

            msg = chat_resp.choices[0].message
            tool_calls = msg.tool_calls

            # Record assistant turn
            assistant_turn = AgentTurnRecord(
                turn_index=turn_count,
                role="assistant",
                content=msg.content,
                tool_calls=[tc.model_dump() for tc in tool_calls] if tool_calls else None,
                latency_ms=call_duration,
            )
            turns_record.append(assistant_turn)

            # If model produced plain text without tool calls, task has terminated
            if not tool_calls:
                messages.append({"role": "assistant", "content": msg.content or ""})
                break

            # Append assistant message with tool calls
            msg_dict: Dict[str, Any] = {"role": "assistant"}
            if msg.content:
                msg_dict["content"] = msg.content
            msg_dict["tool_calls"] = [tc.model_dump() for tc in tool_calls]
            messages.append(msg_dict)

            # Execute tool calls
            for tc in tool_calls:
                res.tool_invocations_count += 1
                fn_name = tc.function.name
                fn_raw_args = tc.function.arguments

                # Parse arguments
                parsed_args: Dict[str, Any] = {}
                arg_error: Optional[Exception] = None
                try:
                    if isinstance(fn_raw_args, str) and fn_raw_args.strip():
                        parsed_args = json.loads(fn_raw_args)
                    elif isinstance(fn_raw_args, dict):
                        parsed_args = fn_raw_args
                    parsed_args = coerce_tool_arguments(fn_name, parsed_args)
                except json.JSONDecodeError as jde:
                    arg_error = jde
                    res.agent_outcome = "AGENT_ARGUMENT_FAILURE"

                if fn_name == "storage_upload" and fn_name not in tools and "put_object" in tools:
                    fn_name = "put_object"

                if arg_error:
                    envelope = format_return_envelope(error=arg_error)
                elif fn_name not in tools:
                    res.agent_outcome = "AGENT_TOOL_SELECTION_FAILURE"
                    envelope = format_return_envelope(
                        error=KeyError(f"Tool '{fn_name}' is not in the allowed tools for this task.")
                    )
                else:
                    tool_fn = tools[fn_name]
                    tool_start = time.time()
                    try:
                        tool_out = tool_fn(**parsed_args)
                        envelope = format_return_envelope(result=tool_out)
                    except Exception as ex:
                        envelope = format_return_envelope(error=ex)
                    tool_latency = (time.time() - tool_start) * 1000.0

                # Record tool execution turn
                tool_turn = AgentTurnRecord(
                    turn_index=turn_count,
                    role="tool",
                    tool_call_id=tc.id,
                    tool_name=fn_name,
                    tool_arguments=parsed_args,
                    tool_response=envelope,
                    latency_ms=tool_latency if "tool_latency" in locals() else 0.0,
                )
                turns_record.append(tool_turn)

                # Feed return envelope back to model
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(envelope),
                })

        if turn_count >= self.max_agent_turns and res.agent_outcome == "AGENT_SUCCESS":
            # Check if agent halted before turn budget
            if turns_record and turns_record[-1].role != "assistant":
                res.agent_outcome = "AGENT_MAX_TURNS"

        res.messages = messages
        res.turns = turns_record
        res.total_latency_ms = (time.time() - start_time) * 1000.0
        return res
