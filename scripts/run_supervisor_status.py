#!/usr/bin/env python3
"""Run `supervisorctl status` while tolerating expected non-zero service states."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Sequence

STATUS_LINE_PATTERN = re.compile(
    r"^\S+\s+(RUNNING|STARTING|STOPPED|BACKOFF|FATAL|EXITED|UNKNOWN)\b",
    re.MULTILINE,
)


def _build_output(stdout: str, stderr: str) -> str:
    """Merge process stdout and stderr into a single printable string."""
    parts = [part.strip() for part in (stdout, stderr) if part.strip()]
    return "\n".join(parts)


def run_supervisor_status(command: Sequence[str]) -> tuple[int, str]:
    """Run a supervisor status command and normalize expected status exits."""
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    output = _build_output(completed.stdout, completed.stderr)

    if completed.returncode == 0:
        return 0, output

    if STATUS_LINE_PATTERN.search(output):
        return 0, output

    return completed.returncode, output


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI entrypoint."""
    command = list(argv or sys.argv[1:] or ["sudo", "supervisorctl", "status"])
    exit_code, output = run_supervisor_status(command)

    if output:
        print(output)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
