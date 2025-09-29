"""Utility helpers for resolving repo-relative configuration paths."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
        candidate = Path(raw_value).expanduser()
        if candidate.is_absolute():
            if not candidate.exists():
                logger.warning("%s points to missing file %s", env_var, candidate)
            return candidate

        cwd_candidate = (Path.cwd() / candidate).resolve()
        if cwd_candidate.exists():
            return cwd_candidate

        repo_candidate = (PROJECT_ROOT / candidate).resolve()
        if repo_candidate.exists():
            return repo_candidate

        logger.warning(
            "%s=%s not found in CWD (%s) or repo (%s); falling back to default",
            env_var,
            raw_value,
            cwd_candidate,
            repo_candidate,
        )

    default_path = (PROJECT_ROOT / default_rel).resolve()
    if not default_path.exists():
        logger.warning("Default config missing at %s", default_path)
    return default_path
