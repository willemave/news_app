"""Utility helpers for resolving repo-relative configuration paths."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR_ENV = "NEWSAPP_CONFIG_DIR"


def _resolve_candidate_paths(raw: str) -> Iterable[Path]:
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        yield candidate.resolve(strict=False)
    else:
        yield (Path.cwd() / candidate).resolve(strict=False)
        yield (PROJECT_ROOT / candidate).resolve(strict=False)


def resolve_config_directory() -> Path:
    """Determine the base configuration directory with environment override."""

    raw_dir = os.getenv(CONFIG_DIR_ENV)
    if raw_dir:
        candidates = list(_resolve_candidate_paths(raw_dir))
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        logger.warning(
            "%s=%s not found (checked: %s); falling back to default",
            CONFIG_DIR_ENV,
            raw_dir,
            ", ".join(str(path) for path in candidates),
        )
        # return first candidate even if missing to aid path resolution below
        return candidates[0]

    default_dir = (PROJECT_ROOT / "config").resolve()
    if not default_dir.exists():
        logger.warning("Default config directory missing at %s", default_dir)
    return default_dir


def resolve_config_path(env_var: str, default_rel: str) -> Path:
    """Resolve configuration path using env overrides with graceful fallbacks.

    Args:
        env_var: Environment variable name to check for an override.
        default_rel: Repo-relative path used when no override resolves.

    Returns:
        Resolved absolute ``Path`` pointing to the desired configuration file.
    """

    raw_value = os.getenv(env_var)
    if raw_value:
        for candidate in _resolve_candidate_paths(raw_value):
            candidate_resolved = candidate.resolve(strict=False)
            if candidate_resolved.exists():
                return candidate_resolved
        logger.warning(
            "%s=%s did not resolve to an existing file; falling back to defaults",
            env_var,
            raw_value,
        )

    config_dir = resolve_config_directory()
    default_path = Path(default_rel)

    candidates: list[Path] = []
    if default_path.is_absolute():
        candidates.append(default_path)
    else:
        candidates.append((config_dir / default_path.name).resolve(strict=False))
        candidates.append((config_dir / default_path).resolve(strict=False))
        candidates.append((PROJECT_ROOT / default_path).resolve(strict=False))

    seen: set[str] = set()
    ordered_candidates: list[Path] = []
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            ordered_candidates.append(path)

    for candidate in ordered_candidates:
        if candidate.exists():
            return candidate

    logger.warning(
        "Config file missing. Searched: %s",
        ", ".join(str(path) for path in ordered_candidates),
    )
    return ordered_candidates[0]
