"""Subprocess coverage for admin CLI entrypoints."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_python_module_entrypoint_help_works():
    completed = subprocess.run(
        [sys.executable, "-m", "admin", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "Production operator CLI for Newsly operations." in completed.stdout
    assert "admin logs tail --limit 200" in completed.stdout


def test_directory_entrypoint_help_works():
    completed = subprocess.run(
        [sys.executable, "admin", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "Production operator CLI for Newsly operations." in completed.stdout


def test_logs_tail_help_defaults_to_docker():
    completed = subprocess.run(
        [sys.executable, "-m", "admin", "logs", "tail", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "Defaults to docker." in completed.stdout
