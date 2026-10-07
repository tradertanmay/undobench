# UndoBench Hugging Face Pre-Publication Audit Report (UB-HF-PREPUBLICATION-QA)

**Audit Timestamp**: 2026-10-07T07:07:00Z  
**Repository**: [`TanmaySah/undobench`](https://huggingface.co/datasets/TanmaySah/undobench)  
**Status**: Confirmed **PRIVATE** (No visibility change made)  

---

## 1. Repository Inventory & Visibility Status

* **HF Owner**: `TanmaySah`
* **HF Dataset**: `undobench`
* **Visibility**: **PRIVATE** (`private: True`)
* **Live Dataset Viewer Status**: `NOT_YET_VERIFIED`
* **Dataset Viewer Reason**: `PRIVATE_REPOSITORY` (The Hugging Face Dataset Viewer cannot be verified on the Hub while the repository is private; full verification will occur post-publication).

### Exact Files Uploaded to Hugging Face
| File Path | Size (Bytes) | Category |
| :--- | ---: | :--- |
| `.gitattributes` | 2,504 | Configuration |
| `README.md` | 4,136 | Documentation |
| `UB_HF_DATASET_VALIDATION.md` | 2,589 | Documentation |
| `data/dev.parquet` | 23,065 | Parquet Data |
| `data/test.parquet` | 20,950 | Parquet Data |
| `data/validation.parquet` | 21,481 | Parquet Data |

* **Raw Trajectories / Provider Logs / Credentials Present**: **NONE (0)**
* **Unexpected Files**: **0**

---

## 2. Row Counts & Split Partitioning

* **Total Parquet Rows**: 36
* **DEV Split (`data/dev.parquet`)**: 14 rows
* **VALIDATION Split (`data/validation.parquet`)**: 10 rows
* **TEST Split (`data/test.parquet`)**: 12 rows

### Split Membership Validation
* Rows in `dev.parquet` with `split == 'dev'`: **14 / 14** (0 mismatches)
* Rows in `validation.parquet` with `split == 'validation'`: **10 / 10** (0 mismatches)
* Rows in `test.parquet` with `split == 'test'`: **12 / 12** (0 mismatches)

---

## 3. Dataset Schema (17 Columns)

All 3 splits share an identical 17-column PyArrow schema:

| # | Column Name | PyArrow Type | Description |
|---|:---|:---|:---|
| 1 | `task_id` | `string` | Unique workflow identifier |
| 2 | `split` | `string` | Split partition (`dev`, `validation`, `test`) |
| 3 | `domain` | `string` | Enterprise software domain |
| 4 | `workflow_name` | `string` | Canonical workflow title |
| 5 | `workflow_description` | `string` | Baseline workflow description |
| 6 | `objective` | `string` | Natural language instruction for agent |
| 7 | `fault_scenario` | `string` | JSON-serialized evaluator fault injection spec |
| 8 | `fault_boundary` | `string` | Primary failure lifecycle boundary |
| 9 | `reversibility` | `string` | Action reversibility classification |
| 10 | `idempotency_support` | `bool` | Native server-side idempotency flag |
| 11 | `tools` | `list<item: string>` | Callable tools available to agent |
| 12 | `initial_state` | `string` | JSON-serialized initial sandbox state |
| 13 | `expected_outcome` | `string` | JSON-serialized target final state |
| 14 | `required_effects` | `string` | JSON-serialized wire mutations |
| 15 | `oracle_spec` | `string` | JSON-serialized assertions and invariants |
| 16 | `benchmark_version` | `string` | Freeze version (`v1.0.1`) |
| 17 | `source_path` | `string` | Canonical repository-relative implementation path |

* **Exact Column Count**: 17
* **README Schema Matches Parquet**: **YES**

---

## 4. Task ID Integrity & Canonical Source Matching

* **Total Task IDs**: 36
* **Unique Task IDs**: 36
* **Duplicate Task IDs**: 0
* **Null / Empty Task IDs**: 0
* **Cross-Split Duplicates**: 0
* **Missing from Canonical Benchmark**: 0
* **Extra in Hugging Face**: 0
* **Task ID Set Matches Canonical Repository**: **YES**

---

## 5. Domain Distribution (8 Enterprise Domains)

| Domain | DEV | VALIDATION | TEST | TOTAL |
| :--- | :---: | :---: | :---: | :---: |
| **Cloud** | 2 | 1 | 1 | **4** |
| **Crm** | 2 | 1 | 1 | **4** |
| **Database** | 2 | 1 | 2 | **5** |
| **Git** | 2 | 1 | 1 | **4** |
| **Messaging** | 2 | 1 | 2 | **5** |
| **Payments** | 2 | 1 | 2 | **5** |
| **Storage** | 1 | 2 | 2 | **5** |
| **Ticketing** | 1 | 2 | 1 | **4** |
| **Total** | **14** | **10** | **12** | **36** |

* **Total Domains Represented**: 8
* **Unknown / Extra Domains**: 0

---

## 6. Structured JSON Fields Validation

All serialized JSON columns parse cleanly with `json.loads()` across all 36 rows with zero truncation:

| Field Name | Rows Checked | Valid JSON | Malformed / Truncated |
| :--- | :---: | :---: | :---: |
| `fault_scenario` | 36 | 36 | 0 |
| `initial_state` | 36 | 36 | 0 |
| `expected_outcome` | 36 | 36 | 0 |
| `required_effects` | 36 | 36 | 0 |
| `oracle_spec` | 36 | 36 | 0 |

---

## 7. Null & Empty Content Audit

| Column Name | Null Count | Empty String Count | Status |
| :--- | :---: | :---: | :---: |
| `task_id` | 0 | 0 | PASS |
| `domain` | 0 | 0 | PASS |
| `objective` | 0 | 0 | PASS |
| `workflow_name` | 0 | 0 | PASS |
| `fault_boundary` | 0 | 0 | PASS |
| `benchmark_version` | 0 | 0 | PASS |
| `source_path` | 0 | 0 | PASS |

---

## 8. Implementation Source Paths (`source_path`)

* **Valid Repository-Relative Paths**: 36 / 36 (All resolve to concrete task implementation files in `https://github.com/tradertanmay/undobench`)
* **Invalid Paths**: 0
* **Local Absolute Paths (`/Users/...`)**: 0

---

## 9. Benchmark Version Consistency

* **Unique Benchmark Versions Across All Rows**: `["v1.0.1"]` (0 version mismatches)

---

## 10. Representative Rows

### DEV Representative Row (`RB-DB-001` · Database)
```json
{
  "task_id": "RB-DB-001",
  "split": "dev",
  "domain": "database",
  "workflow_name": "Account Balance Transfer under Lost ACK",
  "workflow_description": "Customer Address Update",
  "objective": "Transfer $30 from Alice's account (acc_alice) to Bob's account (acc_bob).",
  "fault_scenario": "{\"scenario_id\": \"SCN-LOST-ACK\", \"name\": \"Lost-ACK on Debit\", \"boundary\": \"POST_MUTATION_PRE_ACK\", \"perturbation\": \"ACK_LOSS\", \"target_tool\": null, \"target_call_index\": 1, \"observability\": \"UNKNOWN_OUTCOME\", \"concurrent_state_delta\": null, \"description\": \"Deduct succeeds externally but ACK is dropped\", \"expected_recovery_behavior\": \"Detect external state witness before retrying debit\", \"fault_spec\": {\"boundary\": \"POST_MUTATION_PRE_ACK\", \"perturbation\": \"ACK_LOSS\", \"target_tool\": null, \"target_call_index\": 1, \"injected_count\": 1, \"concurrent_state_delta\": null}}",
  "fault_boundary": "POST_MUTATION_PRE_ACK",
  "reversibility": "COMPENSATABLE",
  "idempotency_support": "False",
  "tools": "['deduct_account_balance' 'credit_account_balance']",
  "initial_state": "{\"accounts\": {\"acc_alice\": 100.0, \"acc_bob\": 50.0}}",
  "expected_outcome": "{\"accounts.acc_alice\": 70.0, \"accounts.acc_bob\": 80.0}",
  "required_effects": "[{\"target\": \"accounts.acc_alice.balance\", \"op_type\": \"UPDATE\", \"expected_value\": 70.0, \"max_occurrences\": 1, \"reversibility\": \"REVERSIBLE\", \"description\": \"Deduct $30 from Alice's account\"}, {\"target\": \"accounts.acc_bob.balance\", \"op_type\": \"UPDATE\", \"expected_value\": 80.0, \"max_occurrences\": 1, \"reversibility\": \"REVERSIBLE\", \"description\": \"Credit $30 to Bob's account\"}]",
  "oracle_spec": "{\"acceptable_final_states\": {\"accounts.acc_alice\": 70.0, \"accounts.acc_bob\": 80.0}, \"forbidden_effects\": [{\"target\": \"accounts.acc_alice.balance\", \"op_type\": null, \"forbidden_value\": 40.0, \"reason\": \"Double deduction from Alice's account due to unsafe retry\"}], \"invariants\": [{\"name\": \"non_negative_alice\", \"description\": \"Alice balance must not be negative\", \"expression\": \"non_negative_balance\"}]}",
  "benchmark_version": "v1.0.1",
  "source_path": "recoverbench/tasks/dev/rb_db_001.py"
}
```

### VALIDATION Representative Row (`RB-CLOUD-001` · Cloud)
```json
{
  "task_id": "RB-CLOUD-001",
  "split": "validation",
  "domain": "cloud",
  "workflow_name": "Cloud Service Scale-Out & Discovery Sync",
  "workflow_description": "Autoscaling Policy Update",
  "objective": "Scale checkout-service from 3 to 6 replicas and sync service discovery catalog.",
  "fault_scenario": "{\"scenario_id\": \"SCN-POST-ACK-PRE-CHECKPOINT\", \"name\": \"Crash Post-ACK Pre-Checkpoint\", \"boundary\": \"POST_ACK_PRE_CHECKPOINT\", \"perturbation\": \"WORKER_CRASH\", \"target_tool\": null, \"target_call_index\": 1, \"observability\": \"UNKNOWN_OUTCOME\", \"concurrent_state_delta\": null, \"description\": \"Scale succeeds and ACK returned, but worker crashes before catalog sync\", \"expected_recovery_behavior\": \"Resume and synchronize discovery catalog without re-scaling\", \"fault_spec\": {\"boundary\": \"POST_ACK_PRE_CHECKPOINT\", \"perturbation\": \"WORKER_CRASH\", \"target_tool\": null, \"target_call_index\": 1, \"injected_count\": 1, \"concurrent_state_delta\": null}}",
  "fault_boundary": "POST_ACK_PRE_CHECKPOINT",
  "reversibility": "COMPENSATABLE",
  "idempotency_support": "False",
  "tools": "['scale_service' 'sync_discovery_catalog']",
  "initial_state": "{\"service_name\": \"checkout-service\", \"replicas\": 3}",
  "expected_outcome": "{\"services.checkout-service.desired_replicas\": 6, \"running_replicas\": 6, \"catalog_count\": 6}",
  "required_effects": "[{\"target\": \"cloud.service.checkout-service.scale\", \"op_type\": \"UPDATE\", \"expected_value\": null, \"max_occurrences\": 1, \"reversibility\": \"REVERSIBLE\", \"description\": \"Scale compute replicas to exactly 6\"}, {\"target\": \"cloud.discovery.catalog.checkout-service\", \"op_type\": \"UPDATE\", \"expected_value\": null, \"max_occurrences\": 1, \"reversibility\": \"REVERSIBLE\", \"description\": \"Synchronize active instances with discovery catalog\"}]",
  "oracle_spec": "{\"acceptable_final_states\": {\"services.checkout-service.desired_replicas\": 6, \"running_replicas\": 6, \"catalog_count\": 6}, \"forbidden_effects\": [], \"invariants\": []}",
  "benchmark_version": "v1.0.1",
  "source_path": "recoverbench/tasks/validation/rb_cloud_001.py"
}
```

### TEST Representative Row (`RB-PAY-004` · Payments)
```json
{
  "task_id": "RB-PAY-004",
  "split": "test",
  "domain": "payments",
  "workflow_name": "Subscription Renewal with Grace Period",
  "workflow_description": "Subscription Renewal with Grace Period",
  "objective": "Renew annual enterprise subscription sub_annual_99 for $1,200.00 (120000 cents).",
  "fault_scenario": "{\"scenario_id\": \"SCN-LOST-ACK\", \"name\": \"Lost-ACK on Subscription Billing\", \"boundary\": \"POST_MUTATION_PRE_ACK\", \"perturbation\": \"ACK_LOSS\", \"target_tool\": null, \"target_call_index\": 1, \"observability\": \"UNKNOWN_OUTCOME\", \"concurrent_state_delta\": null, \"description\": \"Subscription renewed at card processor but ACK lost\", \"expected_recovery_behavior\": \"Attach subscription renewal idempotency token or query subscription status\", \"fault_spec\": {\"boundary\": \"POST_MUTATION_PRE_ACK\", \"perturbation\": \"ACK_LOSS\", \"target_tool\": null, \"target_call_index\": 1, \"injected_count\": 1, \"concurrent_state_delta\": null}}",
  "fault_boundary": "POST_MUTATION_PRE_ACK",
  "reversibility": "COMPENSATABLE",
  "idempotency_support": "False",
  "tools": "['process_subscription_renewal']",
  "initial_state": "{\"sub_id\": \"sub_annual_99\", \"plan_id\": \"enterprise_annual\"}",
  "expected_outcome": "{}",
  "required_effects": "[{\"target\": \"payments.subscription.sub_annual_99\", \"op_type\": \"CREATE\", \"expected_value\": null, \"max_occurrences\": 1, \"reversibility\": \"REVERSIBLE\", \"description\": \"Process exactly one subscription renewal charge\"}]",
  "oracle_spec": "{\"acceptable_final_states\": {}, \"forbidden_effects\": [{\"target\": \"payments.subscription.sub_annual_99\", \"op_type\": null, \"forbidden_value\": null, \"reason\": \"Double recurring subscription billing to customer card\"}], \"invariants\": []}",
  "benchmark_version": "v1.0.1",
  "source_path": "recoverbench/tasks/test/rb_pay_004.py"
}
```

---

## 11. Authenticated Remote `load_dataset()` & Parquet Parity

* **Authenticated Client Load**: `load_dataset("TanmaySah/undobench", token=True)` succeeds with zero warnings.
* **Returned Splits**: `["dev", "validation", "test"]`
* **Local vs. Remote Parquet Parity**: **100% Match** (`LOCAL_REMOTE_DATA_MATCH = YES`)

---

## 12. Authorship, Scholarly Attribution & Citation

* **Authors Listed**:
  1. Dolly Sah
  2. Tanmay Sah
  3. Harshul Jain
  4. Tanya Sah
* **Author Order**: Exactly matches the public arXiv record `arXiv:2610.05622`.
* **Citation in README**:
  ```bibtex
  @article{undobench2026,
    title={UndoBench: Separating Task Competence from Recovery Capability in Tool-Using AI Agents},
    author={Dolly Sah and Tanmay Sah and Harshul Jain and Tanya Sah},
    journal={arXiv preprint arXiv:2610.05622},
    year={2026},
    url={https://arxiv.org/abs/2610.05622}
  }
  ```

---

## 13. Security & Publication-Status Privacy Scan

* **Hugging Face Tokens Found**: 0
* **GitHub Tokens Found**: 0
* **API Keys Found (OpenAI/Anthropic/Google)**: 0
* **Private Key Headers Found**: 0
* **Local Filesystem Paths (`/Users/`)**: 0
* **Peer-Review / Conference Status References (NAACL, ARR, etc.)**: 0
* **Security & Privacy Status**: **PASSED**

---

## 14. Scientific Immutability Attestation

* **Canonical Task Definitions Changed**: NO
* **Task IDs Changed**: NO
* **Splits Changed**: NO
* **Fault Definitions Changed**: NO
* **Oracle Definitions Changed**: NO
* **Scientific Results Changed**: NO
* **Frozen Test Set Hashes Changed**: NO
