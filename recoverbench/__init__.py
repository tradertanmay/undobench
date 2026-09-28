"""RecoverBench: A Method-Agnostic Benchmark and SDK for AI Agent Recovery Around External Side Effects.

Public Python API:
    import recoverbench
    
    tasks = recoverbench.load_tasks(split="dev")
    results = recoverbench.run(task="RB-PAY-003", model="ollama/llama3.1")
    metrics = recoverbench.evaluate("runs/my_run")
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union

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

__version__ = SDK_VERSION
__benchmark_version__ = BENCHMARK_VERSION
__protocol_version__ = PROTOCOL_VERSION

COMPATIBILITY: Dict[str, str] = {
    "sdk_version": "1.0.0",
    "benchmark_version": "1.0.1",
    "trajectory_schema": "1",
    "submission_schema": "1",
    "agent_protocol": "1",
}


def load_tasks(
    split: Optional[str] = None,
    domain: Optional[str] = None,
    suite: Optional[str] = None,
) -> List[PublicTaskSpec]:
    """Load sanitized public task specifications.
    
    Args:
        split: Task split to load ("dev", "validation", "test").
        domain: Specific domain filter ("payments", "database", etc.).
        suite: Pre-defined suite name ("smoke", "dev", etc.).
        
    Returns:
        List of PublicTaskSpec objects containing public objectives and tools.
    """
    if suite == "smoke":
        tids = list(SMOKE_SUITE_TASKS)
    elif split:
        tids = TaskRegistry.list_task_ids(split=split)
    else:
        tids = TaskRegistry.list_task_ids()

    if domain:
        tids = [
            t for t in tids
            if TaskRegistry.get_task_spec(t).domain.value.lower() == domain.lower()
        ]

    specs = []
    for tid in tids:
        raw_spec = TaskRegistry.get_task_spec(tid)
        specs.append(PublicTaskSpec.from_task_spec(raw_spec))
    return specs


def run(
    model: Optional[str] = None,
    agent: Optional[Any] = None,
    agent_url: Optional[str] = None,
    split: Optional[str] = None,
    suite: Optional[str] = None,
    task: Optional[str] = None,
    recovery: str = "naive",
    workers: int = 1,
    resume: bool = False,
    dry_run: bool = False,
    output_dir: str = "runs",
    run_id: Optional[str] = None,
    seeds: Optional[List[int]] = None,
    allow_frozen_test_execution: bool = False,
) -> RunResult:
    """Execute a RecoverBench evaluation run programmatically.
    
    Args:
        model: Model provider identifier (e.g. "ollama/llama3.1", "openai/gpt-4o").
        agent: Python agent instance, class, or "file.py:AgentClass" spec.
        agent_url: URL to an external HTTP agent server.
        split: Task split ("dev", "validation", "test").
        suite: Suite alias ("smoke", "dev", "validation", "all").
        task: Individual task ID (e.g. "RB-PAY-003").
        recovery: Recovery baseline method to wrap tools with.
        workers: Concurrency count.
        resume: Skip already completed trials in the run directory.
        dry_run: Validate tasks and agent without execution or state mutations.
        output_dir: Root directory for run artifacts.
        run_id: Custom run identifier.
        seeds: List of random seeds (defaults to [42]).
        allow_frozen_test_execution: Flag required to execute quarantined TEST tasks.
        
    Returns:
        RunResult object with status, metrics summary, and artifact paths.
    """
    import datetime
    import uuid

    rid = run_id or f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    agent_spec_str = agent if isinstance(agent, str) else None

    config = RunConfig(
        run_id=rid,
        model=model,
        agent_spec=agent_spec_str,
        agent_url=agent_url,
        split=split,
        suite=suite,
        task_id=task,
        recovery=recovery,
        workers=workers,
        resume=resume,
        dry_run=dry_run,
        output_dir=output_dir,
        seeds=seeds or [42],
        allow_frozen_test_execution=allow_frozen_test_execution,
    )
    engine = BenchmarkEngine(config)
    return engine.run_benchmark()


def evaluate(path_or_dir: str) -> Dict[str, Any]:
    """Recompute all RecoverBench metrics offline from trajectory records.
    
    Args:
        path_or_dir: Path to trajectories.jsonl file or completed run directory.
        
    Returns:
        Summary metrics dictionary including control rate, RSR, CRSR, EOR, DER, and MER.
    """
    return BenchmarkEngine.evaluate_trajectories_file(path_or_dir)


__all__ = [
    "load_tasks",
    "run",
    "evaluate",
    "PublicTaskSpec",
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "RecoverBenchAgent",
    "RunResult",
    "AgentContext",
    "AgentResponse",
    "AgentTurn",
    "COMPATIBILITY",
    "BENCHMARK_VERSION",
    "PROTOCOL_VERSION",
    "SDK_VERSION",
]

