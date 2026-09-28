# RecoverBench 5-Minute Quickstart

Get RecoverBench running and evaluate your first agent in under 5 minutes.

---

## 1. Installation

```bash
# Clone the repository
git clone https://github.com/tradertanmay/recoverbench.git
cd recoverbench

# Install in editable mode
pip install -e .

# Or install with all optional provider adapters (OpenAI, LangGraph, etc.)
pip install -e ".[all]"
```

---

## 2. Environment Verification

Run the diagnostics doctor to confirm Python version, dependencies, tool contracts, and sandbox isolation:

```bash
recoverbench doctor
```

Expected output ending:
```text
======================================================================
RECOVERBENCH READY
======================================================================
```

---

## 3. Run the Instant Smoke Test (Zero API Keys Needed)

Run the fast deterministic smoke test verifying end-to-end sandbox execution, fault injection, recovery handling, wire-level logging, and state oracles:

```bash
recoverbench smoke
```

---

## 4. Explore Benchmark Workflows

Inspect the 36 multi-turn workflows across 8 enterprise domains:

```bash
# List all operational enterprise domains
recoverbench tasks domains

# List workflows in the developmental split
recoverbench tasks list --split dev

# Show full prompt, parameters, and tools for a specific task
recoverbench tasks show RB-PAY-003
```

---

## 5. Benchmark Your First Agent

### Option A: Minimal Deterministic Python Agent
Run the provided zero-dependency example agent:
```bash
recoverbench run \
    --agent examples/simple_agent.py:SimpleDeterministicAgent \
    --suite smoke \
    --output runs/simple_agent_demo
```

### Option B: Local Ollama Model
```bash
recoverbench run \
    --model ollama/llama3.1:latest \
    --task RB-PAY-003 \
    --recovery naive
```

### Option C: OpenAI-Compatible Endpoint
```bash
export OPENAI_API_KEY="sk-..."
recoverbench run \
    --model openai/gpt-4o-mini \
    --suite smoke \
    --recovery naive
```

---

## 6. Inspect Results and Recompute Metrics

```bash
# Recompute offline metrics from trajectory logs
recoverbench evaluate runs/latest

# Generate Markdown and CSV score reports
recoverbench report runs/latest

# Inspect turn-by-turn dialogue and tool calls
recoverbench inspect runs/latest
```

---

## Next Steps
* Learn how to wrap your own custom agent in [docs/AGENT_INTEGRATION.md](AGENT_INTEGRATION.md).
* Understand the formal evaluation metrics in [docs/METRICS.md](METRICS.md).
* Package and submit your results in [docs/SUBMITTING_RESULTS.md](SUBMITTING_RESULTS.md).
