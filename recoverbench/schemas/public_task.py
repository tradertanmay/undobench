"""Public Agent-Facing Task Specification Schema for RecoverBench.

Strictly separates PUBLIC agent-visible metadata from EVALUATOR-PRIVATE ground truth
(acceptable final states, oracle assertion predicates, required effect multiplicity, and fault specifications).
"""

from __future__ import annotations
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from recoverbench.harness.canonical import get_openai_tools, load_canonical_tool_schemas
from recoverbench.schemas.task import TaskSpec


@dataclass
class ToolSpec:
    """Formal specification of a tool callable by an agent."""
    name: str
    description: str
    parameters: Dict[str, Any]
    returns: Optional[Dict[str, Any]] = None

    def to_openai_dict(self) -> Dict[str, Any]:
        """Convert to standard OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @classmethod
    def from_openai_dict(cls, data: Dict[str, Any]) -> ToolSpec:
        fn = data.get("function", {})
        return cls(
            name=fn.get("name", ""),
            description=fn.get("description", ""),
            parameters=fn.get("parameters", {}),
            returns=fn.get("returns"),
        )


@dataclass
class ToolCall:
    """Agent tool call request."""
    tool_name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResult:
    """Outcome of a tool invocation."""
    tool_name: str
    output: Any
    call_id: Optional[str] = None
    error: Optional[str] = None
    is_error: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PublicTaskMetadata:
    """Public task classification metadata."""
    complexity: str
    reversibility: str
    observability: str
    idempotency_support: bool
    concurrency_present: bool
    cross_system_transaction: bool
    provenance: str


@dataclass
class PublicTaskSpec:
    """Public agent-facing task specification conforming to Phase RB-6.
    
    Contains strictly public information needed by an agent to plan and execute:
    task objective, allowed tool definitions, and domain context.
    
    Never exposes evaluator-private fields:
    - acceptable_final_states
    - required_effects / forbidden_effects
    - oracle invariants / assertions
    - fault injection schedules / proxy internals
    """
    benchmark_version: str
    task_id: str
    name: str
    split: str
    domain: str
    objective: str
    tools: List[str]
    tool_definitions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_task_spec(cls, spec: TaskSpec, version: str = "V4") -> PublicTaskSpec:
        """Construct a sanitized public task specification from internal TaskSpec."""
        tool_defs = get_openai_tools(spec.allowed_tools, version=version)
        meta = {
            "complexity": spec.complexity.value if hasattr(spec.complexity, "value") else str(spec.complexity),
            "reversibility": spec.reversibility.value if hasattr(spec.reversibility, "value") else str(spec.reversibility),
            "observability": spec.observability.value if hasattr(spec.observability, "value") else str(spec.observability),
            "idempotency_support": spec.idempotency_support,
            "concurrency_present": spec.concurrency_present,
            "cross_system_transaction": spec.cross_system_transaction,
            "provenance": spec.provenance.value if hasattr(spec.provenance, "value") else str(spec.provenance),
        }
        return cls(
            benchmark_version="1.0.1",
            task_id=spec.task_id,
            name=spec.name,
            split=spec.split.value if hasattr(spec.split, "value") else str(spec.split),
            domain=spec.domain.value if hasattr(spec.domain, "value") else str(spec.domain),
            objective=spec.objective,
            tools=list(spec.allowed_tools),
            tool_definitions=tool_defs,
            metadata=meta,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def get_tool_specs(self) -> List[ToolSpec]:
        """Return tool definitions as structured ToolSpec instances."""
        specs: List[ToolSpec] = []
        for tdef in self.tool_definitions:
            if "function" in tdef:
                specs.append(ToolSpec.from_openai_dict(tdef))
            else:
                specs.append(
                    ToolSpec(
                        name=tdef.get("name", ""),
                        description=tdef.get("description", ""),
                        parameters=tdef.get("parameters", {}),
                        returns=tdef.get("returns"),
                    )
                )
        return specs

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PublicTaskSpec:
        return cls(
            benchmark_version=data.get("benchmark_version", "1.0.1"),
            task_id=data["task_id"],
            name=data.get("name", data["task_id"]),
            split=data.get("split", "dev"),
            domain=data.get("domain", "general"),
            objective=data["objective"],
            tools=data.get("tools", []),
            tool_definitions=data.get("tool_definitions", []),
            metadata=data.get("metadata", {}),
        )
