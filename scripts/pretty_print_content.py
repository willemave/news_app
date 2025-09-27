#!/usr/bin/env python3
"""Pretty print content records by ID or random sample."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

# Ensure project root is importable when executing as a script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.db import get_session_factory, init_db  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.models.metadata import ContentType  # noqa: E402
from app.models.schema import Content  # noqa: E402

logger = get_logger(__name__)


class PrettyPrintArgs(BaseModel):
    """Validated arguments for content pretty printing."""

    content_id: int | None = Field(default=None, ge=1)
    content_type: ContentType | None = Field(default=None)
    count: int = Field(default=3, ge=1, le=50)

    @model_validator(mode="after")
    def validate_target(self) -> "PrettyPrintArgs":
        """Ensure mutually exclusive selection parameters are valid."""

        if self.content_id is None and self.content_type is None:
            raise ValueError("Provide either --content-id or --content-type.")

        if self.content_id is not None and self.content_type is not None:
            raise ValueError("Use only one of --content-id or --content-type, not both.")

        return self


class PrettyContentPayload(BaseModel):
    """Serializable payload representing a content record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int
    content_type: ContentType
    title: str | None
    source: str | None
    platform: str | None
    status: str
    classification: str | None
    is_aggregate: bool
    url: str
    created_at: datetime
    updated_at: datetime | None
    processed_at: datetime | None
    publication_date: datetime | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    structured_summary: dict[str, Any] | None



class PrettyPrintResult(BaseModel):
    """Returned payload for pretty print execution."""

    query: PrettyPrintArgs
    contents: list[PrettyContentPayload]


def build_content_payload(content: Content) -> PrettyContentPayload:
    """Construct a serializable payload for a content row."""

    metadata: dict[str, Any] = content.content_metadata or {}
    structured = content.get_structured_summary()
    structured_summary = structured.model_dump(mode="json") if structured else None

    return PrettyContentPayload(
        id=content.id,
        content_type=ContentType(content.content_type),
        title=content.title,
        source=content.source,
        platform=content.platform,
        status=content.status,
        classification=content.classification,
        is_aggregate=bool(content.is_aggregate),
        url=content.url,
        created_at=content.created_at,
        updated_at=getattr(content, "updated_at", None),
        processed_at=content.processed_at,
        publication_date=content.publication_date,
        metadata=metadata,
        structured_summary=structured_summary,
    )


def fetch_by_id(session: Session, args: PrettyPrintArgs) -> list[PrettyContentPayload]:
    """Fetch a single content record by identifier."""

    record = session.get(Content, args.content_id)
    if record is None:
        raise LookupError(f"Content with ID {args.content_id} was not found.")

    return [build_content_payload(record)]


def fetch_random_by_type(session: Session, args: PrettyPrintArgs) -> list[PrettyContentPayload]:
    """Fetch a random sample for a content type."""

    results = (
        session.query(Content)
        .filter(Content.content_type == args.content_type.value)
        .order_by(func.random())
        .limit(args.count)
        .all()
    )

    if not results:
        raise LookupError(
            f"No content found for content_type='{args.content_type.value}'."
        )

    return [build_content_payload(item) for item in results]


def pretty_print_content(session: Session, args: PrettyPrintArgs) -> PrettyPrintResult:
    """Retrieve and format content records based on provided arguments."""

    if args.content_id is not None:
        contents = fetch_by_id(session, args)
    else:
        contents = fetch_random_by_type(session, args)

    return PrettyPrintResult(query=args, contents=contents)


def parse_arguments(argv: list[str] | None = None) -> PrettyPrintArgs:
    """Parse CLI arguments into a validated payload."""

    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument("--content-id", type=int, help="Fetch a specific content ID")
    parser.add_argument(
        "--content-type",
        type=str,
        choices=[item.value for item in ContentType],
        help="Random sample restricted to this content type",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="Number of random records to fetch when using --content-type (default: 3)",
    )

    namespace = parser.parse_args(argv)

    try:
        return PrettyPrintArgs(**vars(namespace))
    except ValidationError as exc:
        parser.error(str(exc))
        raise


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    try:
        args = parse_arguments(argv)
    except SystemExit:
        return 1

    init_db()
    session_factory = get_session_factory()

    session = session_factory()
    try:
        result = pretty_print_content(session, args)
    except LookupError as error:
        logger.error(str(error))
        print(f"Error: {error}")
        return 1
    except Exception as error:  # pragma: no cover - unexpected failure logging
        logger.exception("Unexpected error while pretty printing content")
        print(f"Unexpected error: {error}")
        return 1
    finally:
        session.close()

    payload = result.model_dump(mode="json", exclude_none=True)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI execution
    raise SystemExit(main())
