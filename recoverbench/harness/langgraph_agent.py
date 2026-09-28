"""F2: LangGraph Runtime Agent Harness Adapter."""

from __future__ import annotations
import json
import time
from typing import Any, Callable, Dict, List, Optional, TypedDict
try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    MemorySaver = None  # type: ignore
    StateGraph = None   # type: ignore
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
from recoverbench.harness.direct_agent import AgentExecutionResult, AgentTurnRecord
from recoverbench.schemas.task import TaskSpec


class LangGraphAgentState(TypedDict):
    messages: List[Dict[str, Any]]
    turn_count: int
    max_turns: int
    agent_outcome: str
    tool_invocations_count: int
    llm_calls_count: int
    prompt_tokens: int
    completion_tokens: int
    turns_record: List[AgentTurnRecord]
    has_tool_calls: bool
    error: Optional[str]


class LangGraphRuntimeAgent:
    """F2: Production LangGraph 1.2.11 StateGraph agent loop with MemorySaver checkpointing."""

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
        framework_id: str = "langgraph_agent:v3",
    ):
        self.model_id = model_id
        if OpenAI is None:
            raise ImportError("openai package is required for LangGraphAgent. Install with: pip install openai")
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
        system_prompt = load_canonical_system_prompt()
        user_prompt = format_user_prompt(task)
        openai_tools = get_openai_tools(task.allowed_tools)

        # Build StateGraph
        builder = StateGraph(LangGraphAgentState)

        def agent_node(state: LangGraphAgentState) -> Dict[str, Any]:
            turn = state["turn_count"] + 1
            call_start = time.time()

            try:
                chat_resp = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=state["messages"],
                    tools=openai_tools if openai_tools else None,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.max_output_tokens,
                    seed=self.seed,
                )
            except Exception as e:
                return {
                    "error": f"LLM_CALL_FAILED: {str(e)}",
                    "agent_outcome": "AGENT_PLANNING_FAILURE",
                    "has_tool_calls": False,
                    "turn_count": turn,
                }

            call_duration = (time.time() - call_start) * 1000.0
            p_tokens = chat_resp.usage.prompt_tokens if chat_resp.usage else 0
            c_tokens = chat_resp.usage.completion_tokens if chat_resp.usage else 0

            msg = chat_resp.choices[0].message
            tool_calls = msg.tool_calls

            turn_rec = AgentTurnRecord(
                turn_index=turn,
                role="assistant",
                content=msg.content,
                tool_calls=[tc.model_dump() for tc in tool_calls] if tool_calls else None,
                latency_ms=call_duration,
            )

            new_messages = list(state["messages"])
            if not tool_calls:
                new_messages.append({"role": "assistant", "content": msg.content or ""})
                return {
                    "messages": new_messages,
                    "turn_count": turn,
                    "llm_calls_count": state["llm_calls_count"] + 1,
                    "prompt_tokens": state["prompt_tokens"] + p_tokens,
                    "completion_tokens": state["completion_tokens"] + c_tokens,
                    "turns_record": state["turns_record"] + [turn_rec],
                    "has_tool_calls": False,
                }

            msg_dict: Dict[str, Any] = {"role": "assistant"}
            if msg.content:
                msg_dict["content"] = msg.content
            msg_dict["tool_calls"] = [tc.model_dump() for tc in tool_calls]
            new_messages.append(msg_dict)

            return {
                "messages": new_messages,
                "turn_count": turn,
                "llm_calls_count": state["llm_calls_count"] + 1,
                "prompt_tokens": state["prompt_tokens"] + p_tokens,
                "completion_tokens": state["completion_tokens"] + c_tokens,
                "turns_record": state["turns_record"] + [turn_rec],
                "has_tool_calls": True,
            }

        def tool_node(state: LangGraphAgentState) -> Dict[str, Any]:
            last_msg = state["messages"][-1]
            tool_calls = last_msg.get("tool_calls", [])

            new_messages = list(state["messages"])
            new_turns = list(state["turns_record"])
            tool_invocations = state["tool_invocations_count"]
            agent_outcome = state["agent_outcome"]

            for tc in tool_calls:
                tool_invocations += 1
                fn_name = tc["function"]["name"]
                fn_raw_args = tc["function"]["arguments"]

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
                    agent_outcome = "AGENT_ARGUMENT_FAILURE"

                if fn_name == "storage_upload" and fn_name not in tools and "put_object" in tools:
                    fn_name = "put_object"

                if arg_error:
                    envelope = format_return_envelope(error=arg_error)
                elif fn_name not in tools:
                    agent_outcome = "AGENT_TOOL_SELECTION_FAILURE"
                    envelope = format_return_envelope(
                        error=KeyError(f"Tool '{fn_name}' is not in the allowed tools for this task.")
                    )
                else:
                    tool_fn = tools[fn_name]
                    t_start = time.time()
                    try:
                        tool_out = tool_fn(**parsed_args)
                        envelope = format_return_envelope(result=tool_out)
                    except Exception as ex:
                        envelope = format_return_envelope(error=ex)
                    t_lat = (time.time() - t_start) * 1000.0

                tool_turn = AgentTurnRecord(
                    turn_index=state["turn_count"],
                    role="tool",
                    tool_call_id=tc["id"],
                    tool_name=fn_name,
                    tool_arguments=parsed_args,
                    tool_response=envelope,
                    latency_ms=t_lat if "t_lat" in locals() else 0.0,
                )
                new_turns.append(tool_turn)

                new_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(envelope),
                })

            return {
                "messages": new_messages,
                "turns_record": new_turns,
                "tool_invocations_count": tool_invocations,
                "agent_outcome": agent_outcome,
            }

        def route_condition(state: LangGraphAgentState) -> str:
            if state["error"]:
                return END
            if not state["has_tool_calls"]:
                return END
            if state["turn_count"] >= state["max_turns"]:
                return END
            return "tools"

        builder.add_node("agent", agent_node)
        builder.add_node("tools", tool_node)
        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", route_condition, {"tools": "tools", END: END})
        builder.add_edge("tools", "agent")

        checkpointer = MemorySaver()
        app = builder.compile(checkpointer=checkpointer)

        init_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        initial_state: LangGraphAgentState = {
            "messages": init_messages,
            "turn_count": 0,
            "max_turns": self.max_agent_turns,
            "agent_outcome": "AGENT_SUCCESS",
            "tool_invocations_count": 0,
            "llm_calls_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "turns_record": [],
            "has_tool_calls": False,
            "error": None,
        }

        thread_id = f"thread_{task.task_id}_{int(time.time()*1000)}"
        final_state = app.invoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )

        total_latency = (time.time() - start_time) * 1000.0

        outcome = final_state["agent_outcome"]
        if final_state["turn_count"] >= self.max_agent_turns and outcome == "AGENT_SUCCESS":
            if final_state["has_tool_calls"]:
                outcome = "AGENT_MAX_TURNS"

        return AgentExecutionResult(
            task_id=task.task_id,
            model_id=self.model_id,
            framework_id=self.framework_id,
            success_signal=final_state["error"] is None,
            agent_outcome=outcome,
            messages=final_state["messages"],
            turns=final_state["turns_record"],
            tool_invocations_count=final_state["tool_invocations_count"],
            llm_calls_count=final_state["llm_calls_count"],
            total_prompt_tokens=final_state["prompt_tokens"],
            total_completion_tokens=final_state["completion_tokens"],
            total_latency_ms=total_latency,
            error=final_state["error"],
        )
