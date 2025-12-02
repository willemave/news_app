"""Timing utilities for profiling database and service calls."""

import time
from collections.abc import Generator
from contextlib import contextmanager

from app.core.logging import get_logger

logger = get_logger(__name__)


@contextmanager
def timed(operation: str) -> Generator[None]:
    """Context manager for timing operations.

    Args:
        operation: Description of the operation being timed.

    Usage:
        with timed("fetch user content"):
            results = db.query(Content).all()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        if duration_ms < 50:
            logger.debug(f"[{duration_ms:.2f}ms] {operation}")
        elif duration_ms < 200:
            logger.info(f"[{duration_ms:.2f}ms] {operation} (slow)")
        else:
            logger.warning(f"[{duration_ms:.2f}ms] {operation} (very slow)")
