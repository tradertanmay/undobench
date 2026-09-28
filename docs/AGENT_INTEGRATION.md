# Bring Your Own Agent in 10 Minutes

RecoverBench provides a framework-neutral integration protocol. Any AI agent—regardless of programming language, orchestration framework, or model provider—can be evaluated without modifying benchmark internals.

---

## 1. Integration Modes Overview

RecoverBench supports four pluggable integration modes:

| Mode | Use Case | Typical Implementation |
| :--- | :--- | :--- |
| **1. Python Adapter** | Custom Python agents, existing research code | Subclass `RecoverBenchAgent` in `my_agent.py` |
| **2. OpenAI-Compatible** | Standard LLM endpoints (vLLM, Ollama, OpenAI) | CLI flag `--model openai/<model_name>` |
| **3. LangGraph Adapter** | Graph-based agents with checkpoints & retry | Subclass `LangGraphAgent` |
| **4. HTTP REST Microservice** | Non-Python agents (Go, Rust, TypeScript, Java) | CLI flag `--agent-url http://localhost:8080` |

---

## 2. Mode 1: Python Agent Adapter

Subclass `recoverbench.agents.adapter.RecoverBenchAgent` and implement the `run()` method:

```python
"""my_custom_agent.py: Example custom agent."""

import time
from typing import Any, Callable, Dict
from recoverbench.agents.adapter import (
    AgentContext,
    AgentResponse,
    AgentTurn,
    RecoverBenchAgent,
)
from recoverbench.schemas.public_task import PublicTaskSpec


class MyCustomAgent(RecoverBenchAgent):
    """Custom agent implementing the RecoverBenchAgent protocol."""

    def __init__(self, name: str = "MyAgent"):
        self.name = name

    def run(
        self,
        task: PublicTaskSpec,
        tools: Dict[str, Callable[..., Any]],
        context: AgentContext,
    ) -> AgentResponse:
        start_time = time.time()
        turns = []
        messages = [
            {"role": "system", "content": context.system_prompt},
            {"role": "user", "content": context.user_prompt},
        ]
        tool_count = 0
        error_msg = None

        # Execute required task tools
        for idx, tool_name in enumerate(task.tools):
            tool_fn = tools.get(tool_name)
            if not tool_fn:
                continue

            tool_count += 1
            turn_start = time.time()

            try:
                # 1. Execute tool call
                result = tool_fn()

                # 2. Record successful turn
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tool_name, "arguments": {}}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "result": result}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
            except Exception as ex:
                # 3. Handle faults safely (e.g. transport timeout or lost ACK)
                error_msg = str(ex)
                turns.append(AgentTurn(
                    turn_index=idx + 1,
                    role="assistant",
                    tool_calls=[{"id": f"call_{idx+1}", "function": {"name": tool_name, "arguments": {}}}],
                    tool_results=[{"tool_call_id": f"call_{idx+1}", "error": error_msg}],
                    latency_ms=(time.time() - turn_start) * 1000.0,
                ))
                # Safely halting or probing prevents duplicate external mutations!
                break

        return AgentResponse(
            status="SUCCESS" if error_msg is None else "FAILED",
            final_message=f"Executed {len(turns)} turns",
            messages=messages,
            turns=turns,
            tool_invocations_count=tool_count,
            latency_ms=(time.time() - start_time) * 1000.0,
            error=error_msg,
        )
```

Run your agent against the benchmark:
```bash
recoverbench run \
    --agent my_custom_agent.py:MyCustomAgent \
    --suite smoke \
    --output runs/my_agent_eval
```

---

## 3. Mode 2: Polyglot HTTP REST Microservice

If your agent is written in **Rust, Go, TypeScript, Java, or C#**, start an HTTP server listening on a local port.

### REST Protocol:
* `POST /run`
  * Request Body:
    ```json
    {
      "task_id": "RB-PAY-003",
      "objective": "...",
      "tools": ["payment_gateway_charge", ...],
      "system_prompt": "...",
      "user_prompt": "...",
      "tool_endpoint": "http://127.0.0.1:51234/call"
    }
    ```
  * Response Body:
    ```json
    {
      "status": "SUCCESS",
      "turns": [...],
      "latency_ms": 1240.5
    }
    ```

Run the benchmark against your HTTP service:
```bash
recoverbench run \
    --agent-url http://localhost:8080 \
    --suite smoke
```
See [examples/http_agent/](examples/http_agent/) for a complete working server example.
