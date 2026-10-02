"""Example 3: Local Ollama Agent Adapter for UndoBench.

Benchmarks models served locally via Ollama (e.g. Llama 3.1, Qwen 2.5, Mistral)
over the OpenAI-compatible endpoint at http://localhost:11434/v1.

Usage:
    # 1. Start Ollama: ollama run llama3.1
    # 2. Run UndoBench:
    undobench run --agent examples/ollama_agent.py:OllamaLocalAgent --task RB-PAY-003
"""

from __future__ import annotations
import os
from undobench import ModelAgentAdapter


class OllamaLocalAgent(ModelAgentAdapter):
    """Specialized adapter for locally hosted Ollama models."""

    def __init__(
        self,
        model: str = "ollama/llama3.1:latest",
        api_base: str = "http://localhost:11434/v1",
        temperature: float = 0.2,
    ):
        super().__init__(
            model=model,
            api_base=api_base,
            api_key="ollama",
            temperature=temperature,
        )


if __name__ == "__main__":
    import undobench
    res = undobench.run(
        agent="examples/ollama_agent.py:OllamaLocalAgent",
        task="RB-PAY-003",
    )
    print("Ollama Run Result:", res)
