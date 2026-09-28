# RecoverBench: Measuring Recovery Capability and Side-Effect Safety in Tool-Using AI Agents

[![CI](https://github.com/tradertanmay/recoverbench/actions/workflows/ci.yml/badge.svg)](https://github.com/tradertanmay/recoverbench/actions/workflows/ci.yml)
[![Benchmark Version](https://img.shields.io/badge/Benchmark-v1.0.1%20Frozen-blue.svg)](benchmark/manifests/TEST_MANIFEST_V1_0_1.json)
[![Protocol](https://img.shields.io/badge/Protocol-V4-green.svg)](benchmark/protocol_v4/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12%20|%203.13%20|%203.14-blue.svg)](pyproject.toml)

RecoverBench is an open benchmark and evaluation framework for measuring recovery capability and side-effect safety in tool-using AI agents under execution failures.

---

## The Central Insight: Task Competence $
eq$ Recovery Capability

Existing AI agent benchmarks (e.g. SWE-bench, WebArena, ToolBench) evaluate agents primarily under **nominal execution**—testing whether an agent can formulate an API call or resolve a software issue in ideal, error-free environments.

However, real-world software systems fail constantly: network drops, lost acknowledgments, transient database timeouts, and partial API failures occur routinely. When a tool-using agent encounters a transport fault, measuring whether it recovers correctly requires separating two fundamentally different questions:
1. **Did the agent fail because it lacked the domain competence to solve the task?**
2. **Or did it fail because it could not handle the operational transport fault?**

RecoverBench introduces **counterfactual paired evaluation**: every workflow is executed twice under identical random seeds—once under nominal conditions (**CONTROL**) and once under controlled transport fault injection (**FAULT**). This decouples baseline task planning competence from recovery capability, formalizing **Conditional Recovery Success Rate (CRSR)** as a competence-conditioned recovery metric.

```
       +-----------------------------------------------------------+
       |                  Paired Counterfactual Trial              |
       |                   (Identical Random Seed)                 |
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
  * **Exactly-Once Rate (EOR)**: Invariant satisfaction with zero duplicate committed mutations.
  * **Duplicate Effect Rate (DER)**: Rate of hazardous duplicate mutations (e.g. double wire transfers, duplicate tags).
  * **Missing Effect Rate (MER)**: Rate of abandoned or uncommitted workflow goals.
  * **Unsafe Retry Rate (URR)**: Overall rate of side-effect safety violations.

---

## Evaluated Recovery Baselines

RecoverBench provides unified, pluggable baseline wrappers for evaluating diverse recovery paradigms:
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
git clone https://github.com/tradertanmay/recoverbench.git
cd recoverbench
pip install -e .
```

### 2. Environment Verification

Verify local environment, sandboxes, tool contracts, and dependencies:
```bash
recoverbench doctor
```

### 3. Instant Smoke Test (< 2 seconds, Zero API Keys Required)

Execute the canonical smoke test through sandbox instantiation, fault injection, recovery layers, wire-effect logging, and programmatic state oracles:
```bash
recoverbench smoke
```

### 4. Running Benchmark Evaluations

Evaluate any agent or model family across benchmark splits:
```bash
# Evaluate an OpenAI-compatible endpoint (vLLM, Ollama, OpenAI)
recoverbench run \
    --model openai/gpt-4o-mini \
    --suite smoke \
    --recovery naive

# Evaluate a custom Python agent
recoverbench run \
    --agent examples/custom_python_agent.py:CustomAgent \
    --suite smoke \
    --output runs/my_agent_eval
```

### 5. Offline Metric Inspection

Recompute and inspect standardized metrics offline without making any model calls:
```bash
recoverbench evaluate runs/latest
recoverbench report runs/latest
```

---

## CLI Overview

| Command | Description |
| :--- | :--- |
| `recoverbench doctor` | Diagnostic health check for dependencies, sandboxes, and schemas |
| `recoverbench smoke` | Fast (< 2s) end-to-end verification trial with zero API keys |
| `recoverbench tasks` | Inspect benchmark tasks, splits (DEV/VAL/TEST), and domains |
| `recoverbench run` | Execute benchmark evaluation across models, agents, and recovery methods |
| `recoverbench evaluate` | Offline metric recomputation from trajectory records |
| `recoverbench report` | Generate standardized `summary.json`, `summary.csv`, and `report.md` |
| `recoverbench inspect` | Inspect step-by-step turns, tool calls, faults, and oracle assertions |
| `recoverbench submit` | Package and validate standardized community leaderboard submissions |
| `recoverbench version` | Print benchmark, protocol, and SDK version information |

---

## Bring Your Own Agent

RecoverBench provides a framework-neutral agent interface. Any agent can be benchmarked without modifying benchmark internals:

* **Python Adapter**: Subclass `RecoverBenchAgent` in [examples/custom_python_agent.py](examples/custom_python_agent.py).
* **Minimal Deterministic Agent**: Inspect [examples/simple_agent.py](examples/simple_agent.py) for an agent with zero external dependencies.
* **LangGraph Integration**: Inspect [examples/langgraph_agent.py](examples/langgraph_agent.py) for LangGraph state graph agents.
* **OpenAI-Compatible Models**: Use `recoverbench run --model <model_name>` via [examples/openai_compatible_agent.py](examples/openai_compatible_agent.py).
* **Polyglot HTTP Agents**: Benchmark agents written in **Rust, Go, TypeScript, Java, or C#** over HTTP REST via [examples/http_agent/](examples/http_agent/).

See the [Agent Integration Guide](docs/AGENT_INTEGRATION.md) for full instructions.

---

## Benchmark Immutability & Reproducibility

RecoverBench **v1.0.1** is frozen for scientific validity. Community PRs cannot silently alter benchmark tasks or evaluation mechanics:
* **Canonical Frozen Raw Dataset**: `results/rb3c_test_raw.jsonl`
* **Pre-Registered Dataset SHA-256**: `1016768449aae019484130b23fda33456861abeb161a5f8dfbeb16e9e5e9f882`
* **Frozen TEST Task Composite SHA-256**: `42ad17acaf97fcd480b8b152f8fbbc4df98acc54dfadd686c425b826dd69e0d8`

Reproduce all paper metrics offline in seconds:
```bash
recoverbench evaluate results/rb3c_test_raw.jsonl
python scripts/reproduce_eor.py
```
See [Reproducibility Guide](docs/REPRODUCIBILITY.md) for full details.

---

## Two-Tier Trust Model

* **OPEN_REPRODUCIBLE**: Researchers run RecoverBench on their own hardware or inference endpoints, package standardized submission bundles using `recoverbench submit prepare`, and submit results for public display.
* **OFFICIAL_VERIFIED**: Submissions independently verified on hosted infrastructure using quarantined held-out seeds and tamper-evident sandbox containers.

See [Submitting Results](docs/SUBMITTING_RESULTS.md) for submission instructions and schema specifications.

---

## Citation

```bibtex
@article{recoverbench2026,
  title={RecoverBench: Separating Task Competence from Recovery Capability in Tool-Using AI Agents},
  author={RecoverBench Authors},
  journal={Conference Submission},
  year={2026}
}
```

---

## License

RecoverBench is released under the [Apache 2.0 License](LICENSE).
