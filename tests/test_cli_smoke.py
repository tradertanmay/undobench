"""Tests for unified RecoverBench CLI commands."""

import subprocess
import sys


def test_cli_version():
    res = subprocess.run([sys.executable, "-m", "recoverbench.cli", "version"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "RecoverBench 1.0.1" in res.stdout
    assert "Protocol:         V4" in res.stdout


def test_cli_doctor():
    res = subprocess.run([sys.executable, "-m", "recoverbench.cli", "doctor"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "RECOVERBENCH READY" in res.stdout


def test_cli_tasks_domains():
    res = subprocess.run([sys.executable, "-m", "recoverbench.cli", "tasks", "domains"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Cloud" in res.stdout
    assert "Payments" in res.stdout
    assert "Database" in res.stdout


def test_cli_smoke():
    res = subprocess.run([sys.executable, "-m", "recoverbench.cli", "smoke"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Smoke test completed" in res.stdout
