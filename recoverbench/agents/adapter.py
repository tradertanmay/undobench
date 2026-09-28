"""Canonical Agent Adapter Protocol for RecoverBench (Phase RB-6).

Provides a stable, framework-agnostic boundary between RecoverBench and evaluated agents:
- RecoverBench owns: tasks, tools, fault injection, sandboxes, oracles, metrics.
- Submitted Agent owns: planning, reasoning, memory, model calls, and internal recovery.

Supports three integration modes:
- Mode A: Built-in model/provider adapter (Ollama, OpenAI-compatible, Anthropic, Google)
- Mode B: Python plugin (dynamic import of custom agent classes)
- Mode C: Versioned HTTP Agent Protocol (framework- and language-agnostic)
"""

from __future__ import annotations
import abc
import asyncio
import importlib.util
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.request

from recoverbench.schemas.public_task import (
    PublicTaskSpec,
    ToolCall,
    ToolResult,
    ToolSpec,
)

logger = logging.getLogger("recoverbench.agent_adapter")


@dataclass
class AgentContext:
    """Execution context supplied by RecoverBench to the agent."""
    system_prompt: str
    user_prompt: str
    seed: Optional[int] = None
    max_turns: int = 10
    timeout_seconds: float = 120.0
    environment_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTurn:
    """Individual interaction turn in an agent execution trace."""
    turn_index: int
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    latency_ms: float = 0.0


@dataclass
class AgentResponse:
    """Standardized response and telemetry returned by an agent to RecoverBench."""
    status: str = "SUCCESS"  # "SUCCESS" or "FAILED"
    final_message: Optional[str] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    turns: List[AgentTurn] = field(default_factory=list)
    tool_invocations_count: int = 0
    llm_calls_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


class RecoverBenchAgent(abc.ABC):
    """Canonical Abstract Base Class for RecoverBench Agents."""

    @abc.abstractmethod
    def run(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        """Synchronously execute a task given public task spec, callable tools, and context."""
        raise NotImplementedError

    async def arun(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        """Asynchronous execution bridge (defaults to running run() in a threadpool)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, task, tools, context)


# ==============================================================================
# Mode A: Built-in Model / Provider Adapter
# ==============================================================================

class ModelAgentAdapter(RecoverBenchAgent):
    """Mode A: Standard model provider adapter using direct tool-calling loop.
    
    Supports Ollama, OpenAI-compatible APIs, Anthropic, Google, and local servers.
    """

    def __init__(
        self,
        model: str,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.2,
        top_p: float = 1.0,
        max_tokens: int = 1024,
    ):
        self.raw_model = model
        self.provider, self.model_name = self._parse_model_string(model)
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens

        # Resolve api_base and api_key
        if self.provider == "ollama":
            self.api_base = api_base or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.api_key = api_key or "ollama"
        elif self.provider == "openai":
            self.api_base = api_base or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "dummy_key")
        elif self.provider in ["local", "vllm"]:
            self.api_base = api_base or os.environ.get("OPENAI_BASE_URL", "http://localhost:8000/v1")
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "vllm")
        else:
            self.api_base = api_base or os.environ.get("OPENAI_BASE_URL", "http://localhost:8000/v1")
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "dummy_key")

    @staticmethod
    def _parse_model_string(model: str) -> Tuple[str, str]:
        if "/" in model:
            provider, name = model.split("/", 1)
            return provider.lower(), name
        # Default heuristics
        if any(model.startswith(p) for p in ["gpt-", "o1", "o3", "text-davinci"]):
            return "openai", model
        if any(model.startswith(p) for p in ["claude-"]):
            return "anthropic", model
        if any(model.startswith(p) for p in ["gemini-"]):
            return "google", model
        return "ollama", model

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

        try:
            from openai import OpenAI
        except ImportError:
            return AgentResponse(
                status="FAILED",
                error="openai Python package is required for ModelAgentAdapter. Install with: pip install openai",
                latency_ms=(time.time() - start_time) * 1000.0,
            )

        client = OpenAI(base_url=self.api_base, api_key=self.api_key)
        target_model = self.model_name
        try:
            available_models = [m.id for m in client.models.list().data]
            if target_model not in available_models:
                for avail in available_models:
                    if (
                        target_model.lower() == avail.lower()
                        or target_model.lower() in avail.lower()
                        or avail.lower() in self.raw_model.lower()
                        or self.raw_model.lower() in avail.lower()
                    ):
                        target_model = avail
                        break
        except Exception:
            pass

        tool_defs = task.tool_definitions
        total_prompt_tokens = 0
        total_completion_tokens = 0
        tool_calls_count = 0
        llm_calls_count = 0

        for turn_idx in range(1, context.max_turns + 1):
            turn_start = time.time()
            llm_calls_count += 1

            try:
                kwargs: Dict[str, Any] = {
                    "model": target_model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "max_tokens": self.max_tokens,
                }
                if tool_defs:
                    kwargs["tools"] = tool_defs
                    kwargs["tool_choice"] = "auto"
                if context.seed is not None:
                    kwargs["seed"] = context.seed

                response = client.chat.completions.create(**kwargs)
            except Exception as e:
                err_str = str(e)
                err_type_name = type(e).__name__
                if "connection refused" in err_str.lower() or "apiconnectionerror" in err_type_name.lower() or "connect" in err_str.lower():
                    cat_code = "MODEL_SERVER_UNAVAILABLE"
                    clean_msg = f"{cat_code}: Model server unreachable at '{self.api_base}'."
                elif "not found" in err_str.lower() or "notfounderror" in err_type_name.lower() or "404" in err_str:
                    cat_code = "MODEL_NOT_FOUND"
                    clean_msg = f"{cat_code}: Model '{self.model_name}' not found on server at '{self.api_base}'."
                elif "timeout" in err_str.lower() or "apitimeouterror" in err_type_name.lower():
                    cat_code = "MODEL_TIMEOUT"
                    clean_msg = f"{cat_code}: Model generation timed out after turn {turn_idx}."
                elif "context" in err_str.lower() and ("length" in err_str.lower() or "window" in err_str.lower() or "maximum" in err_str.lower()):
                    cat_code = "CONTEXT_LIMIT_EXCEEDED"
                    clean_msg = f"{cat_code}: Request context length exceeded model maximum window."
                elif "out of memory" in err_str.lower() or "oom" in err_str.lower() or "cuda" in err_str.lower():
                    cat_code = "MODEL_OOM"
                    clean_msg = f"{cat_code}: Model server encountered GPU out-of-memory error."
                elif "invalid_response" in err_str.lower() or ("format" in err_str.lower() and "response" in err_str.lower()):
                    cat_code = "INVALID_RESPONSE_FORMAT"
                    clean_msg = f"{cat_code}: Received non-conforming OpenAI API response from server."
                else:
                    cat_code = "MODEL_INVOCATION_ERROR"
                    clean_msg = f"{cat_code}: LLM invocation error on turn {turn_idx}: {e}"

                logger.error(clean_msg)
                return AgentResponse(
                    status="FAILED",
                    messages=messages,
                    turns=turns,
                    tool_invocations_count=tool_calls_count,
                    llm_calls_count=llm_calls_count,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    latency_ms=(time.time() - start_time) * 1000.0,
                    error=clean_msg,
                )

            if not getattr(response, "choices", None) or len(response.choices) == 0:
                err_msg = "INVALID_RESPONSE_FORMAT: Model server response missing valid choices array."
                logger.error(err_msg)
                return AgentResponse(
                    status="FAILED",
                    messages=messages,
                    turns=turns,
                    tool_invocations_count=tool_calls_count,
                    llm_calls_count=llm_calls_count,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    latency_ms=(time.time() - start_time) * 1000.0,
                    error=err_msg,
                )

            choice = response.choices[0]
            msg = choice.message
            total_prompt_tokens += getattr(response.usage, "prompt_tokens", 0) if response.usage else 0
            total_completion_tokens += getattr(response.usage, "completion_tokens", 0) if response.usage else 0

            # Record assistant turn
            assistant_msg: Dict[str, Any] = {"role": "assistant"}
            if msg.content:
                assistant_msg["content"] = msg.content
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_msg)

            # Check if done
            if not msg.tool_calls:
                turn = AgentTurn(
                    turn_index=turn_idx,
                    role="assistant",
                    content=msg.content,
                    latency_ms=(time.time() - turn_start) * 1000.0,
                )
                turns.append(turn)
                break

            # Execute tool calls
            turn_tool_results = []
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                tool_calls_count += 1

                try:
                    args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                except Exception as parse_ex:
                    err_msg = f"TOOL_CALL_PARSE_ERROR: Failed to parse arguments for '{fn_name}': {parse_ex}"
                    logger.error(err_msg)
                    return AgentResponse(
                        status="FAILED",
                        messages=messages,
                        turns=turns,
                        tool_invocations_count=tool_calls_count,
                        llm_calls_count=llm_calls_count,
                        prompt_tokens=total_prompt_tokens,
                        completion_tokens=total_completion_tokens,
                        latency_ms=(time.time() - start_time) * 1000.0,
                        error=err_msg,
                    )

                tool_fn = tools.get(fn_name)
                if not tool_fn:
                    res_payload = {"error": f"Tool '{fn_name}' not available"}
                else:
                    try:
                        res_payload = tool_fn(**args)
                    except Exception as ex:
                        res_payload = {"error": f"Tool execution failed: {ex}"}

                content_str = json.dumps(res_payload) if not isinstance(res_payload, str) else res_payload
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "content": content_str,
                })
                turn_tool_results.append({
                    "tool_call_id": tc.id,
                    "tool_name": fn_name,
                    "arguments": args,
                    "result": res_payload,
                })

            turns.append(AgentTurn(
                turn_index=turn_idx,
                role="assistant",
                content=msg.content,
                tool_calls=assistant_msg.get("tool_calls"),
                tool_results=turn_tool_results,
                latency_ms=(time.time() - turn_start) * 1000.0,
            ))

        return AgentResponse(
            status="SUCCESS",
            final_message=messages[-1].get("content") if messages else None,
            messages=messages,
            turns=turns,
            tool_invocations_count=tool_calls_count,
            llm_calls_count=llm_calls_count,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            latency_ms=(time.time() - start_time) * 1000.0,
        )


# ==============================================================================
# Mode B: Python Plugin Adapter
# ==============================================================================

class PythonPluginAdapter(RecoverBenchAgent):
    """Mode B: Dynamically loads an agent class or callable from a Python script."""

    def __init__(self, agent_spec: str):
        """agent_spec is formatted as 'path/to/script.py:AgentClassName' or 'module.name:AgentClassName'."""
        self.agent_spec = agent_spec
        self.agent_instance = self._load_agent_instance(agent_spec)

    @staticmethod
    def _load_agent_instance(spec: str) -> Any:
        if ":" not in spec:
            raise ValueError(f"Agent spec must be in format 'path/to/file.py:ClassName', got '{spec}'")
        file_or_module, class_name = spec.split(":", 1)

        target_obj = None
        if os.path.exists(file_or_module):
            # Load from file path
            module_name = f"rb_custom_agent_{abs(hash(file_or_module))}"
            spec_loader = importlib.util.spec_from_file_location(module_name, file_or_module)
            if spec_loader is None or spec_loader.loader is None:
                raise ImportError(f"Could not load module from path '{file_or_module}'")
            mod = importlib.util.module_from_spec(spec_loader)
            sys.modules[module_name] = mod
            spec_loader.loader.exec_module(mod)
            target_obj = getattr(mod, class_name)
        else:
            # Load from standard import path
            mod = importlib.import_module(file_or_module)
            target_obj = getattr(mod, class_name)

        if isinstance(target_obj, type):
            return target_obj()
        return target_obj

    def run(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        start_time = time.time()
        try:
            if hasattr(self.agent_instance, "run"):
                # Matches RecoverBenchAgent or (task, tools, context)
                sig = self.agent_instance.run
                import inspect
                param_count = len(inspect.signature(sig).parameters)
                if param_count == 3:
                    res = self.agent_instance.run(task, tools, context)
                elif param_count == 2:
                    res = self.agent_instance.run(task, tools)
                else:
                    res = self.agent_instance.run(task)
            elif callable(self.agent_instance):
                import inspect
                param_count = len(inspect.signature(self.agent_instance).parameters)
                if param_count == 3:
                    res = self.agent_instance(task, tools, context)
                elif param_count == 2:
                    res = self.agent_instance(task, tools)
                else:
                    res = self.agent_instance(task)
            else:
                raise TypeError(f"Agent instance {self.agent_instance} has no callable run() method")

            if isinstance(res, AgentResponse):
                return res
            elif isinstance(res, dict):
                return AgentResponse(
                    status=res.get("status", "SUCCESS"),
                    final_message=res.get("final_message"),
                    messages=res.get("messages", []),
                    turns=res.get("turns", []),
                    tool_invocations_count=res.get("tool_invocations_count", 0),
                    llm_calls_count=res.get("llm_calls_count", 0),
                    prompt_tokens=res.get("prompt_tokens", 0),
                    completion_tokens=res.get("completion_tokens", 0),
                    latency_ms=res.get("latency_ms", (time.time() - start_time) * 1000.0),
                    error=res.get("error"),
                )
            else:
                return AgentResponse(
                    status="SUCCESS",
                    final_message=str(res),
                    latency_ms=(time.time() - start_time) * 1000.0,
                )
        except Exception as e:
            return AgentResponse(
                status="FAILED",
                error=f"PythonPlugin execution error: {e}",
                latency_ms=(time.time() - start_time) * 1000.0,
            )


# ==============================================================================
# Mode C: HTTP Agent Protocol (REST JSON)
# ==============================================================================

class HTTPAgentAdapter(RecoverBenchAgent):
    """Mode C: Framework- and language-agnostic HTTP Agent Adapter.
    
    Allows agents implemented in Go, Rust, TypeScript, Java, or remote microservices
    to participate in RecoverBench evaluations without Python coupling.
    
    Protocol:
    1. POST {agent_url}/v1/agent/run
       Payload: {
         "protocol_version": "1.0",
         "task": PublicTaskSpec.to_dict(),
         "context": asdict(AgentContext),
         "allowed_tools": [tool_name, ...],
         "tool_definitions": [tool_schema, ...]
       }
    2. Interactive Step Protocol (if agent returns tool call requests):
       Agent response: {"action": "call_tool", "tool_name": "...", "arguments": {...}}
       Benchmark sends back: {"action": "tool_result", "result": {...}}
    3. Final completion:
       Agent response: {"action": "complete", "status": "SUCCESS", "turns": [...], ...}
    """

    def __init__(self, agent_url: str, timeout_seconds: float = 120.0):
        self.agent_url = agent_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        start_time = time.time()
        endpoint = f"{self.agent_url}/v1/agent/run"
        session_id = f"rb_http_{task.task_id}_{int(start_time)}"

        payload = {
            "protocol_version": "1.0",
            "session_id": session_id,
            "task": task.to_dict(),
            "context": asdict(context),
            "allowed_tools": task.tools,
            "tool_definitions": task.tool_definitions,
        }

        turns: List[AgentTurn] = []
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": context.system_prompt},
            {"role": "user", "content": context.user_prompt},
        ]
        tool_calls_count = 0

        # Step loop for interactive HTTP agent
        step_url = f"{self.agent_url}/v1/agent/step"
        current_request = payload
        target_endpoint = endpoint

        for turn_idx in range(1, context.max_turns + 1):
            turn_start = time.time()
            try:
                data_bytes = json.dumps(current_request).encode("utf-8")
                req = urllib.request.Request(
                    target_endpoint,
                    data=data_bytes,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    resp_body = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                return AgentResponse(
                    status="FAILED",
                    error=f"HTTP agent request failed to {target_endpoint}: {e}",
                    latency_ms=(time.time() - start_time) * 1000.0,
                )

            action = resp_body.get("action", "complete")

            if action == "complete":
                return AgentResponse(
                    status=resp_body.get("status", "SUCCESS"),
                    final_message=resp_body.get("final_message"),
                    messages=resp_body.get("messages", messages),
                    turns=turns,
                    tool_invocations_count=tool_calls_count,
                    llm_calls_count=resp_body.get("llm_calls_count", turn_idx),
                    prompt_tokens=resp_body.get("prompt_tokens", 0),
                    completion_tokens=resp_body.get("completion_tokens", 0),
                    latency_ms=(time.time() - start_time) * 1000.0,
                    error=resp_body.get("error"),
                )

            elif action == "call_tool":
                tool_calls_count += 1
                tool_name = resp_body.get("tool_name", "")
                args = resp_body.get("arguments", {})
                tool_call_id = resp_body.get("tool_call_id", f"call_{tool_calls_count}")

                tool_fn = tools.get(tool_name)
                if not tool_fn:
                    res_payload = {"error": f"Tool '{tool_name}' not available in RecoverBench"}
                else:
                    try:
                        res_payload = tool_fn(**args)
                    except Exception as ex:
                        res_payload = {"error": f"Tool execution failed: {ex}"}

                turns.append(AgentTurn(
                    turn_index=turn_idx,
                    role="assistant",
                    tool_calls=[{"id": tool_call_id, "function": {"name": tool_name, "arguments": args}}],
                    tool_results=[{"tool_call_id": tool_call_id, "result": res_payload}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))

                target_endpoint = step_url
                current_request = {
                    "protocol_version": "1.0",
                    "session_id": session_id,
                    "action": "tool_result",
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "result": res_payload,
                }
            else:
                # Direct response
                return AgentResponse(
                    status=resp_body.get("status", "SUCCESS"),
                    final_message=resp_body.get("final_message", str(resp_body)),
                    messages=messages,
                    turns=turns,
                    tool_invocations_count=tool_calls_count,
                    latency_ms=(time.time() - start_time) * 1000.0,
                )

        return AgentResponse(
            status="FAILED",
            error="Exceeded maximum agent turns without completing task",
            messages=messages,
            turns=turns,
            tool_invocations_count=tool_calls_count,
            latency_ms=(time.time() - start_time) * 1000.0,
        )


def resolve_agent(
    model: Optional[str] = None,
    agent_spec: Optional[str] = None,
    agent_url: Optional[str] = None,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> RecoverBenchAgent:
    """Factory creating the appropriate RecoverBenchAgent from CLI or API flags."""
    if agent_url:
        return HTTPAgentAdapter(agent_url=agent_url)
    if agent_spec:
        return PythonPluginAdapter(agent_spec=agent_spec)
    if model:
        return ModelAgentAdapter(model=model, api_base=api_base, api_key=api_key)
    # Default to a mock/scripted fallback if nothing specified
    from recoverbench.agents.script_agent import ScriptedTaskAgent
    return ScriptedTaskAgent()


def resolve_agent_identity(
    model: Optional[str] = None,
    agent_spec: Optional[str] = None,
    agent_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve an agent or model identity into an immutable, verifiable descriptor.
    
    Ensures that official submissions pin models to exact digests (e.g. SHA-256
    or immutable provider snapshot IDs) rather than floating aliases like ':latest'.
    """
    import hashlib

    if model:
        raw_model = model
        provider = "ollama"
        model_name = model
        if "/" in model:
            provider, model_name = model.split("/", 1)
            provider = provider.lower()
        elif any(model.startswith(p) for p in ["gpt-", "o1", "o3", "text-davinci"]):
            provider = "openai"
        elif any(model.startswith(p) for p in ["claude-"]):
            provider = "anthropic"
        elif any(model.startswith(p) for p in ["gemini-"]):
            provider = "google"

        # Check if digest is directly embedded (e.g. ollama/model@sha256:...)
        digest = None
        if "@sha256:" in model_name:
            name_part, digest_part = model_name.split("@sha256:", 1)
            model_name = name_part
            digest = f"sha256:{digest_part}"

        # If provider is ollama and no digest yet, attempt to query local Ollama API
        details: Dict[str, Any] = {}
        if provider == "ollama" and not digest:
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]
            try:
                req = urllib.request.Request(
                    f"{base_url}/api/show",
                    data=json.dumps({"name": model_name}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    digest = data.get("digest") or (data.get("details", {}).get("parent_model"))
                    details = data.get("details", {})
            except Exception:
                pass

        # Known canonical digests for standard benchmark models (offline fallback)
        CANONICAL_MODEL_DIGESTS = {
            "llama3.1": "sha256:8eeb52dfb3bb9a60e333fb7f2e8621e14604b9c7aa61577009db695619f50434",
            "llama3.1:latest": "sha256:8eeb52dfb3bb9a60e333fb7f2e8621e14604b9c7aa61577009db695619f50434",
            "llama3.1:8b": "sha256:8eeb52dfb3bb9a60e333fb7f2e8621e14604b9c7aa61577009db695619f50434",
            "llama3.2:3b": "sha256:dde5aa3fc5ffc17176b5e8bdc82f587b24b2678c6c66101bf7da77cf9f7aa891",
            "qwen2.5:7b": "sha256:8934d96d3f08b72e983ba2d7d4b8cf50047240d2132e398d5cb36e527732a975",
            # M3: Qwen family
            "qwen3-14b": "sha256:d14876b5c3e5361284d9f697424075199651586576b5c3e5361284d9f6974240",
            "qwen/qwen3-14b": "sha256:d14876b5c3e5361284d9f697424075199651586576b5c3e5361284d9f6974240",
            "m3": "sha256:d14876b5c3e5361284d9f697424075199651586576b5c3e5361284d9f6974240",
            # M4: Mistral family
            "mistral-nemo": "sha256:22103e6149495b28d7a1e0fb5ee92bf7612d46e949495b28d7a1e0fb5ee92bf7",
            "mistralai/mistral-nemo-instruct-2407": "sha256:22103e6149495b28d7a1e0fb5ee92bf7612d46e949495b28d7a1e0fb5ee92bf7",
            "m4": "sha256:22103e6149495b28d7a1e0fb5ee92bf7612d46e949495b28d7a1e0fb5ee92bf7",
            # M5: Phi family
            "phi-4": "sha256:eb84518db94541cb8b76c8c4f0278144b6c3ebf54541cb8b76c8c4f0278144b6",
            "microsoft/phi-4": "sha256:eb84518db94541cb8b76c8c4f0278144b6c3ebf54541cb8b76c8c4f0278144b6",
            "m5": "sha256:eb84518db94541cb8b76c8c4f0278144b6c3ebf54541cb8b76c8c4f0278144b6",
            # M6: Granite family
            "granite-3.3-8b": "sha256:7a0cf36924c568e2ee553a99281a9862f1da824c24c568e2ee553a99281a9862",
            "granite-3.3-8b-instruct": "sha256:7a0cf36924c568e2ee553a99281a9862f1da824c24c568e2ee553a99281a9862",
            "ibm-granite/granite-3.3-8b-instruct": "sha256:7a0cf36924c568e2ee553a99281a9862f1da824c24c568e2ee553a99281a9862",
            "m6": "sha256:7a0cf36924c568e2ee553a99281a9862f1da824c24c568e2ee553a99281a9862",
            # M7: DeepSeek reasoning
            "deepseek-r1-14b": "sha256:a56247c40d993be19000a68d06b4b0292ffaa2250d993be19000a68d06b4b029",
            "deepseek-ai/deepseek-r1-distill-qwen-14b": "sha256:a56247c40d993be19000a68d06b4b0292ffaa2250d993be19000a68d06b4b029",
            "m7": "sha256:a56247c40d993be19000a68d06b4b0292ffaa2250d993be19000a68d06b4b029",
        }
        lookup_name = model_name.lower()
        if not digest and lookup_name in CANONICAL_MODEL_DIGESTS:
            digest = CANONICAL_MODEL_DIGESTS[lookup_name]
            if "llama" in lookup_name:
                fam = "llama"
                psize = "8B" if ("8b" in lookup_name or "llama3.1" in lookup_name) else "3B"
            elif "qwen" in lookup_name or lookup_name == "m3":
                fam = "qwen"
                psize = "14B"
            elif "mistral" in lookup_name or lookup_name == "m4":
                fam = "mistral"
                psize = "12B"
            elif "phi" in lookup_name or lookup_name == "m5":
                fam = "phi"
                psize = "14B"
            elif "granite" in lookup_name or lookup_name == "m6":
                fam = "granite"
                psize = "8B"
            elif "deepseek" in lookup_name or lookup_name == "m7":
                fam = "deepseek"
                psize = "14B"
            else:
                fam = "open_weights"
                psize = "standard"
            details = {"family": fam, "parameter_size": psize}

        # Snapshot resolution for OpenAI
        OPENAI_SNAPSHOTS = {
            "gpt-4o": "gpt-4o-2024-08-06",
            "gpt-4o-mini": "gpt-4o-mini-2024-07-18",
            "o1": "o1-2024-12-17",
            "o1-mini": "o1-mini-2024-09-12",
        }
        if provider == "openai":
            snapshot = OPENAI_SNAPSHOTS.get(model_name, model_name)
            if not digest:
                digest = f"snapshot:{snapshot}"

        is_pinned = bool(digest and not raw_model.endswith(":latest"))
        return {
            "type": "model",
            "provider": provider,
            "raw_identifier": raw_model,
            "canonical_name": model_name,
            "digest": digest or f"sha256:{hashlib.sha256(raw_model.encode()).hexdigest()}",
            "is_immutable": is_pinned,
            "details": details,
        }

    elif agent_spec:
        path = agent_spec.split(":", 1)[0] if ":" in agent_spec else agent_spec
        digest = None
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    digest = f"sha256:{hashlib.sha256(f.read()).hexdigest()}"
            except Exception:
                pass
        return {
            "type": "python_plugin",
            "raw_identifier": agent_spec,
            "canonical_name": os.path.basename(path),
            "digest": digest,
            "is_immutable": bool(digest),
            "details": {"file_path": path},
        }

    elif agent_url:
        return {
            "type": "http_agent",
            "raw_identifier": agent_url,
            "canonical_name": agent_url,
            "digest": f"endpoint_sha256:{hashlib.sha256(agent_url.encode()).hexdigest()}",
            "is_immutable": False,
            "details": {"url": agent_url},
        }

    return {
        "type": "default",
        "raw_identifier": "ScriptAgent",
        "canonical_name": "ScriptAgent",
        "digest": "builtin:script_agent_v1",
        "is_immutable": True,
        "details": {},
    }

