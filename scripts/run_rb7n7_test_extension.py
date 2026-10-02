"""Phase RB-7N.7T: Full Contemporary-Model Held-Out TEST Extension Runner.

Executes the prospectively specified factorial evaluation:
- 12 held-out TEST workflows across 8 enterprise domains
- 2 contemporary models: M3 (Gemini 3.8 Flash), M4 (GLM-5.2 MaaS)
- 2 frameworks: F1 (Direct Tool Calling), F2 (LangGraph)
- 3 recovery methods: B0 (Naive Retry), B2 (Idempotency), B5 (EvoUndo-RB1)
- 2 conditions: CONTROL (NO_FAULT) and FAULT (POST_MUTATION_PRE_ACK)
- 20 seeds: 2001 through 2020 (trial_index 0..19)
- Total: 2,880 Paired Trials = 5,760 Individual Condition Executions

FROZEN CONFIGURATION COMMIT: cc3108e684f9af105ce72c19737f6077f57fdf59
OUTPUT ISOLATION: results/contemporary_models/
"""

from __future__ import annotations
import concurrent.futures
import csv
import json
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from recoverbench.harness.paired_runner import PairedExperimentRunner, PairedTrialVerdict
from recoverbench.tasks.registry import TaskRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("rb7n7_test")

# 12 Held-Out TEST Tasks
TEST_TASKS = [
    ("cloud", "RB-CLOUD-004"),
    ("crm", "RB-CRM-004"),
    ("database", "RB-DB-004"),
    ("database", "RB-DB-005"),
    ("git", "RB-GIT-004"),
    ("messaging", "RB-MSG-004"),
    ("messaging", "RB-MSG-005"),
    ("payments", "RB-PAY-004"),
    ("payments", "RB-PAY-005"),
    ("storage", "RB-STOR-004"),
    ("storage", "RB-STOR-005"),
    ("ticketing", "RB-TICK-004"),
]

MODELS = [
    ("M3", "gemini-3.8-flash", "google/gemini-3.8-flash"),
    ("M4", "zai-org/glm-5.2-maas", "zai-org/glm-5.2-maas"),
]

FRAMEWORKS = [
    ("F1", "direct_tool_calling:v4"),
    ("F2", "langgraph_agent:v4"),
]

RECOVERY_METHODS = [
    ("B0", "naive_retry:v1"),
    ("B2", "idempotency:v1"),
    ("B5", "evoundo:rb1"),
]

NUM_TRIALS = 20  # Seeds 2001..2020
START_SEED = 2001

# Output Structure
BASE_DIR = "results/contemporary_models"
MANIFEST_DIR = os.path.join(BASE_DIR, "manifests")
RAW_DIR = os.path.join(BASE_DIR, "raw")
RAW_GEMINI = os.path.join(RAW_DIR, "gemini_3_8_flash")
RAW_GLM = os.path.join(RAW_DIR, "glm_5_2")
LOG_DIR = os.path.join(BASE_DIR, "logs")
TELEMETRY_DIR = os.path.join(BASE_DIR, "telemetry")
FINAL_DIR = os.path.join(BASE_DIR, "final")

MATRIX_CSV = os.path.join(RAW_DIR, "matrix.csv")
ALL_TRAJ_FILE = os.path.join(RAW_DIR, "trajectories.jsonl")
GEMINI_TRAJ_FILE = os.path.join(RAW_GEMINI, "trajectories.jsonl")
GLM_TRAJ_FILE = os.path.join(RAW_GLM, "trajectories.jsonl")
RERUN_LEDGER_FILE = os.path.join(TELEMETRY_DIR, "rerun_ledger.jsonl")
MANIFEST_FILE = os.path.join(MANIFEST_DIR, "test_factorial_manifest.json")


def setup_directories():
    for d in [BASE_DIR, MANIFEST_DIR, RAW_DIR, RAW_GEMINI, RAW_GLM, LOG_DIR, TELEMETRY_DIR, FINAL_DIR]:
        os.makedirs(d, exist_ok=True)


def build_manifest(total_pairs: int) -> List[Tuple]:
    plan = []
    manifest_entries = []
    for domain, tid in TEST_TASKS:
        for m_code, m_id, m_canon in MODELS:
            for f_code, f_id in FRAMEWORKS:
                for r_code, r_method in RECOVERY_METHODS:
                    for t_idx in range(NUM_TRIALS):
                        seed = START_SEED + t_idx
                        item = (domain, tid, m_code, m_id, m_canon, f_code, f_id, r_code, r_method, t_idx, seed)
                        plan.append(item)
                        manifest_entries.append({
                            "task_id": tid,
                            "domain": domain,
                            "model_code": m_code,
                            "model_id": m_canon,
                            "framework_code": f_code,
                            "framework_id": f_id,
                            "recovery_code": r_code,
                            "recovery_method": r_method,
                            "trial_index": t_idx,
                            "seed": seed,
                        })

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "benchmark_phase": "RB-7N.7T",
            "protocol": "prospectively_specified_post_freeze_contemporary_model_extension",
            "frozen_code_commit": "cc3108e684f9af105ce72c19737f6077f57fdf59",
            "total_paired_trials": len(manifest_entries),
            "total_executions": len(manifest_entries) * 2,
            "tasks": [t[1] for t in TEST_TASKS],
            "models": {m[0]: m[2] for m in MODELS},
            "frameworks": {f[0]: f[1] for f in FRAMEWORKS},
            "recovery_methods": {r[0]: r[1] for r in RECOVERY_METHODS},
            "seeds": list(range(START_SEED, START_SEED + NUM_TRIALS)),
            "trials": manifest_entries,
        }, f, indent=2)

    return plan


def run_test_extension(workers: int = 6):
    setup_directories()

    total_expected = len(TEST_TASKS) * len(MODELS) * len(FRAMEWORKS) * len(RECOVERY_METHODS) * NUM_TRIALS
    plan = build_manifest(total_expected)

    completed_keys: Set[Tuple[str, str, str, str, int]] = set()
    if os.path.exists(MATRIX_CSV):
        try:
            with open(MATRIX_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    completed_keys.add((
                        r["task_id"],
                        r["model_code"],
                        r["framework_code"],
                        r["recovery_code"],
                        int(r["trial_index"]),
                    ))
            logger.info(f"Resuming: Loaded {len(completed_keys)} already completed paired trials from {MATRIX_CSV}")
        except Exception as e:
            logger.warning(f"Error reading existing matrix CSV: {e}")

    remaining_plan = [p for p in plan if (p[1], p[2], p[5], p[7], p[9]) not in completed_keys]
    logger.info(f"Total planned paired trials: {total_expected} (5,760 executions). Remaining to execute: {len(remaining_plan)}")

    # Instantiate runners
    runner_m3 = PairedExperimentRunner(output_dir=RAW_GEMINI, trajectories_file=GEMINI_TRAJ_FILE)
    runner_m4 = PairedExperimentRunner(output_dir=RAW_GLM, trajectories_file=GLM_TRAJ_FILE)

    file_lock = threading.Lock()

    if not os.path.exists(MATRIX_CSV):
        with open(MATRIX_CSV, "w", newline="", encoding="utf-8") as f:
            dummy = PairedTrialVerdict(
                pair_id="", task_id="", domain="", model_code="", model_id="",
                framework_code="", framework_id="", recovery_code="", recovery_method="",
                trial_index=0, ctrl_success=False, agent_outcome="", ctrl_duration_ms=0.0,
                ctrl_prompt_tokens=0, ctrl_completion_tokens=0, ctrl_tool_calls=0, ctrl_llm_calls=0,
                fault_success=False, recovery_outcome="", fault_duration_ms=0.0,
                fault_prompt_tokens=0, fault_completion_tokens=0, fault_tool_calls=0, fault_llm_calls=0,
            )
            writer = csv.DictWriter(f, fieldnames=list(dummy.__dict__.keys()))
            writer.writeheader()

    completed_count = len(completed_keys)
    start_time = time.time()
    total_prompt_tokens = 0
    total_completion_tokens = 0
    provider_errors_count = 0

    def execute_trial_item(item):
        nonlocal completed_count, total_prompt_tokens, total_completion_tokens, provider_errors_count
        domain, tid, m_code, m_id, m_canon, f_code, f_id, r_code, r_method, t_idx, seed = item

        runner = runner_m3 if m_code == "M3" else runner_m4
        t_start = time.time()

        try:
            verdict = runner.run_paired_trial(
                task_id=tid,
                model_code=m_code,
                model_id=m_id,
                framework_code=f_code,
                framework_id=f_id,
                recovery_code=r_code,
                recovery_method=r_method,
                trial_index=t_idx,
                seed=seed,
            )
        except Exception as ex:
            with file_lock:
                provider_errors_count += 1
                logger.error(f"EXCEPTION on {tid} | {m_code} | {f_code} | {r_code} | trial {t_idx}: {ex}")
                with open(RERUN_LEDGER_FILE, "a", encoding="utf-8") as rf:
                    rf.write(json.dumps({
                        "task_id": tid,
                        "model_code": m_code,
                        "framework_code": f_code,
                        "recovery_code": r_code,
                        "trial_index": t_idx,
                        "seed": seed,
                        "error": str(ex),
                        "timestamp": time.time(),
                    }) + "\n")
            raise ex

        elapsed = time.time() - t_start
        p_tok = verdict.ctrl_prompt_tokens + verdict.fault_prompt_tokens
        c_tok = verdict.ctrl_completion_tokens + verdict.fault_completion_tokens

        with file_lock:
            completed_count += 1
            total_prompt_tokens += p_tok
            total_completion_tokens += c_tok

            # Append to master CSV
            with open(MATRIX_CSV, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(verdict.__dict__.keys()))
                writer.writerow(verdict.__dict__)

            # Operational monitoring only (No scientific aggregation during execution)
            if completed_count % 10 == 0 or completed_count == total_expected:
                elapsed_total = time.time() - start_time
                avg_pace = elapsed_total / max(1, (completed_count - len(completed_keys)))
                eta_sec = (total_expected - completed_count) * avg_pace
                eta_min = eta_sec / 60.0
                logger.info(
                    f"[{completed_count}/{total_expected}] ({(completed_count/total_expected)*100:.1f}%) | "
                    f"Latest: {tid} ({m_code}/{f_code}/{r_code}/t{t_idx}) in {elapsed:.2f}s | "
                    f"Tokens: {p_tok}p/{c_tok}c | Pace: {avg_pace:.2f}s/trial | ETA: {eta_min:.1f}m"
                )

        return verdict

    if remaining_plan:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(execute_trial_item, remaining_plan))

    total_time = time.time() - start_time
    logger.info(f"EXECUTION COMPLETE: All {total_expected} paired trials recorded in {MATRIX_CSV} (Time: {total_time:.1f}s)")


if __name__ == "__main__":
    workers = 6
    if len(sys.argv) > 1:
        workers = int(sys.argv[1])
    run_test_extension(workers=workers)
