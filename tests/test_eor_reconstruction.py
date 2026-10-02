"""Regression and Conformance Tests for Exactly-Once Semantic Effect Rate (EOR) Reconstruction."""

import os
import pytest
from scripts.reproduce_eor import compute_sha256, reproduce_metrics, EXPECTED_SHA256, DEFAULT_DATASET


def test_frozen_dataset_sha256_integrity():
    """Verify that results/rb3c_test_raw.jsonl matches its immutable frozen hash."""
    assert os.path.exists(DEFAULT_DATASET), f"Frozen dataset {DEFAULT_DATASET} not found"
    actual_hash = compute_sha256(DEFAULT_DATASET)
    assert actual_hash == EXPECTED_SHA256, f"Hash mismatch: expected {EXPECTED_SHA256}, got {actual_hash}"


def test_eor_metrics_reproduction_conformance():
    """Verify exact recomputed EOR counts against audited ground truth."""
    metrics = reproduce_metrics(DEFAULT_DATASET, verify_hash=True)

    assert metrics["total_paired_trials"] == 2880
    assert metrics["capable_control_trials"] == 2406
    assert metrics["unconditional_rsr"] == 0.3903
    assert metrics["conditional_crsr"] == 0.4672

    # Exactly-Once Counts
    assert metrics["exactly_once"]["unconditional_eor_count"] == 1124
    assert metrics["exactly_once"]["unconditional_eor_rate"] == 0.3903
    assert metrics["exactly_once"]["conditional_eor_count"] == 1124
    assert metrics["exactly_once"]["conditional_eor_rate"] == 0.4672

    # Side-effect rates
    assert metrics["safety_metrics"]["duplicate_effect_rate"] == 0.5014
    assert metrics["safety_metrics"]["unsafe_retry_rate"] == 0.5014
    assert metrics["safety_metrics"]["missing_effect_rate"] == 0.0986

    # Recovery Method breakdown
    b0 = metrics["by_recovery_method"]["B0"]
    assert b0["trials"] == 960
    assert b0["ctrl_passes"] == 802
    assert b0["crsr"] == 0.4277
    assert b0["conditional_eor"] == 0.4277
    assert b0["der"] == 0.5333

    b2 = metrics["by_recovery_method"]["B2"]
    assert b2["trials"] == 960
    assert b2["ctrl_passes"] == 802
    assert b2["crsr"] == 0.5349
    assert b2["conditional_eor"] == 0.5349
    assert b2["der"] == 0.4542

    b5 = metrics["by_recovery_method"]["B5"]
    assert b5["trials"] == 960
    assert b5["ctrl_passes"] == 802
    assert b5["crsr"] == 0.4389
    assert b5["conditional_eor"] == 0.4389
    assert b5["der"] == 0.5167
