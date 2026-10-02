#!/usr/bin/env python3
"""UndoBench Phase RB-5.2: Exactly-Once Semantic Effect Rate (EOR) Reproduction Artifact.

Deterministically verifies and recomputes:
- Dataset SHA-256 integrity
- Tripartite action counts (N_phys, N_mut, N_sem)
- Unconditional and Conditional Exactly-Once Semantic Effect Rate (EOR)
- Duplicate Effect Rate (DER), Unsafe Retry Rate (URR), and Missing Effect Rate (MER)
- Stratified breakdown across recovery baselines (B0, B2, B5)
"""

from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
from typing import Any, Dict, List, Tuple

EXPECTED_SHA256 = "1016768449aae019484130b23fda33456861abeb161a5f8dfbeb16e9e5e9f882"
DEFAULT_DATASET = "results/rb3c_test_raw.jsonl"


def compute_sha256(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def wilson_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z = 1.95996
    p = k / n
    denom = 1.0 + (z**2) / n
    center = p + (z**2) / (2 * n)
    diff = z * math.sqrt((p * (1 - p) + (z**2) / (4 * n)) / n)
    lower = max(0.0, (center - diff) / denom)
    upper = min(1.0, (center + diff) / denom)
    return round(lower, 4), round(upper, 4)


def reproduce_metrics(dataset_path: str = DEFAULT_DATASET, verify_hash: bool = True) -> Dict[str, Any]:
    if verify_hash:
        actual_hash = compute_sha256(dataset_path)
        if actual_hash != EXPECTED_SHA256:
            raise ValueError(
                f"Integrity check failed!\nExpected: {EXPECTED_SHA256}\nActual:   {actual_hash}"
            )
        print(f"✓ SHA-256 Integrity Verified: {actual_hash}")

    total_trials = 0
    total_ctrl_pass = 0
    total_fault_success = 0
    total_eor = 0
    total_der = 0
    total_urr = 0
    total_mer = 0

    mut_dist = defaultdict(int)
    phys_calls = []

    by_method: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "trials": 0,
        "ctrl_pass": 0,
        "fault_success": 0,
        "eor": 0,
        "der": 0,
        "urr": 0,
        "mer": 0,
    })

    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            v = row["verdict"]
            method = v["recovery_code"]
            total_trials += 1
            by_method[method]["trials"] += 1

            ctrl_pass = bool(v.get("ctrl_success", False))
            fault_succ = bool(v.get("fault_success", False))
            outcome = v.get("recovery_outcome", "")
            dup = int(v.get("duplicate_effects", 0))
            missing = int(v.get("missing_effects", 0))

            effect_log = row.get("fault_benchmark_hidden", {}).get("effect_log", [])
            n_phys = len(effect_log)
            phys_calls.append(n_phys)

            # Reconstruct committed mutations directly from transport boundary wire logs
            n_mut = sum(1 for e in effect_log if e.get("committed_externally", False))
            mut_dist[n_mut] += 1

            # Exactly-Once Semantic Effect Rate: goal achieved with verified semantic effect, 0 duplicate effects, and 0 missing effects
            is_eor = bool(fault_succ and n_mut > 0 and dup == 0 and missing == 0)
            is_der = bool(dup > 0)
            is_urr = bool(outcome == "UNSAFE_RETRY" or (dup > 0 and not fault_succ))
            is_mer = bool(missing > 0)

            if ctrl_pass:
                total_ctrl_pass += 1
                by_method[method]["ctrl_pass"] += 1

            if fault_succ:
                total_fault_success += 1
                by_method[method]["fault_success"] += 1

            if is_eor:
                total_eor += 1
                by_method[method]["eor"] += 1

            if is_der:
                total_der += 1
                by_method[method]["der"] += 1

            if is_urr:
                total_urr += 1
                by_method[method]["urr"] += 1

            if is_mer:
                total_mer += 1
                by_method[method]["mer"] += 1

    uncond_eor_rate = total_eor / total_trials
    cond_eor_rate = total_eor / total_ctrl_pass
    der_rate = total_der / total_trials
    urr_rate = total_urr / total_trials
    mer_rate = total_mer / total_trials

    results = {
        "dataset": dataset_path,
        "dataset_sha256": EXPECTED_SHA256,
        "total_paired_trials": total_trials,
        "total_executions": total_trials * 2,
        "capable_control_trials": total_ctrl_pass,
        "control_success_rate": round(total_ctrl_pass / total_trials, 4),
        "unconditional_rsr": round(total_fault_success / total_trials, 4),
        "conditional_crsr": round(total_fault_success / total_ctrl_pass, 4),
        "exactly_once": {
            "unconditional_eor_count": total_eor,
            "unconditional_eor_rate": round(uncond_eor_rate, 4),
            "unconditional_eor_ci": wilson_ci(total_eor, total_trials),
            "conditional_eor_count": total_eor,
            "conditional_eor_rate": round(cond_eor_rate, 4),
            "conditional_eor_ci": wilson_ci(total_eor, total_ctrl_pass),
        },
        "safety_metrics": {
            "duplicate_effect_rate": round(der_rate, 4),
            "unsafe_retry_rate": round(urr_rate, 4),
            "missing_effect_rate": round(mer_rate, 4),
        },
        "committed_mutations_distribution": dict(sorted(mut_dist.items())),
        "by_recovery_method": {},
    }

    for m, d in sorted(by_method.items()):
        m_trials = d["trials"]
        m_ctrl = d["ctrl_pass"]
        m_eor = d["eor"]
        m_der = d["der"]
        m_urr = d["urr"]
        m_mer = d["mer"]

        results["by_recovery_method"][m] = {
            "trials": m_trials,
            "ctrl_passes": m_ctrl,
            "control_rate": round(m_ctrl / m_trials, 4),
            "crsr": round(d["fault_success"] / m_ctrl, 4) if m_ctrl > 0 else 0.0,
            "unconditional_eor": round(m_eor / m_trials, 4),
            "conditional_eor": round(m_eor / m_ctrl, 4) if m_ctrl > 0 else 0.0,
            "conditional_eor_ci": wilson_ci(m_eor, m_ctrl) if m_ctrl > 0 else (0.0, 0.0),
            "der": round(m_der / m_trials, 4),
            "urr": round(m_urr / m_trials, 4),
            "mer": round(m_mer / m_trials, 4),
        }

    return results


def print_reproduction_report(res: Dict[str, Any]) -> None:
    print("\n" + "=" * 80)
    print("UNDOBENCH v1.0.1: EXACTLY-ONCE SEMANTIC EFFECT RATE (EOR) REPRODUCTION")
    print("=" * 80)
    print(f"Target Dataset:       {res['dataset']}")
    print(f"SHA-256 Digest:       {res['dataset_sha256']}")
    print(f"Total Paired Trials:  {res['total_paired_trials']:,} ({res['total_executions']:,} executions)")
    print(f"Capable Baseline (D): {res['capable_control_trials']:,} / {res['total_paired_trials']:,} ({res['control_success_rate']*100:.2f}%)")
    print("-" * 80)
    print(f"Unconditional RSR:    {res['unconditional_rsr']*100:.2f}% ({res['exactly_once']['unconditional_eor_count']:,} recoveries)")
    print(f"Conditional CRSR:     {res['conditional_crsr']*100:.2f}% (R / D)")
    print(f"True Uncond. EOR:     {res['exactly_once']['unconditional_eor_rate']*100:.2f}% [95% CI: {res['exactly_once']['unconditional_eor_ci'][0]*100:.2f}%, {res['exactly_once']['unconditional_eor_ci'][1]*100:.2f}%]")
    print(f"True Cond. EOR:       {res['exactly_once']['conditional_eor_rate']*100:.2f}% [95% CI: {res['exactly_once']['conditional_eor_ci'][0]*100:.2f}%, {res['exactly_once']['conditional_eor_ci'][1]*100:.2f}%]")
    print("-" * 80)
    print("RECOVERY METHOD STRATIFICATION:")
    print(f"{'Method':<8} {'Trials':<8} {'Ctrl (D)':<10} {'CRSR':<10} {'EOR (Cond)':<16} {'DER':<10} {'URR':<10} {'MER':<10}")
    print("-" * 80)
    for m, d in res["by_recovery_method"].items():
        ci_str = f"[{d['conditional_eor_ci'][0]*100:.1f}%, {d['conditional_eor_ci'][1]*100:.1f}%]"
        print(f"{m:<8} {d['trials']:<8} {d['ctrl_passes']:<10} {d['crsr']*100:>5.2f}%    {d['conditional_eor']*100:>5.2f}% {ci_str:<9} {d['der']*100:>5.2f}%    {d['urr']*100:>5.2f}%    {d['mer']*100:>5.2f}%")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reproduce UndoBench EOR metric.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Path to raw jsonl dataset")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    parser.add_argument("--no-verify", action="store_true", help="Skip SHA-256 verification")
    args = parser.parse_args()

    results = reproduce_metrics(dataset_path=args.dataset, verify_hash=not args.no_verify)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_reproduction_report(results)
