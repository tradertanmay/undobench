"""UndoBench: A Method-Agnostic Benchmark and SDK for AI Agent Recovery Around External Side Effects.

Public Python API:
    import undobench
    
    tasks = undobench.load_tasks(split="dev")
    results = undobench.run(task="RB-PAY-003", model="ollama/llama3.1")
    metrics = undobench.evaluate("runs/my_run")
"""

from __future__ import annotations
import sys
from typing import Any, Dict, List, Optional, Union

# Import and re-export all core functionality from recoverbench
import recoverbench
from recoverbench import (
    load_tasks,
    run,
    evaluate,
    COMPATIBILITY,
)
from recoverbench.agents.adapter import (
    AgentContext,
    AgentResponse,
    AgentTurn,
    RecoverBenchAgent,
    resolve_agent,
)
from recoverbench.engine import (
    BenchmarkEngine,
    BENCHMARK_VERSION,
    PROTOCOL_VERSION,
    RunConfig,
    RunResult,
    SDK_VERSION,
    SMOKE_SUITE_TASKS,
)
from recoverbench.schemas.public_task import (
    PublicTaskSpec,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from recoverbench.tasks.registry import TaskRegistry

# UndoBench primary agent alias
UndoBenchAgent = RecoverBenchAgent

__version__ = SDK_VERSION
__benchmark_version__ = BENCHMARK_VERSION
__protocol_version__ = PROTOCOL_VERSION

__all__ = [
    "load_tasks",
    "run",
    "evaluate",
    "UndoBenchAgent",
    "RecoverBenchAgent",
    "AgentContext",
    "AgentResponse",
    "AgentTurn",
    "BenchmarkEngine",
    "TaskRegistry",
    "PublicTaskSpec",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "RunConfig",
    "RunResult",
    "BENCHMARK_VERSION",
    "PROTOCOL_VERSION",
    "SDK_VERSION",
    "SMOKE_SUITE_TASKS",
    "COMPATIBILITY",
]
