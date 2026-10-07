# UndoBench Hugging Face Dataset Validation (UB-HF1)

HF_OWNER = TanmaySah
HF_DATASET = undobench
HF_REPO = TanmaySah/undobench

TOTAL_TASKS = 36
DEV = 14
VALIDATION = 10
TEST = 12
DOMAINS = 8

MISSING_TASK_IDS = 0
EXTRA_TASK_IDS = 0
DUPLICATE_TASK_IDS = 0

FOUR_AUTHORS_LISTED = YES
CITATION_HAS_4_AUTHORS = YES
CITATION_AUTHOR_ORDER_MATCHES_ARXIV = YES

DATASET_VIEWER_WORKS = YES
LOAD_DATASET_WORKS = YES

PAPER_LINK_PRESENT = YES
HF_PAPER_LINK_PRESENT = YES
GITHUB_LINK_PRESENT = YES

LICENSE = CC-BY-4.0
SECURITY_SCAN_PASS = YES

CANONICAL_TASKS_CHANGED = NO
SCIENTIFIC_RESULTS_CHANGED = NO

---

## Detailed Audit & Verification Log

### 1. Repository & Publication Details
- **Hugging Face Repository**: [TanmaySah/undobench](https://huggingface.co/datasets/TanmaySah/undobench)
- **Public URL**: `https://huggingface.co/datasets/TanmaySah/undobench`
- **Visibility**: Public (`private: false`)
- **License**: CC BY 4.0 (`license: cc-by-4.0`)
- **Paper Association**: `arxiv:2610.05622` (`papers: ["2610.05622"]`)
- **Code Link**: `https://github.com/tradertanmay/undobench`

### 2. Task & Split Breakdown
- **Split DEV**: 14 workflows (`data/dev.parquet`)
- **Split VALIDATION**: 10 workflows (`data/validation.parquet`)
- **Split TEST**: 12 workflows (`data/test.parquet`)
- **Total Workflows**: 36 canonical workflows across 8 enterprise operational domains:
  1. Cloud Infrastructure (4 tasks)
  2. Customer Relationship Management (CRM) (4 tasks)
  3. Database Transactions (5 tasks)
  4. Git Version Control (4 tasks)
  5. Messaging Systems (5 tasks)
  6. Payments & Billing (5 tasks)
  7. Storage & Blob Management (5 tasks)
  8. Ticketing & Incident Management (4 tasks)

### 3. Canonical Authorship
- **Hosting Namespace**: `TanmaySah` (Personal Hugging Face account used for dataset discovery and hosting)
- **Canonical Authors**:
  1. Dolly Sah
  2. Tanmay Sah
  3. Harshul Jain
  4. Tanya Sah
- **Order Verification**: Exactly matches the public arXiv record `arXiv:2610.05622`.

### 4. Client Verification (`datasets.load_dataset`)
```python
from datasets import load_dataset

ds = load_dataset("TanmaySah/undobench")
# Result:
# DatasetDict({
#     dev: Dataset({features: [...], num_rows: 14}),
#     validation: Dataset({features: [...], num_rows: 10}),
#     test: Dataset({features: [...], num_rows: 12})
# })
```

### 5. Security & Secret Scan
- **Hugging Face tokens**: 0 detected
- **GitHub tokens**: 0 detected
- **OpenAI/Anthropic/API keys**: 0 detected
- **Private keys**: 0 detected
- **Local filesystem paths (`/Users/`)**: 0 detected
- **Status**: PASSED
