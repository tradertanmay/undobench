"""Trajectory serialization and schema validation for RecoverBench."""

from __future__ import annotations
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionTrajectory:
    """Standardized canonical trajectory record conforming to RECOVERBENCH_TRAJECTORY_SCHEMA_V1."""
    run_id: str
    benchmark_version: str
    task_id: str
    split: str
    condition: str  # "CONTROL" or "FAULT"
    agent_name: str
    final_status: str  # "SUCCESS" or "FAILED"
    messages: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    pair_id: Optional[str] = None
    domain: Optional[str] = None
    agent_version: str = "1.0.0"
    model_name: Optional[str] = None
    model_digest: Optional[str] = None
    framework: Optional[str] = None
    recovery_method: Optional[str] = None
    seed: Optional[int] = None
    latency_ms: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    fault_visible_observations: List[str] = field(default_factory=list)
    benchmark_hidden_trace: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionTrajectory:
        return cls(
            run_id=data.get("run_id", ""),
            benchmark_version=data.get("benchmark_version", "1.0.1"),
            task_id=data.get("task_id", ""),
            split=data.get("split", "dev"),
            condition=data.get("condition", "CONTROL"),
            agent_name=data.get("agent_name", "unknown"),
            final_status=data.get("final_status", "SUCCESS"),
            messages=data.get("messages", []),
            tool_calls=data.get("tool_calls", []),
            tool_results=data.get("tool_results", []),
            pair_id=data.get("pair_id"),
            domain=data.get("domain"),
            agent_version=data.get("agent_version", "1.0.0"),
            model_name=data.get("model_name"),
            model_digest=data.get("model_digest"),
            framework=data.get("framework"),
            recovery_method=data.get("recovery_method"),
            seed=data.get("seed"),
            latency_ms=data.get("latency_ms", 0.0),
            token_usage=data.get("token_usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            fault_visible_observations=data.get("fault_visible_observations", []),
            benchmark_hidden_trace=data.get("benchmark_hidden_trace"),
        )


def validate_trajectory(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a trajectory record against required fields."""
    errors = []
    required_fields = [
        "run_id",
        "benchmark_version",
        "task_id",
        "split",
        "condition",
        "agent_name",
        "final_status",
        "messages",
        "tool_calls",
    ]
    for rf in required_fields:
        if rf not in data:
            errors.append(f"Missing required field: '{rf}'")
    
    if "condition" in data and data["condition"] not in ["CONTROL", "FAULT"]:
        errors.append(f"Invalid condition '{data['condition']}'; must be 'CONTROL' or 'FAULT'")

    if "final_status" in data and data["final_status"] not in ["SUCCESS", "FAILED"]:
        errors.append(f"Invalid final_status '{data['final_status']}'; must be 'SUCCESS' or 'FAILED'")

    return len(errors) == 0, errors
