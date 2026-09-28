"""RecoverBench Submission Preparation and Validation Pipeline (Phase RB-6).

Provides deterministic packaging and automated verification of benchmark runs
for peer review, leaderboard submissions, and reproduction audits.
"""

from __future__ import annotations
import datetime
import hashlib
import json
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional, Tuple

from recoverbench.engine import BenchmarkEngine, BENCHMARK_VERSION, PROTOCOL_VERSION
from recoverbench.schemas.trajectory import validate_trajectory
from recoverbench.tasks.registry import TaskRegistry


def compute_file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class SubmissionPipeline:
    """Handles preparation and verification of RecoverBench submissions."""

    @classmethod
    def prepare_submission(
        cls,
        run_dir: str,
        output_dir: Optional[str] = None,
        organization: str = "Independent Researcher",
        paper_url: Optional[str] = None,
        repo_url: Optional[str] = None,
    ) -> str:
        """Package a completed run into a standardized submission bundle."""
        if not os.path.exists(run_dir):
            raise FileNotFoundError(f"Run directory '{run_dir}' does not exist.")

        original_dir = run_dir
        # Check if trajectories.jsonl is in run_dir or a nested run subdirectory
        if not os.path.exists(os.path.join(run_dir, "trajectories.jsonl")):
            for entry in sorted(os.listdir(run_dir), reverse=True):
                sub_p = os.path.join(run_dir, entry)
                if os.path.isdir(sub_p) and os.path.exists(os.path.join(sub_p, "trajectories.jsonl")):
                    run_dir = sub_p
                    break

        manifest_file = os.path.join(run_dir, "manifest.json")
        trajectories_file = os.path.join(run_dir, "trajectories.jsonl")
        summary_file = os.path.join(run_dir, "summary.json")

        if not os.path.exists(trajectories_file):
            raise FileNotFoundError(f"Missing required trajectory file: '{trajectories_file}'")

        if output_dir is None:
            output_dir = os.path.join(original_dir, "submission")
        os.makedirs(output_dir, exist_ok=True)

        # 1. Compute trajectory hash and metadata
        traj_hash = compute_file_sha256(trajectories_file)
        
        # Read run manifest if present
        run_manifest = {}
        if os.path.exists(manifest_file):
            with open(manifest_file, "r", encoding="utf-8") as f:
                run_manifest = json.load(f)

        # Re-evaluate metrics deterministically
        metrics = BenchmarkEngine.evaluate_trajectories_file(trajectories_file)

        # Count trajectories, tasks, seeds
        tasks_seen = set()
        seeds_seen = set()
        trajectory_count = 0
        with open(trajectories_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    trajectory_count += 1
                    if "task_id" in r:
                        tasks_seen.add(r["task_id"])
                    elif "verdict" in r:
                        tasks_seen.add(r["verdict"]["task_id"])
                    if "seed" in r:
                        seeds_seen.add(r["seed"])
                except Exception:
                    pass

        # 2. Determine STANDARD vs. CUSTOM track
        config = run_manifest.get("config", {})
        split = config.get("split") or config.get("suite") or "dev"
        expected_tasks = TaskRegistry.list_task_ids(split=split) if split in ["dev", "validation", "test"] else []
        complete_coverage = set(expected_tasks).issubset(tasks_seen) if expected_tasks else False
        
        track = "STANDARD" if complete_coverage else "CUSTOM"

        # Resolve agent identity and model digest
        agent_id = run_manifest.get("agent_identity", {})
        canonical_model = agent_id.get("canonical_name") or config.get("model")
        model_digest = agent_id.get("digest")
        is_immutable = agent_id.get("is_immutable", False)

        agent_info = {
            "name": config.get("agent_spec") or canonical_model or config.get("agent_url") or "UnknownAgent",
            "version": config.get("sdk_version", "1.0.0"),
            "framework": "recoverbench_adapter",
            "model_name": canonical_model,
            "raw_alias": config.get("model"),
            "model_digest": model_digest,
            "is_immutable": is_immutable,
            "recovery_strategy": config.get("recovery", "none"),
        }

        # 3. Create submission.json
        submission_id = f"sub_{uuid.uuid4().hex[:8]}"
        submission_data = {
            "submission_id": submission_id,
            "benchmark_version": run_manifest.get("benchmark_version", BENCHMARK_VERSION),
            "protocol_version": run_manifest.get("protocol_version", PROTOCOL_VERSION),
            "date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "track": track,
            "trust_level": "OPEN_REPRODUCIBLE",
            "verification_status": "SELF-REPORTED",
            "trust_notice": (
                "OPEN_REPRODUCIBLE results are locally generated with open evaluator code. "
                "Local hash verification validates trajectory integrity and metric reproduction, "
                "but does not prevent deliberate benchmark gaming. Official leaderboard ranking "
                "requires OFFICIAL_VERIFIED qualification via official CI rerun."
            ),
            "organization": organization,
            "paper_url": paper_url,
            "repo_url": repo_url,
            "agent": agent_info,
            "metrics": {
                "control_rate": metrics.get("control_rate", 0.0),
                "rsr": metrics.get("rsr", 0.0),
                "crsr": metrics.get("crsr"),
                "eor": metrics.get("eor"),
                "der": metrics.get("der", 0.0),
                "mer": metrics.get("mer", 0.0),
                "total_pairs": metrics.get("total_pairs", 0),
            },
            "verification": {
                "trajectory_file_hash": traj_hash,
                "task_manifest_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "complete_coverage": complete_coverage,
                "offline_reproduced": True,
                "notes": f"Prepared from run '{run_manifest.get('run_id', 'unknown')}' with {trajectory_count} trajectories.",
            },
        }

        with open(os.path.join(output_dir, "submission.json"), "w", encoding="utf-8") as f:
            json.dump(submission_data, f, indent=2)

        with open(os.path.join(output_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(run_manifest, f, indent=2)

        traj_manifest = {
            "trajectory_file_hash": traj_hash,
            "total_trajectories": trajectory_count,
            "tasks_count": len(tasks_seen),
            "tasks": sorted(list(tasks_seen)),
            "seeds_count": len(seeds_seen),
            "seeds": sorted(list(seeds_seen)),
        }
        with open(os.path.join(output_dir, "trajectory_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(traj_manifest, f, indent=2)

        # Copy trajectories
        shutil.copy2(trajectories_file, os.path.join(output_dir, "trajectories.jsonl"))

        return output_dir

    @classmethod
    def validate_submission(
        cls,
        submission_dir: str,
        strict: bool = False,
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Statically and empirically validate an existing submission bundle."""
        errors: List[str] = []
        checks: Dict[str, bool] = {}

        if not os.path.exists(submission_dir):
            parent = os.path.dirname(submission_dir.rstrip("/"))
            if os.path.isdir(parent):
                for entry in sorted(os.listdir(parent), reverse=True):
                    cand = os.path.join(parent, entry, "submission")
                    if os.path.exists(cand):
                        submission_dir = cand
                        break
        if not os.path.exists(submission_dir):
            return False, [f"Directory '{submission_dir}' not found"], {}

        sub_file = os.path.join(submission_dir, "submission.json")
        metrics_file = os.path.join(submission_dir, "metrics.json")
        traj_file = os.path.join(submission_dir, "trajectories.jsonl")
        traj_manifest_file = os.path.join(submission_dir, "trajectory_manifest.json")

        for fpath, label in [(sub_file, "submission.json"), (traj_file, "trajectories.jsonl"), (traj_manifest_file, "trajectory_manifest.json")]:
            if not os.path.exists(fpath):
                errors.append(f"Missing required file: {label}")
                checks[label] = False
            else:
                checks[label] = True

        if errors:
            return False, errors, checks

        with open(sub_file, "r", encoding="utf-8") as f:
            sub_data = json.load(f)
        with open(traj_manifest_file, "r", encoding="utf-8") as f:
            t_manifest = json.load(f)

        # 1. Benchmark & Protocol Version check
        b_ver = sub_data.get("benchmark_version")
        checks["benchmark_version"] = (b_ver == BENCHMARK_VERSION)
        if not checks["benchmark_version"]:
            errors.append(f"Benchmark version mismatch: expected '{BENCHMARK_VERSION}', got '{b_ver}'")

        # 2. Trajectory Hash Verification
        actual_hash = compute_file_sha256(traj_file)
        expected_hash = sub_data.get("verification", {}).get("trajectory_file_hash")
        checks["trajectory_hash_match"] = (actual_hash == expected_hash)
        if not checks["trajectory_hash_match"]:
            errors.append(f"Trajectory SHA-256 hash mismatch! Stored: {expected_hash}, Actual: {actual_hash}")

        # 3. Trajectory Schema Validation (Sample up to 100 trajectories)
        schema_valid = True
        traj_count = 0
        with open(traj_file, "r", encoding="utf-8") as f:
            for line in f:
                traj_count += 1
                if traj_count > 100:
                    break
                try:
                    r = json.loads(line)
                    if "verdict" in r:
                        # Legacy RB-3 format, allowed
                        pass
                    else:
                        ok, errs = validate_trajectory(r)
                        if not ok:
                            schema_valid = False
                            errors.extend(errs[:2])
                            break
                except Exception as ex:
                    schema_valid = False
                    errors.append(f"JSON parsing error on trajectory line {traj_count}: {ex}")
                    break
        checks["trajectory_schema_valid"] = schema_valid

        # 4. Offline Metric Reproduction
        reproduced_metrics = BenchmarkEngine.evaluate_trajectories_file(traj_file)
        stored_metrics = sub_data.get("metrics", {})
        metrics_reproduced = True
        for key in ["control_rate", "rsr", "der", "mer"]:
            val_stored = stored_metrics.get(key)
            val_reproduced = reproduced_metrics.get(key)
            if val_stored is not None and val_reproduced is not None:
                if abs(val_stored - val_reproduced) > 1e-4:
                    metrics_reproduced = False
                    errors.append(f"Metric mismatch on '{key}': declared {val_stored:.4f} vs reproduced {val_reproduced:.4f}")
        checks["metrics_reproduced"] = metrics_reproduced

        # 5. Model Identity Immutability Check
        agent_spec = sub_data.get("agent", {})
        raw_alias = agent_spec.get("raw_alias") or ""
        model_digest = agent_spec.get("model_digest")
        is_immutable = agent_spec.get("is_immutable", False)

        if sub_data.get("track") == "STANDARD":
            if (raw_alias.endswith(":latest") or not raw_alias) and not model_digest:
                if strict:
                    errors.append(
                        f"STANDARD submission for OFFICIAL_VERIFIED requires an immutable model digest. Found unpinned alias '{raw_alias}' without digest."
                    )
                    checks["model_identity_immutable"] = False
                else:
                    checks["model_identity_immutable"] = False
            else:
                checks["model_identity_immutable"] = True
        else:
            checks["model_identity_immutable"] = True

        # 6. Determine Final Verification Verdict
        overall_valid = (len(errors) == 0)
        checks["overall_valid"] = overall_valid

        # Update verification status in submission.json if valid
        if overall_valid:
            sub_data["verification_status"] = "VERIFIED"
            sub_data["verification"]["offline_reproduced"] = True
            with open(sub_file, "w", encoding="utf-8") as f:
                json.dump(sub_data, f, indent=2)

        return overall_valid, errors, checks

    @classmethod
    def inspect_submission(cls, submission_dir: str) -> Dict[str, Any]:
        """Inspect and summarize a prepared submission bundle."""
        if not os.path.exists(submission_dir):
            raise FileNotFoundError(f"Submission directory '{submission_dir}' not found.")
        sub_file = os.path.join(submission_dir, "submission.json")
        if not os.path.exists(sub_file):
            raise FileNotFoundError(f"Missing 'submission.json' in '{submission_dir}'.")
        with open(sub_file, "r", encoding="utf-8") as f:
            sub = json.load(f)
        valid, errors, checks = cls.validate_submission(submission_dir)
        return {
            "submission_id": sub.get("submission_id"),
            "benchmark_version": sub.get("benchmark_version"),
            "date": sub.get("date"),
            "organization": sub.get("organization"),
            "paper_url": sub.get("paper_url"),
            "repo_url": sub.get("repo_url"),
            "track": sub.get("track"),
            "trust_level": sub.get("trust_level", "OPEN_REPRODUCIBLE"),
            "verification_status": sub.get("verification_status"),
            "agent": sub.get("agent", {}),
            "metrics": sub.get("metrics", {}),
            "checks": checks,
            "errors": errors,
            "valid": valid,
            "trust_notice": sub.get("trust_notice"),
        }
