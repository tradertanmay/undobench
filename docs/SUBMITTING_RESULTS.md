# Submitting Benchmark Results to the UndoBench Leaderboard

UndoBench maintains an open community leaderboard evaluating agent recovery resilience and side-effect safety.

---

## 1. Two-Tier Trust Model

UndoBench operates under a formal two-tier trust architecture:

```
+-----------------------------------------------------------------------------------+
| Tier 1: OPEN_REPRODUCIBLE (Self-Reported & Peer Audited)                          |
| - Researcher runs evaluation on local or cloud inference endpoints                |
| - Generates standardized JSON trajectory bundle via CLI                           |
| - Automatically validated against schema constraints                              |
| - Published to public leaderboard with "Open Reproducible" badge                  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Tier 2: OFFICIAL_VERIFIED (Independently Re-Run)                                  |
| - Submitted agent code or endpoint re-evaluated by UndoBench maintainers       |
| - Executed inside isolated container sandboxes under quarantined evaluation seeds |
| - Results verified against held-out perturbation schedules                        |
| - Published with "Official Verified" badge                                        |
+-----------------------------------------------------------------------------------+
```

---

## 2. Packaging a Submission Bundle

After completing a benchmark run, package the results into a validated submission bundle:

```bash
undobench submit prepare \
    --run-dir runs/my_eval_run \
    --author "My Organization or Name" \
    --model "ModelFamily-70B-Instruct" \
    --framework "CustomAgentFramework" \
    --output submissions/my_org/my_model
```

This creates:
```
submissions/my_org/my_model/
├── submission.json          # Metadata, model configs, author info
├── manifest.json            # File inventory and SHA-256 digests
├── metrics.json             # Recomputed metrics (Control, CRSR, DER, etc.)
└── submission_bundle.zip    # Compressed raw trajectories and logs
```

---

## 3. Validating the Submission Locally

Before opening a Pull Request, validate the bundle against official UndoBench schemas:

```bash
undobench submit validate \
    --bundle-path submissions/my_org/my_model/submission_bundle.zip
```

The validator checks:
* Trajectory schema compliance (`UNDOBENCH_TRAJECTORY_SCHEMA_V1.json`)
* Paired counterfactual integrity (matching control/fault seed pairs)
* Non-tampered oracle verdicts and wire effect logs
* Metric mathematical consistency

---

## 4. Submitting via Pull Request

1. Commit your submission directory:
   ```bash
   git checkout -b submission/my-org-my-model
   git add submissions/my_org/my_model/
   git commit -m "sub: add ModelFamily-70B UndoBench submission"
   ```
2. Open a Pull Request on GitHub targeting the `main` branch.
3. Automated CI will run `undobench submit validate` on your submission bundle.
4. Once verified, your results will appear on the public leaderboard.
