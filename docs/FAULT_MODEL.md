# RecoverBench Distributed Fault Model Specification

This document details the formal fault injection model, execution boundaries, perturbation types, and scope of empirical evidence in RecoverBench.

---

## 1. The Distributed Tool-Calling Lifecycle

Tool execution in autonomous agents is fundamentally a distributed system interaction:
$$\text{Agent} \xrightarrow{\text{Request}} \text{Network} \xrightarrow{\text{Tool/API}} \text{Backend Datastore}$$

RecoverBench instruments the tool execution boundary with deterministic, programmable fault proxies capable of intercepting execution at five canonical boundaries.

```
       [Agent Planning]
              |
      (1) PRE_MUTATION  --> Network connection refused / DNS timeout
              |
      [Tool API Invocation]
              |
      (2) DURING_MUTATION --> Database deadlock / partial transaction abort
              |
      [Datastore Commit]
              |
      (3) POST_MUTATION_PRE_ACK --> Mutation committed, but response dropped (Lost ACK)
              |
      [Agent ACK Received]
              |
      (4) POST_ACK_PRE_CHECKPOINT --> Process crashes before saving state graph
              |
      [Failure Recovery / Rollback]
              |
      (5) DURING_COMPENSATION --> Compensating refund or rollback API fails
```

---

## 2. The Five Canonical Execution Boundaries

### Boundary 1: `PRE_MUTATION`
* **Mechanism**: Transport failure occurs before any state-modifying payload reaches the external server.
* **External State**: Unmodified (0 committed mutations).
* **Recovery Implication**: Safe to retry immediately; no idempotency key or compensation required.

### Boundary 2: `DURING_MUTATION`
* **Mechanism**: Server accepts the request but crashes or aborts mid-transaction (e.g. unique constraint violation, deadlock).
* **External State**: Partial or aborted transaction state.
* **Recovery Implication**: Agent must inspect database error codes or clean up partial temporary records.

### Boundary 3: `POST_MUTATION_PRE_ACK` (The Lost ACK Problem)
* **Mechanism**: The backend successfully executes and commits the mutation. However, before the HTTP `200 OK` or success acknowledgment reaches the agent, the transport connection drops or times out.
* **External State**: **Committed** (1 mutation registered in external datastore).
* **Agent Epistemic State**: **Unknown** (agent received `TimeoutError` or `ConnectionResetError`).
* **Recovery Implication**: Extremely hazardous. Blindly retrying will cause duplicate side effects unless protected by idempotency keys ($B_2$), post-commit state probes ($B_6$), or human-in-the-loop escalation.

### Boundary 4: `POST_ACK_PRE_CHECKPOINT`
* **Mechanism**: The agent receives the success ACK, but the host process is terminated or restarts before the agent can write its memory checkpoint to persistent disk.
* **External State**: Committed.
* **Agent Epistemic State**: On restart, agent memory believes the task step has not occurred.
* **Recovery Implication**: Requires durable external transaction logging or reconcilers to avoid re-executing completed workflow steps.

### Boundary 5: `DURING_COMPENSATION`
* **Mechanism**: When an unhandled failure occurs, a saga or compensating controller attempts to execute a compensating reversal (e.g. `issue_refund`), which itself fails or times out.
* **External State**: Inconsistent split-brain state.
* **Recovery Implication**: Requires multi-phase commit or dead-letter queue escalation.

---

## 3. Scope of Held-Out TEST Evidence

> **Important Scope Note**:  
> The frozen held-out TEST experimental evidence in the RecoverBench v1.0.1 paper (12 workflows, 5,760 executions, 2,880 paired counterfactual trials) **concentrates specifically on the `POST_MUTATION_PRE_ACK` boundary**.

### Why Focus on `POST_MUTATION_PRE_ACK`?
1. **Pervasive in Production**: Lost acknowledgments and transport timeouts are ubiquitous in real-world microservices, webhooks, and cloud APIs.
2. **Maximum Ambiguity**: `POST_MUTATION_PRE_ACK` produces maximum epistemic uncertainty: the agent cannot distinguish whether the server never received the request or whether the server committed the request and lost the response.
3. **Severe Safety Consequences**: Under this boundary, naive retry causes duplicate mutations in 53.33% of trials.

The DEV and VALIDATION splits include companion scenarios covering the other boundaries to enable multi-boundary generalization research.
