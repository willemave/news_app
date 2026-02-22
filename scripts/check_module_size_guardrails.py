#!/usr/bin/env python3
"""Fail when key high-churn modules grow past agreed line-count guardrails."""

from __future__ import annotations

import json
from pathlib import Path


def load_guardrails(config_path: Path) -> dict[str, int]:
    """Load guardrail line limits from JSON config."""
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Guardrail config must be a JSON object mapping path -> line limit")

    parsed: dict[str, int] = {}
    for path, limit in data.items():
        if not isinstance(path, str):
            raise ValueError(f"Guardrail key must be a string path: {path!r}")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"Guardrail limit for {path!r} must be a positive integer")
        parsed[path] = limit
    return parsed


def count_lines(path: Path) -> int:
    """Return total line count for a file."""
    return sum(1 for _ in path.open("r", encoding="utf-8"))


def main() -> int:
    """Run the guardrail check."""
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "config/module_size_guardrails.json"
    guardrails = load_guardrails(config_path)

    violations: list[tuple[str, int, int]] = []
    missing: list[str] = []

    for rel_path, limit in guardrails.items():
        file_path = repo_root / rel_path
        if not file_path.exists():
            missing.append(rel_path)
            continue
        line_count = count_lines(file_path)
        if line_count > limit:
            violations.append((rel_path, line_count, limit))

    if missing:
        print("Missing guardrail targets:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    if violations:
        print("Module size guardrail violations:")
        for rel_path, line_count, limit in violations:
            print(f"- {rel_path}: {line_count} lines (limit {limit})")
        return 1

    print(f"Module size guardrails OK ({len(guardrails)} files checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
