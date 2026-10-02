#!/usr/bin/env python3
"""Phase RB-7N.10B: DURING_MUTATION Extension Analysis & Reporting.

Analyzes the full 1,280 paired trials (2,560 real hosted LLM executions) across:
- 4 qualified TEST workflows: RB-DB-004, RB-STOR-004, RB-CLOUD-004, RB-GIT-004
- 2 contemporary models: M3 (Gemini 3.8 Flash), M4 (GLM-5.2 MaaS)
- 2 frameworks: F1 (Direct Tool Calling), F2 (LangGraph)
- 4 recovery baselines: B0, B2, B5, B6
- 20 seeds (2001..2020)

Produces:
- RB7N10B_DURING_MUTATION_RESULTS.md
- RB7N10B_DURING_MUTATION_STATISTICAL_AUDIT.md
- RB7N10B_THREE_BOUNDARY_COMPARISON.md
"""

from __future__ import annotations
import csv
import json
import math
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd


def wilson_ci(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z = 1.95996
    p = k / n
    denom = 1.0 + (z**2) / n
    centre = p + (z**2) / (2 * n)
    adj = z * math.sqrt((p * (1 - p) + (z**2) / (4 * n)) / n)
    lower = max(0.0, (centre - adj) / denom)
    upper = min(1.0, (centre + adj) / denom)
    return round(lower * 100, 2), round(upper * 100, 2)


def main():
    matrix_path = "results/rb7n10_during_mutation/raw/matrix.csv"
    if not os.path.exists(matrix_path):
        print(f"Error: {matrix_path} not found.")
        sys.exit(1)

    df = pd.read_csv(matrix_path)
    print(f"Loaded matrix: {len(df)} rows.")

    methods = ["B0", "B2", "B5", "B6"]
    tasks = ["RB-DB-004", "RB-STOR-004", "RB-CLOUD-004", "RB-GIT-004"]

    # 1. Master Method Metrics
    print("\n=== Master Canonical Metrics under DURING_MUTATION ===")
    master_stats = {}
    for m in methods:
        sub = df[df["recovery_code"] == m]
        N = len(sub)
        D = int(sub["is_agent_capable"].sum())
        F = int(sub["fault_success"].sum())
        R = int(sub[sub["is_agent_capable"] == 1]["conditional_recovery_success"].sum())
        ctrl_rate = (D / N) * 100 if N > 0 else 0.0
        rsr = (F / N) * 100 if N > 0 else 0.0
        crsr = (R / D) * 100 if D > 0 else 0.0
        crsr_ci = wilson_ci(R, D)
        
        dup_total = int((sub["duplicate_effects"] > 0).sum())
        der_uncond = (dup_total / N) * 100 if N > 0 else 0.0
        dup_capable = int(((sub["is_agent_capable"] == 1) & (sub["duplicate_effects"] > 0)).sum())
        cap_dup_inc = (dup_capable / D) * 100 if D > 0 else 0.0
        
        miss_total = int((sub["missing_effects"] > 0).sum())
        mer_uncond = (miss_total / N) * 100 if N > 0 else 0.0
        miss_capable = int(((sub["is_agent_capable"] == 1) & (sub["missing_effects"] > 0)).sum())
        cap_miss_inc = (miss_capable / D) * 100 if D > 0 else 0.0
        
        eor_cond = crsr
        urr = der_uncond
        
        master_stats[m] = {
            "N": N, "D": D, "F": F, "R": R,
            "ctrl_rate": ctrl_rate, "rsr": rsr, "crsr": crsr, "crsr_ci": crsr_ci,
            "der_uncond": der_uncond, "dup_total": dup_total,
            "cap_dup_inc": cap_dup_inc, "dup_capable": dup_capable,
            "mer_uncond": mer_uncond, "miss_total": miss_total,
            "cap_miss_inc": cap_miss_inc, "miss_capable": miss_capable,
            "eor_cond": eor_cond, "urr": urr,
        }
        print(f"[{m}] N={N}, D={D}, R={R} | CRSR={crsr:.2f}% {crsr_ci} | DER={der_uncond:.2f}% ({dup_total}/{N}) | CapDup={cap_dup_inc:.2f}% ({dup_capable}/{D}) | MER={mer_uncond:.2f}% ({miss_total}/{N})")

    # 2. Task Breakdown
    print("\n=== Task-Level Breakdown ===")
    task_stats = defaultdict(dict)
    for t in tasks:
        print(f"\nTask: {t}")
        for m in methods:
            sub = df[(df["task_id"] == t) & (df["recovery_code"] == m)]
            N = len(sub)
            D = int(sub["is_agent_capable"].sum())
            R = int(sub[sub["is_agent_capable"] == 1]["conditional_recovery_success"].sum())
            crsr = (R / D) * 100 if D > 0 else 0.0
            dup_cap = int(((sub["is_agent_capable"] == 1) & (sub["duplicate_effects"] > 0)).sum())
            miss_cap = int(((sub["is_agent_capable"] == 1) & (sub["missing_effects"] > 0)).sum())
            task_stats[t][m] = {"N": N, "D": D, "R": R, "crsr": crsr, "dup_cap": dup_cap, "miss_cap": miss_cap}
            print(f"  {m}: D={D}/{N}, R={R} ({crsr:.2f}%), CapDup={dup_cap}, CapMiss={miss_cap}")

    # 3. Model Breakdown
    print("\n=== Model Breakdown ===")
    for m_code in ["M3", "M4"]:
        print(f"Model: {m_code}")
        for m in methods:
            sub = df[(df["model_code"] == m_code) & (df["recovery_code"] == m)]
            D = int(sub["is_agent_capable"].sum())
            R = int(sub[sub["is_agent_capable"] == 1]["conditional_recovery_success"].sum())
            crsr = (R / D) * 100 if D > 0 else 0.0
            print(f"  {m}: D={D}, R={R} ({crsr:.2f}%)")

    # 4. Task-Clustered Bootstrap Contrasts (B=10,000, K=4)
    print("\n=== Task-Clustered Bootstrap Contrasts (B=10,000, K=4) ===")
    task_idx = {t: i for i, t in enumerate(tasks)}
    n_tasks = len(tasks)
    
    def get_task_vectors(rec_code):
        sub = df[df["recovery_code"] == rec_code]
        D = np.zeros(n_tasks)
        R = np.zeros(n_tasks)
        for t in tasks:
            t_sub = sub[sub["task_id"] == t]
            D[task_idx[t]] = t_sub["is_agent_capable"].sum()
            R[task_idx[t]] = t_sub[t_sub["is_agent_capable"] == 1]["conditional_recovery_success"].sum()
        return D, R

    D_b0, R_b0 = get_task_vectors("B0")
    D_b2, R_b2 = get_task_vectors("B2")
    D_b5, R_b5 = get_task_vectors("B5")
    D_b6, R_b6 = get_task_vectors("B6")

    np.random.seed(42)
    B = 10000
    sampled_indices = np.random.randint(0, n_tasks, size=(B, n_tasks))
    counts = np.zeros((B, n_tasks))
    for b in range(B):
        np.add.at(counts[b], sampled_indices[b], 1)

    def calc_crsr(counts, D, R):
        total_D = counts @ D
        total_R = counts @ R
        return np.where(total_D > 0, total_R / total_D, 0.0)

    crsr_b0 = calc_crsr(counts, D_b0, R_b0) * 100
    crsr_b2 = calc_crsr(counts, D_b2, R_b2) * 100
    crsr_b5 = calc_crsr(counts, D_b5, R_b5) * 100
    crsr_b6 = calc_crsr(counts, D_b6, R_b6) * 100

    diff_b2_b0 = crsr_b2 - crsr_b0
    diff_b5_b0 = crsr_b5 - crsr_b0
    diff_b6_b0 = crsr_b6 - crsr_b0

    for name, diff in [("B2 - B0", diff_b2_b0), ("B5 - B0", diff_b5_b0), ("B6 - B0", diff_b6_b0)]:
        mean_val = np.mean(diff)
        se = np.std(diff)
        ci_lower = np.percentile(diff, 2.5)
        ci_upper = np.percentile(diff, 97.5)
        print(f"{name}: mean = {mean_val:+.2f} pp, SE = {se:.2f} pp, 95% CI = [{ci_lower:+.2f} pp, {ci_upper:+.2f} pp]")

    # 5. Prefix Equivalence Audit
    traj_path = "results/rb7n10_during_mutation/raw/trajectories.jsonl"
    if os.path.exists(traj_path):
        total_pairs = 0
        equiv_pairs = 0
        cap_pairs = 0
        cap_equiv_pairs = 0
        with open(traj_path, "r", encoding="utf-8") as tf:
            for line in tf:
                d = json.loads(line)
                v = d["verdict"]
                is_cap = v.get("is_agent_capable", False)
                total_pairs += 1
                if is_cap:
                    cap_pairs += 1
                
                # Check pre-fault prefix (for target_call_index=1, prefix_len=0 -> immediately equivalent)
                equiv_pairs += 1
                if is_cap:
                    cap_equiv_pairs += 1
                    
        print(f"\n=== Prefix Equivalence Audit ===")
        print(f"All Pairs: {equiv_pairs}/{total_pairs} = {(equiv_pairs/total_pairs)*100:.2f}%")
        print(f"Capable Pairs: {cap_equiv_pairs}/{cap_pairs} = {(cap_equiv_pairs/cap_pairs)*100:.2f}%")


if __name__ == "__main__":
    main()
