<p align="center">
  <img src="assets/undobench_banner.png" alt="UndoBench Banner" width="100%">
</p>

# UndoBench: Measuring Recovery Capability and Side-Effect Safety in Tool-Using AI Agents

[![arXiv](https://img.shields.io/badge/arXiv-2610.05622-b31b1b.svg)](https://arxiv.org/abs/2610.05622)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Dataset-yellow.svg)](https://huggingface.co/datasets/TanmaySah/undobench)
[![UndoBench CI](https://img.shields.io/badge/UndoBench%20CI-passing-brightgreen.svg)](https://github.com/tradertanmay/undobench/actions/workflows/ci.yml)
[![Benchmark Version](https://img.shields.io/badge/Benchmark-v1.0.1%20Frozen-blue.svg)](benchmark/manifests/TEST_MANIFEST_V1_0_1.json)
[![Protocol](https://img.shields.io/badge/Protocol-V4-green.svg)](benchmark/protocol_v4/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12%20|%203.13%20|%203.14-blue.svg)](pyproject.toml)

UndoBench is an open benchmark and evaluation framework for measuring recovery capability and side-effect safety in tool-using AI agents under execution failures.

---

## The Central Insight: Task Competence ≠ Recovery Capability

Existing AI agent benchmarks (e.g. SWE-bench, WebArena, ToolBench) evaluate agents primarily under **nominal execution**—testing whether an agent can formulate an API call or resolve a software issue in ideal, error-free environments.

However, real-world software systems fail constantly: network drops, lost acknowledgments, transient database timeouts, and partial API failures occur routinely. When a tool-using agent encounters a transport fault, measuring whether it recovers correctly requires separating two fundamentally different questions:
1. **Did the agent fail because it lacked the domain competence to solve the task?**
2. **Or did it fail because it could not handle the operational transport fault?**

UndoBench introduces **counterfactual paired evaluation**: every workflow is executed twice under identical seeds—once under nominal conditions (**CONTROL**) and once under controlled transport fault injection (**FAULT**). This decouples baseline task planning competence from recovery capability, formalizing **Conditional Recovery Success Rate (CRSR)** as a competence-conditioned recovery metric.

```
       +-----------------------------------------------------------+
       |                  Paired Counterfactual Trial              |
       |                         (Identical Seed)                  |
       +-----------------------------+-----------------------------+
                                     |
                    +----------------+----------------+
                    |                                 |
           [ Nominal CONTROL ]               [ Injected FAULT ]
                    |                                 |
            C_i in {0, 1}                     F_i in {0, 1}
      (Task Competence Oracle)          (Recovery Success Oracle)
                    |                                 |
                    +----------------+----------------+
                                     |
                        +------------v------------+
                        |  CRSR = P(F_i=1 | C_i=1)|
                        |  Evaluates Recovery     |
                        |  Without Confounding    |
                        +-------------------------+
```

---

## Key Benchmark Dimensions

* **36 Multi-Turn Workflows Across 8 Enterprise Domains**:
  * Cloud Infrastructure (blue-green cutovers, traffic shifts)
  * Customer Relationship Management (SLA renewals, tier updates)
  * Relational Databases (DDL schema migrations, dividend allocations)
  * Version Control / Git (cherry-picks, release tag cuts)
  * Incident Messaging (pager alerts, webhook fanouts)
  * Payment Processing (cross-border wires, subscription renewals)
  * Object Storage (bucket replication, atomic object swaps)
  * Enterprise Ticketing (escalation policies, incident routing)
* **Wire-Level Effect-History & State Oracles**: Evaluates not just the final sandbox state, but inspects every committed mutation at the wire level to detect silent duplicate mutations and orphaned transactions.
* **Rigorous Safety Metrics**:
  * **Control Pass Rate ($D/N$)**: Baseline planning competence.
  * **Unconditional RSR ($R/N$)**: Task completion under fault injection.
  * **Conditional Recovery Success Rate (CRSR = $C/D$)**: Recovery success conditioned strictly on nominal competence.
  * **Exactly-Once Semantic Effect Rate (EOR)**: Task completion where the intended semantic effect occurs exactly once, satisfying all goal invariants with zero duplicate or missing semantic effects.
  * **Duplicate Effect Rate (DER)**: Rate of hazardous duplicate mutations (e.g. double wire transfers, duplicate tags).
  * **Missing Effect Rate (MER)**: Rate of abandoned or uncommitted workflow goals.
  * **Unsafe Retry Rate (URR)**: Overall rate of side-effect safety violations.

---

## Evaluated Recovery Baselines

UndoBench provides unified, pluggable baseline wrappers for evaluating diverse recovery paradigms:
* **Naive Retry ($B_0$)**: Blind re-execution upon error (induces duplicate mutations in 53.33% of faulted runs).
* **Checkpoint & Rollback ($B_1$)**: Memory checkpointing with local state rollback.
* **Idempotency Keys ($B_2$)**: End-to-end idempotency key propagation across external calls.
* **Sagas ($B_3$)**: Compensating backward transactions upon unhandled failures.
* **LangGraph Native ($B_4$)**: Production state graph retry policies with memory savers.
* **EvoUndo ($B_5$)**: Journaling reconciler with pre-state witnesses and post-condition probing (evaluated as one baseline among others).
* **Verify-Before-Retry ($B_6$)**: Zero-privilege post-commit containment via non-mutating active probes or cautious abstention.

---

## 5-Minute Quickstart

### 1. Installation

```bash
git clone https://github.com/tradertanmay/undobench.git
cd undobench
pip install -e .
```

### 2. Environment Verification

Verify local environment, sandboxes, tool contracts, and dependencies:
```bash
undobench doctor
```

### 3. Instant Smoke Test (< 2 seconds, Zero API Keys Required)

Execute the canonical smoke test through sandbox instantiation, fault injection, recovery layers, wire-effect logging, and programmatic state oracles:
```bash
undobench smoke
```

### 4. Running Benchmark Evaluations

Evaluate any agent or model family across benchmark splits:
```bash
# Evaluate an OpenAI-compatible endpoint (vLLM, Ollama, OpenAI)
undobench run \
    --model openai/gpt-4o-mini \
    --suite smoke \
    --recovery naive

# Evaluate a custom Python agent
undobench run \
    --agent examples/custom_python_agent.py:CustomAgent \
    --suite smoke \
    --output runs/my_agent_eval
```

### 5. Offline Metric Inspection

Recompute and inspect standardized metrics offline without making any model calls:
```bash
undobench evaluate runs/latest
undobench report runs/latest
```

---

## CLI Overview

| Command | Description |
| :--- | :--- |
| `undobench doctor` | Diagnostic health check for dependencies, sandboxes, and schemas |
| `undobench smoke` | Fast (< 2s) end-to-end verification trial with zero API keys |
| `undobench tasks` | Inspect benchmark tasks, splits (DEV/VAL/TEST), and domains |
| `undobench run` | Execute benchmark evaluation across models, agents, and recovery methods |
| `undobench evaluate` | Offline metric recomputation from trajectory records |
| `undobench report` | Generate standardized `summary.json`, `summary.csv`, and `report.md` |
| `undobench inspect` | Inspect step-by-step turns, tool calls, faults, and oracle assertions |
| `undobench submit` | Package and validate standardized community leaderboard submissions |
| `undobench version` | Print benchmark, protocol, and SDK version information |

---

## Bring Your Own Agent

UndoBench provides a framework-neutral agent interface. Any agent can be benchmarked without modifying benchmark internals:

* **Python Adapter**: Subclass `UndoBenchAgent` in [examples/custom_python_agent.py](examples/custom_python_agent.py).
* **Minimal Deterministic Agent**: Inspect [examples/simple_agent.py](examples/simple_agent.py) for an agent with zero external dependencies.
* **LangGraph Integration**: Inspect [examples/langgraph_agent.py](examples/langgraph_agent.py) for LangGraph state graph agents.
* **OpenAI-Compatible Models**: Use `undobench run --model <model_name>` via [examples/openai_compatible_agent.py](examples/openai_compatible_agent.py).
* **Polyglot HTTP Agents**: Benchmark agents written in **Rust, Go, TypeScript, Java, or C#** over HTTP REST via [examples/http_agent/](examples/http_agent/).

See the [Agent Integration Guide](docs/AGENT_INTEGRATION.md) for full instructions.

---

## Benchmark Immutability & Reproducibility

UndoBench **v1.0.1** is frozen for scientific validity. Community PRs cannot silently alter benchmark tasks or evaluation mechanics:
* **Canonical Frozen Raw Dataset**: `results/rb3c_test_raw.jsonl`
* **Pre-Registered Dataset SHA-256**: `1016768449aae019484130b23fda33456861abeb161a5f8dfbeb16e9e5e9f882`
* **Frozen TEST Task Composite SHA-256**: `42ad17acaf97fcd480b8b152f8fbbc4df98acc54dfadd686c425b826dd69e0d8`

Reproduce all paper metrics offline in seconds:
```bash
undobench evaluate results/rb3c_test_raw.jsonl
python scripts/reproduce_eor.py
```
See [Reproducibility Guide](docs/REPRODUCIBILITY.md) for full details.

---

## Two-Tier Trust Model

* **OPEN_REPRODUCIBLE**: Researchers run UndoBench on their own hardware or inference endpoints, package standardized submission bundles using `undobench submit prepare`, and submit results for public display.
* **OFFICIAL_VERIFIED**: Submissions independently verified on hosted infrastructure using quarantined held-out seeds and tamper-evident sandbox containers.

See [Submitting Results](docs/SUBMITTING_RESULTS.md) for submission instructions and schema specifications.

---

## Citation

```bibtex
@article{undobench2026,
  title={UndoBench: Separating Task Competence from Recovery Capability in Tool-Using AI Agents},
  author={Dolly Sah and Tanmay Sah and Harshul Jain and Tanya Sah},
  journal={arXiv preprint arXiv:2610.05622},
  year={2026},
  url={https://arxiv.org/abs/2610.05622}
}
```

## Licensing Structure

UndoBench uses a dual-licensing model:

| Component | License | Scope |
| :--- | :--- | :--- |
| **Software & SDK Code** | [Apache 2.0](LICENSE) | Python code, runner, engine, CLI, harness, fault injection proxy, adapters (`recoverbench/`, `undobench/`, `examples/`, `tests/`, `scripts/`, `Dockerfile`) |
| **Benchmark Artifacts** | [CC BY 4.0](LICENSE-DATA) | Public task specifications, manifests, protocol specifications, trajectory results (`benchmark/`, `docs/`, `results/`) |

*Task Code Scope (`recoverbench/tasks/`)*: The Python task wrapper code is executable under Apache 2.0, while the underlying task scenarios, objectives, prompts, and evaluation specifications are licensed under Creative Commons Attribution 4.0 International (CC BY 4.0).
