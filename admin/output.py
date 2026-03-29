"""Output helpers for the operator CLI."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, TextIO


@dataclass(frozen=True)
class EnvelopeError:
    """Serializable error payload."""

    message: str
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class Envelope:
    """Stable CLI envelope."""

    ok: bool
    command: str
    data: Any = None
    warnings: list[str] = field(default_factory=list)
    error: EnvelopeError | None = None


def emit(envelope: Envelope, output_format: str, stream: TextIO | None = None) -> None:
    """Write an envelope in the requested format."""
    target = stream or sys.stdout
    if output_format == "text":
        target.write(_format_text(envelope))
        if not _format_text(envelope).endswith("\n"):
            target.write("\n")
        return

    payload = {
        "ok": envelope.ok,
        "command": envelope.command,
        "data": envelope.data,
    }
    if envelope.warnings:
        payload["warnings"] = envelope.warnings
    if envelope.error is not None:
        payload["error"] = {
            "message": envelope.error.message,
            "details": envelope.error.details,
        }
    json.dump(payload, target, ensure_ascii=False, indent=2, default=str)
    target.write("\n")


def _format_text(envelope: Envelope) -> str:
    if envelope.ok:
        if isinstance(envelope.data, str):
            body = envelope.data
        else:
            body = json.dumps(envelope.data, ensure_ascii=False, indent=2, default=str)
        if envelope.warnings:
            warning_block = "\n".join(f"warning: {warning}" for warning in envelope.warnings)
            return f"{body}\n{warning_block}"
        return body

    body = envelope.error.message if envelope.error is not None else "Unknown error"
    if envelope.error and envelope.error.details:
        details = json.dumps(envelope.error.details, ensure_ascii=False, indent=2, default=str)
        return f"error: {body}\n{details}"
    return f"error: {body}"
