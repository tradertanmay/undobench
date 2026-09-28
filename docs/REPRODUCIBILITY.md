# RecoverBench Reproducibility & Cryptographic Verification Guide

RecoverBench v1.0.1 is designed for 100% deterministic, push-button scientific reproducibility.

---

## 1. Frozen Artifact Checksums

The primary scientific findings of RecoverBench are permanently anchored by cryptographic SHA-256 hashes:

| Artifact | Path | Pre-Registered SHA-256 Digest |
| :--- | :--- | :--- |
| **Primary TEST Trajectory Log** | `results/rb3c_test_raw.jsonl` | `1016768449aae019484130b23fda33456861abeb161a5f8dfbeb16e9e5e9f882` |
| **Composite TEST Task Checksum**| `TEST_SET_SHA256_V1_0_1.txt` | `42ad17acaf97fcd480b8b152f8fbbc4df98acc54dfadd686c425b826dd69e0d8` |
| **TEST Task Manifest** | `TEST_MANIFEST_V1_0_1.json` | 12 held-out task file hashes |
| **Recovery Method Manifest** | `METHOD_MANIFEST_V1.json` | 6 baseline method implementation hashes |

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
recoverbench evaluate results/rb3c_test_raw.jsonl
```

Expected terminal output:
```text
======================================================================
RECOVERBENCH OFFLINE METRIC EVALUATION
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
Exactly-Once Rate:     39.03% (1,124 / 2,880)
======================================================================
```

To reproduce the forensic Exactly-Once Rate (EOR) reconstruction across wire effect logs:
```bash
python scripts/reproduce_eor.py
```

---

## 4. Test Split Quarantine Policy

To prevent test-set contamination during agent development:
- The standard benchmark runner (`recoverbench run`) **strictly refuses** to execute tasks on the `test` split by default.
- Attempting to run a test split task without explicit authorization raises `TestQuarantineError`.
- Authorization requires explicitly passing `--allow-frozen-test-execution`.
