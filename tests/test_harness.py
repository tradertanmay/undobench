"""Unit tests for the RB-3A LLM evaluation harness components."""

import json
import os
import pytest
from recoverbench.faults.injector import InjectedAckLoss, InjectedNetworkTimeout
from recoverbench.harness.canonical import (
    format_return_envelope,
    format_user_prompt,
    get_openai_tools,
    load_canonical_system_prompt,
    load_canonical_tool_schemas,
)
from recoverbench.harness.paired_runner import PairedExperimentRunner
from recoverbench.tasks.registry import TaskRegistry


def test_canonical_system_prompt_hygiene():
    """Verify system prompt does not leak benchmark solution mechanisms."""
    prompt = load_canonical_system_prompt()
    assert len(prompt) > 50
    lower = prompt.lower()
    assert "lost ack" not in lower
    assert "idempotency key" not in lower
    assert "evoundo" not in lower
    assert "recoverbench" not in lower
    assert "probe" not in lower


def test_canonical_tool_schemas_integrity():
    """Verify tool schemas for all 9 DEV tools are complete and valid JSON schema."""
    schemas = load_canonical_tool_schemas()
    expected_tools = [
        "deduct_account_balance",
        "credit_account_balance",
        "disburse_split_payout",
        "write_workspace_file",
        "commit_changes",
        "drain_and_terminate",
        "send_slack_alert",
        "post_webhook_event",
        "put_object",
    ]
    for t in expected_tools:
        assert t in schemas, f"Missing tool schema: {t}"
        spec = schemas[t]
        assert spec["name"] == t
        assert "description" in spec
        assert spec["parameters"]["type"] == "object"
        assert "properties" in spec["parameters"]
        assert "required" in spec["parameters"]


def test_format_return_envelope_fault_masking():
    """Verify return envelope masks internal benchmark fault strings with realistic errors."""
    # Clean success
    s_env = format_return_envelope(result={"balance": 70.0})
    assert s_env["status"] == "success"
    assert s_env["result"]["balance"] == 70.0

    # InjectedAckLoss
    ex = InjectedAckLoss("[RECOVERBENCH INJECTED] Lost ACK at boundary POST_MUTATION_PRE_ACK for tool 'credit'")
    err_env = format_return_envelope(error=ex)
    assert err_env["status"] == "error"
    assert "ConnectionResetError" in err_env["message"]
    assert "RECOVERBENCH" not in err_env["message"]
    assert "POST_MUTATION" not in err_env["message"]

    # InjectedNetworkTimeout
    ex_to = InjectedNetworkTimeout("[RECOVERBENCH INJECTED] Network timed out at boundary PRE_MUTATION")
    err_to = format_return_envelope(error=ex_to)
    assert err_to["status"] == "error"
    assert "TimeoutError" in err_to["message"]
    assert "RECOVERBENCH" not in err_to["message"]


def test_paired_runner_scripted_shadow():
    """Verify paired runner executes scripted shadow trial and produces valid PairedTrialVerdict."""
    runner = PairedExperimentRunner(trajectories_file="results/test_traj.jsonl")
    verdict = runner.run_paired_trial(
        task_id="RB-DB-001",
        model_code="M0",
        model_id="scripted_shadow",
        framework_code="F0",
        framework_id="scripted_control",
        recovery_code="B0",
        recovery_method="naive_retry:v1",
        trial_index=0,
        use_scripted=True,
    )
    assert verdict.task_id == "RB-DB-001"
    assert verdict.ctrl_success is True
    assert verdict.agent_outcome == "AGENT_SUCCESS"
    assert verdict.is_agent_capable is True
    # Under B0 (naive_retry) with lost ACK on Step 2, naive retry duplicates credit -> fails
    assert verdict.fault_success is False
    assert verdict.conditional_recovery_success is False
    assert os.path.exists("results/test_traj.jsonl")
    os.remove("results/test_traj.jsonl")
