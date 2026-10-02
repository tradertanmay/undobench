"""RecoverBench LLM Evaluation Harness Package."""

from recoverbench.harness.canonical import (
    format_return_envelope,
    format_user_prompt,
    get_openai_tools,
    load_canonical_system_prompt,
    load_canonical_tool_schemas,
    load_task_prompt_template,
)
try:
    from recoverbench.harness.direct_agent import (
        AgentExecutionResult,
        AgentTurnRecord,
        DirectToolCallingAgent,
    )
except ImportError:
    DirectToolCallingAgent = None  # type: ignore

try:
    from recoverbench.harness.langgraph_agent import LangGraphRuntimeAgent
except ImportError:
    LangGraphRuntimeAgent = None  # type: ignore

from recoverbench.harness.paired_runner import (
    PairedExperimentRunner,
    PairedTrialVerdict,
)

__all__ = [
    "load_canonical_system_prompt",
    "load_canonical_tool_schemas",
    "load_task_prompt_template",
    "format_user_prompt",
    "get_openai_tools",
    "format_return_envelope",
    "DirectToolCallingAgent",
    "LangGraphRuntimeAgent",
    "AgentTurnRecord",
    "AgentExecutionResult",
    "PairedExperimentRunner",
    "PairedTrialVerdict",
]
