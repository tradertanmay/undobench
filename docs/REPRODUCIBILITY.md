# UndoBench Reproducibility & Cryptographic Verification Guide

UndoBench v1.0.1 is designed for 100% deterministic, push-button scientific reproducibility.

---

## 1. Frozen Artifact Checksums

The primary scientific findings of UndoBench are permanently anchored by cryptographic SHA-256 hashes:

| Artifact | Path | Pre-Registered SHA-256 Digest |
| :--- | :--- | :--- |
| **Primary TEST Trajectory Log** | `results/rb3c_test_raw.jsonl` | `1016768449aae019484130b23fda33456861abeb161a5f8dfbeb16e9e5e9f882` |
| **Composite TEST Task Checksum**| `benchmark/manifests/TEST_SET_SHA256_V1_0_1.txt` | `42ad17acaf97fcd480b8b152f8fbbc4df98acc54dfadd686c425b826dd69e0d8` |
| **TEST Task Manifest** | `benchmark/manifests/TEST_MANIFEST_V1_0_1.json` | 12 held-out task file hashes |
| **Recovery Method Manifest** | `benchmark/manifests/METHOD_MANIFEST_V1.json` | 6 baseline method implementation hashes |

---

## 2. Instant Checksum Verification

Verify the cryptographic integrity of the frozen dataset and task files:

```bash
# 1. Verify frozen raw trajectory dataset
shasum -a 256 results/rb3c_test_raw.jsonl
# Expected output:
# 1016768449aae019484130b23fda33456861abeb161a5f8dfbeb16e9e5e9f882  results/rb3c_test_raw.jsonl

# 2. Run automated freeze integrity test suite
pytest tests/test_freeze_integrity.py
```

---

## 3. Recomputing Paper Metrics (Zero Model Calls)

You do not need GPU hardware or API keys to reproduce the paper's exact numerical tables.
Run the offline metric evaluator on the frozen raw trajectories:

```bash
undobench evaluate results/rb3c_test_raw.jsonl
```

Expected terminal output:
```text
======================================================================
UNDOBENCH OFFLINE METRIC EVALUATION
Input: results/rb3c_test_raw.jsonl
======================================================================
Total Trajectories:    5,760
Paired Trials:         2,880
Control Pass Rate:     83.54% (2,406 / 2,880)
Unconditional RSR:     39.03% (1,124 / 2,880)
Conditional CRSR:      46.72% (1,124 / 2,406)
Duplicate Effect Rate: 50.14% (1,444 / 2,880)
Missing Effect Rate:   10.83% (312 / 2,880)
Unsafe Retry Rate:     60.97% (1,756 / 2,880)
Exactly-Once Semantic Effect Rate: 39.03% (1,124 / 2,880)
======================================================================
```

To reproduce the forensic Exactly-Once Semantic Effect Rate (EOR) reconstruction across wire effect logs:
```bash
python scripts/reproduce_eor.py
```

---

## 4. Paper Results & Reproducibility Matrix

Every result, table, and figure presented in the research paper can be reproduced deterministically offline:

| Paper Section / Table | Content / Description | Reproduction Command | Backing Data / Report |
| :--- | :--- | :--- | :--- |
| **Table 1** (Page 5) | Primary Lost-ACK Study (5,760 runs, B0, B2, B5) | `python scripts/reproduce_eor.py` | `results/rb3c_test_raw.jsonl` |
| **Table 2 & 7** (Pages 7, 15) | Contemporary Models Matrix (Gemini 3.8 Flash, GLM-5.2) | `python scripts/analyze_rb7n7_test.py` | `results/contemporary_models/` |
| **Table 3 & Appendix G** (Pages 8, 15) | Multi-Boundary: `PRE_MUTATION` (7,680 runs) | `python scripts/analyze_rb7n10_pre_mutation.py` | `results/rb7n10_pre_mutation/` |
| **Table 8** (Page 16) | Multi-Boundary: `DURING_MUTATION` (2,560 runs) | `python scripts/analyze_rb7n10_during_mutation.py` | `results/rb7n10_during_mutation/` |
| **Section 6 & Appendix H** (Pages 8, 16) | Universal Idempotency B2-K (1,920 runs) | `python scripts/analyze_rb7n10_keys_everywhere_real.py` | `results/rb7n10_keys_everywhere/` |
| **Tables 4 & 5** (Page 13) | 12 Held-Out TEST Workflows & Deduplication Support | `undobench tasks list --split test` | `benchmark/manifests/` |
| **Figures 1–6** | Architecture, Heatmaps, Observability Plots | Generated from raw evaluation trajectories | `results/` |

---

## 5. Test Split Quarantine Policy

To prevent test-set contamination during agent development:
- The standard benchmark runner (`undobench run`) **strictly refuses** to execute tasks on the `test` split by default.
- Attempting to run a test split task without explicit authorization raises `TestQuarantineError`.
- Authorization requires explicitly passing `--allow-frozen-test-execution`.

