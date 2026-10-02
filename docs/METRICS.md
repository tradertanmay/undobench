# UndoBench Evaluation Metrics Specification

This document provides the formal mathematical definitions, conceptual motivations, and implementation specifications for the UndoBench evaluation metric suite.

---

## 1. Why Nominal Benchmarking Is Insufficient

In nominal benchmarks (e.g. SWE-bench, ToolBench, WebArena), an agent is evaluated on a single task trial:
$$\text{Success}_i \in \{0, 1\}$$

If the agent fails, it is impossible to separate whether:
1. The agent lacked base domain competence (e.g. inability to formulate a SQL query or resolve dependencies).
2. The agent failed to recover from an operational environment fault (e.g. lost acknowledgment or transport timeout).

UndoBench resolves this confounding by evaluating every task as a **paired counterfactual trial** under identical initial conditions and random seeds:
- Nominal Control Trial: $C_i \in \{0, 1\}$
- Fault-Injected Trial: $F_i \in \{0, 1\}$

---

## 2. Core Benchmark Metrics

### 2.1 Control Pass Rate ($D/N$)
The proportion of workflows that the agent successfully solves under ideal, error-free conditions:
$$\text{Control} = \frac{1}{N} \sum_{i=1}^N C_i = \frac{D}{N}$$
where $N$ is the total number of evaluation trials and $D = \sum_{i=1}^N C_i$ is the number of capable trials.

### 2.2 Unconditional Recovery Success Rate (RSR)
The raw task completion rate under fault injection, without conditioning on whether the agent could solve the task nominally:
$$\text{RSR} = \frac{1}{N} \sum_{i=1}^N F_i = \frac{R}{N}$$
When nominal competence is low, unconditional RSR mixes nominal planning failures with recovery behavior, making it difficult to interpret as a pure recovery measure.

### 2.3 Conditional Recovery Success Rate (CRSR)
The primary recovery performance metric in UndoBench. CRSR evaluates recovery success **conditioned strictly on nominal task competence**:
$$\text{CRSR} = P(F_i = 1 \mid C_i = 1) = \frac{\sum_{i=1}^N C_i \cdot F_i}{\sum_{i=1}^N C_i} = \frac{C}{D}$$
where $C$ is the count of trials that succeeded under both control and faulted regimes.
* When $D > 0$, CRSR measures the probability that an agent that *knows how to solve the task* survives an operational fault.
* When $D = 0$ (the agent failed every control run for that task), CRSR is mathematically undefined ($0/0$) and reported as `N/A`.

---

## 3. Side-Effect Safety Metrics

Achieving a task goal is dangerous if the agent leaves duplicate external mutations behind. UndoBench inspects wire-level effect traces to compute four formal safety metrics:

### 3.1 Duplicate Effect Rate (DER)
The proportion of faulted trials that committed one or more duplicate external side effects:
$$\text{DER} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}[\text{committed mutations contains duplicate effects}]$$
*Example*: Retrying a subscription renewal without an idempotency key commits two charges in Stripe, producing $\text{DER} = 1.0$.

### 3.2 Missing Effect Rate (MER)
The proportion of faulted trials that aborted prematurely and left one or more required workflow goals uncommitted:
$$\text{MER} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}[\text{required goal invariants unfulfilled}]$$

### 3.3 Unsafe Retry Rate (URR)
The comprehensive side-effect safety violation rate:
$$\text{URR} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}[\text{DER}_i > 0 \lor \text{MER}_i > 0]$$

### 3.4 Exactly-Once Semantic Effect Rate (EOR)
The gold standard of safe distributed recovery. EOR evaluates whether the task's required semantic effect occurred **exactly once** under fault injection, subject to the benchmark's state and effect-history correctness criteria. A trial satisfies EOR if and only if:
1. The nominal task goal is satisfied under fault injection ($F_i = 1$).
2. The intended semantic effect occurs with exact multiplicity ($N_{\text{sem}} = 1$ or target multiplicity).
3. Zero duplicate semantic effects were induced ($\text{DER}_i = 0$).
4. Zero missing required effects remain unfulfilled ($\text{MER}_i = 0$).

$$\text{EOR}_{\text{uncond}} = \frac{1}{N} \sum_{i=1}^N \mathbf{1}[F_i = 1 \land \text{DER}_i = 0 \land \text{MER}_i = 0]$$

Conditioned on nominal competence ($C_i = 1$, where $D = \sum C_i$ is capable pairs):
$$\text{EOR}_{\text{cond}} = \frac{\sum_{i=1}^N C_i \cdot \mathbf{1}[F_i = 1 \land \text{DER}_i = 0 \land \text{MER}_i = 0]}{D}$$


---

## 4. The Three Execution Layers: Invocations, Mutations, and Effects

To correctly analyze tool-using agents under distributed failures, UndoBench strictly distinguishes between three layers of execution:

```
+-----------------------------------------------------------------------------------+
| 1. PHYSICAL INVOCATION (Interface / Wire)                                         |
|    Agent dispatches HTTP POST /api/v1/charge (Tool Call #1)                       |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 2. COMMITTED MUTATION (Backend / Datastore)                                       |
|    Database commits ledger transaction $50.00 (tx_101)                            |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 3. SEMANTIC EFFECT (Domain Invariant)                                             |
|    Customer account marked ACTIVE, renewal period extended by 30 days             |
+-----------------------------------------------------------------------------------+
```

### Why This Distinction Matters

| Phenomenon | Physical Invocations | Committed Mutations | Semantic Effects | Assessment |
| :--- | :---: | :---: | :---: | :--- |
| **Nominal Run** | 1 | 1 | 1 | Valid |
| **Lost ACK + Naive Retry** | 2 | 2 | 2 | **FATAL**: Duplicate charge ($50 x 2) |
| **Lost ACK + Idempotency** | 2 | 1 | 1 | **SAFE**: Second call de-duplicated |
| **Lost ACK + Verify Probe**| 2 (1 call + 1 read) | 1 | 1 | **SAFE**: Read confirms state |

* **Physical Invocation**: What the agent attempts across the network or tool boundary.
* **Committed Mutation**: The persistent delta registered in external storage.
* **Semantic Effect**: The business logic consequence verified by the benchmark oracle.

Blind retry assumes that a failed physical invocation implies zero committed mutations. Under `POST_MUTATION_PRE_ACK` transport failures, this assumption is false and leads directly to duplicate mutations.
