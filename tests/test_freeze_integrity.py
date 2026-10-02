"""Verification of Freeze A (TEST Set), Freeze B (Recovery Methods), and Canonical Dataset Checksums."""

import hashlib
import json
import os
import pytest
from recoverbench.runner.runner import BenchmarkRunner, TestQuarantineError
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.tasks.registry import TaskRegistry


def test_v1_0_0_archival_integrity():
    """Verify that RecoverBench v1.0.0 frozen TEST manifest exists and matches expected structure."""
    manifest_path = "benchmark/manifests/TEST_MANIFEST_V1.json"
    if not os.path.exists(manifest_path):
        manifest_path = "TEST_MANIFEST_V1.json"
    assert os.path.exists(manifest_path), "TEST_MANIFEST_V1.json missing"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["benchmark_version"] == "1.0.0"
    assert manifest["composite_test_set_sha256"] == "1ea69de72b7f238b9dde65138212d43cacf617266005a4f81187352090325963"
    assert len(manifest["tasks"]) == 12


def test_v1_0_1_erratum_manifest_hashes():
    """Verify that every v1.0.1 erratum frozen TEST task file matches its pre-registered SHA-256 hash."""
    manifest_path = "benchmark/manifests/TEST_MANIFEST_V1_0_1.json"
    if not os.path.exists(manifest_path):
        manifest_path = "TEST_MANIFEST_V1_0_1.json"
    assert os.path.exists(manifest_path), "TEST_MANIFEST_V1_0_1.json missing"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["benchmark_version"] == "1.0.1"
    assert manifest["total_test_tasks"] == 12
    assert len(manifest["tasks"]) == 12

    for entry in manifest["tasks"]:
        file_path = entry["file_path"]
        assert os.path.exists(file_path), f"Task file {file_path} does not exist"
        with open(file_path, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()
        assert current_hash == entry["sha256"], f"Integrity violation in {file_path}: expected {entry['sha256']}, got {current_hash}"


def test_v1_0_1_composite_test_hash():
    """Verify that composite hash matches individual test task files."""
    manifest_path = "benchmark/manifests/TEST_MANIFEST_V1_0_1.json"
    if not os.path.exists(manifest_path):
        manifest_path = "TEST_MANIFEST_V1_0_1.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    composite_hasher = hashlib.sha256()
    for entry in sorted(manifest["tasks"], key=lambda x: x["file_path"]):
        with open(entry["file_path"], "rb") as f:
            composite_hasher.update(f.read())

    expected_composite = manifest["composite_test_set_sha256"]
    assert expected_composite == "42ad17acaf97fcd480b8b152f8fbbc4df98acc54dfadd686c425b826dd69e0d8"
    assert composite_hasher.hexdigest() == expected_composite


def test_canonical_raw_dataset_hash():
    """Verify that the primary frozen raw trajectory dataset matches the pre-registered SHA-256 digest."""
    dataset_path = "results/rb3c_test_raw.jsonl"
    assert os.path.exists(dataset_path), f"Frozen dataset {dataset_path} missing"
    with open(dataset_path, "rb") as f:
        current_hash = hashlib.sha256(f.read()).hexdigest()
    expected_hash = "1016768449aae019484130b23fda33456861abeb161a5f8dfbeb16e9e5e9f882"
    assert current_hash == expected_hash, (
        f"Cryptographic integrity violation in {dataset_path}! "
        f"Expected {expected_hash}, got {current_hash}"
    )


def test_method_manifest_hashes():
    """Verify that every frozen recovery baseline method matches its frozen SHA-256 hash."""
    manifest_path = "benchmark/manifests/METHOD_MANIFEST_V1.json"
    if not os.path.exists(manifest_path):
        manifest_path = "METHOD_MANIFEST_V1.json"
    assert os.path.exists(manifest_path), "METHOD_MANIFEST_V1.json missing"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["benchmark_version"] == "1.0.0"
    assert manifest["total_methods"] == 6
    assert len(manifest["methods"]) == 6

    for entry in manifest["methods"]:
        file_path = entry["file_path"]
        assert os.path.exists(file_path), f"Method file {file_path} does not exist"
        with open(file_path, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()
        assert current_hash == entry["sha256"], f"Integrity violation in {file_path}: expected {entry['sha256']}, got {current_hash}"


def test_test_quarantine_enforcement():
    """Verify that ordinary runner calls strictly refuse to execute frozen TEST tasks without explicit authorization."""
    runner = BenchmarkRunner()
    test_tasks = TaskRegistry.list_task_ids(split="test")
    assert len(test_tasks) == 12

    ctrl_fault = FaultSpec(boundary=ExecutionBoundary.NO_FAULT, perturbation=Perturbation.NONE)

    # Attempting to run trial on any test task without authorization must raise TestQuarantineError
    with pytest.raises(TestQuarantineError) as exc_info:
        runner.run_trial(test_tasks[0], "naive", ctrl_fault, allow_frozen_test_execution=False)
    assert "TEST QUARANTINE ENFORCED" in str(exc_info.value)

    # Attempting to run suite on test split must also raise TestQuarantineError
    with pytest.raises(TestQuarantineError):
        runner.run_suite(test_tasks[:2], ["naive"], allow_frozen_test_execution=False)
