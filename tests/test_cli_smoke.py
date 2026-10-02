"""Tests for unified UndoBench CLI commands."""

import subprocess
import sys


def test_cli_version():
    res = subprocess.run([sys.executable, "-m", "undobench.cli", "version"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "UndoBench 1.0.1" in res.stdout
    assert "Protocol:         V4" in res.stdout


def test_cli_doctor():
    res = subprocess.run([sys.executable, "-m", "undobench.cli", "doctor"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "UNDOBENCH READY" in res.stdout


def test_cli_tasks_domains():
    res = subprocess.run([sys.executable, "-m", "undobench.cli", "tasks", "domains"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Cloud" in res.stdout
    assert "Payments" in res.stdout
    assert "Database" in res.stdout


def test_cli_smoke():
    res = subprocess.run([sys.executable, "-m", "undobench.cli", "smoke"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Smoke test completed" in res.stdout
