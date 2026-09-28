"""B4: LangGraph-Native Recovery Baseline (Real LangGraph v1.2.11).

Directly leverages LangGraph's StateGraph, MemorySaver checkpointer, and RetryPolicy.
"""

from __future__ import annotations
import logging
from typing import Any, Callable, Dict, Optional, TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from recoverbench.recovery_methods.base import RecoveryMethod
from recoverbench.schemas.task import TaskSpec

logger = logging.getLogger("recoverbench.recovery.langgraph")


class ToolNodeState(TypedDict):
    args: tuple
    kwargs: dict
    result: Any
    error: Optional[str]
    attempts: int


class LangGraphNativeMethod(RecoveryMethod):
    """B4: LangGraph v1.2.11 StateGraph with MemorySaver checkpointer and node RetryPolicy."""

    name = "langgraph_native"
    version = "v1"
    description = "LangGraph v1.2.11 StateGraph node execution with MemorySaver checkpointer and RetryPolicy."

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.retry_count = 0
        self.checkpointer = MemorySaver()

    def wrap_tool(
        self,
        tool_name: str,
        tool_fn: Callable[..., Any],
        task: TaskSpec,
    ) -> Callable[..., Any]:
        retry_policy = RetryPolicy(
            max_attempts=self.max_retries + 1,
            initial_interval=0.01,
            backoff_factor=1.0,
            jitter=False,
            retry_on=(Exception,),
        )

        call_count = [0]

        def node_fn(state: ToolNodeState) -> Dict[str, Any]:
            call_count[0] += 1
            if call_count[0] > 1:
                self.retry_count += 1
                logger.debug(
                    f"[LangGraph-Native] RetryPolicy active for {tool_name} (attempt {call_count[0]})"
                )
            res = tool_fn(*state["args"], **state["kwargs"])
            return {"result": res, "attempts": call_count[0], "error": None}

        builder = StateGraph(ToolNodeState)
        builder.add_node("call_tool", node_fn, retry=retry_policy)
        builder.add_edge(START, "call_tool")
        builder.add_edge("call_tool", END)

        compiled_graph = builder.compile(checkpointer=self.checkpointer)

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            thread_id = f"{task.task_id}_{tool_name}_{id(tool_fn)}"
            config = {"configurable": {"thread_id": thread_id}}
            initial_state: ToolNodeState = {
                "args": args,
                "kwargs": kwargs,
                "result": None,
                "error": None,
                "attempts": 0,
            }

            try:
                final_state = compiled_graph.invoke(initial_state, config=config)
                return final_state["result"]
            except Exception as ex:
                logger.error(f"[LangGraph-Native] All {self.max_retries + 1} attempts exhausted: {ex}")
                raise ex

        return wrapped

    def on_failure_detected(self, error: Exception, context: Dict[str, Any]) -> None:
        pass

    def reset(self) -> None:
        self.retry_count = 0
        self.checkpointer = MemorySaver()
