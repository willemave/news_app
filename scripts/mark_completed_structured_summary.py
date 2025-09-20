#!/usr/bin/env python3
"""Set `Content.status` to completed when a structured summary exists."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import get_logger  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from app.models.metadata import StructuredSummary  # noqa: E402
from app.models.schema import Content, ContentStatus  # noqa: E402

logger = get_logger(__name__)


class ScriptOptions(BaseModel):
    """Validated configuration for the status backfill script."""

    model_config = ConfigDict(extra="forbid")

    dry_run: bool = Field(
        default=False, description="Log actions without persisting changes."
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description="Optional upper bound on number of rows to inspect.",
    )
    batch_size: int = Field(
        default=200,
        ge=1,
        le=2000,
        description="Number of rows to load per batch when scanning.",
    )


@dataclass(slots=True)
class ScriptResult:
    """Aggregated outcome metrics for the script run."""

    processed: int = 0
    updated: int = 0
    skipped_missing_summary: int = 0


def parse_args(argv: list[str]) -> ScriptOptions:
    """Parse CLI arguments into validated options.

    Args:
        argv: Raw CLI arguments.

    Returns:
        Parsed and validated script options.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log intended updates without saving changes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of records to inspect.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Number of rows to iterate per batch (default: 200).",
    )

    args = parser.parse_args(argv)

    return ScriptOptions(dry_run=args.dry_run, limit=args.limit, batch_size=args.batch_size)


def update_content_status(session: Session, options: ScriptOptions) -> ScriptResult:
    """Update content rows that have structured summaries but lack completed status.

    Args:
        session: Active SQLAlchemy session.
        options: Execution options for the script.

    Returns:
        Aggregated outcome metrics.
    """

    result = ScriptResult()

    query = (
        session.query(Content)
        .filter(Content.status != ContentStatus.COMPLETED.value)
        .filter(Content.content_metadata.isnot(None))
        .order_by(Content.id.asc())
    )

    if options.limit is not None:
        query = query.limit(options.limit)

    for content in iterate_in_batches(query, options.batch_size):
        result.processed += 1

        summary = safe_get_structured_summary(content)
        if summary is None:
            result.skipped_missing_summary += 1
            continue

        logger.info(
            "Marking content %s as completed (summary title: %s)",
            content.id,
            summary.title,
        )

        if options.dry_run:
            result.updated += 1
            continue

        apply_completion_updates(content, summary)
        result.updated += 1

    if options.dry_run:
        session.rollback()
    else:
        session.commit()

    return result


def iterate_in_batches(query, batch_size: int) -> Iterable[Content]:
    """Yield query results in fixed-size batches.

    Args:
        query: SQLAlchemy query for `Content` rows.
        batch_size: Number of rows to process per batch.

    Yields:
        Individual `Content` instances.
    """

    for content in query.yield_per(batch_size):
        yield content


def safe_get_structured_summary(content: Content) -> StructuredSummary | None:
    """Return structured summary when populated and valid.

    Args:
        content: Database row to inspect.

    Returns:
        Structured summary instance if populated; otherwise None.
    """

    summary = content.get_structured_summary()
    if summary is None:
        return None

    if not summary.overview.strip() or not summary.bullet_points:
        return None

    populated_bullets = [bullet for bullet in summary.bullet_points if bullet.text.strip()]
    if not populated_bullets:
        return None

    return summary


def apply_completion_updates(content: Content, summary: StructuredSummary) -> None:
    """Set completion metadata on the provided content row.

    Args:
        content: Database row being updated.
        summary: Structured summary that justifies completion.
    """

    content.status = ContentStatus.COMPLETED.value
    content.error_message = None

    processed_at = summary.summarization_date or datetime.utcnow()
    if processed_at.tzinfo is not None:
        processed_at = processed_at.astimezone(timezone.utc).replace(tzinfo=None)

    content.processed_at = processed_at


def run(options: ScriptOptions) -> ScriptResult:
    """Execute the completion backfill script using the provided options.

    Args:
        options: Validated CLI options.

    Returns:
        Aggregated outcome metrics from the run.
    """

    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    try:
        with session_factory() as session:
            result = update_content_status(session, options)
    except Exception:
        logger.exception("Failed to update content completion statuses")
        raise
    finally:
        engine.dispose()

    return result


def main(argv: list[str]) -> ScriptResult:
    """Script entry point for CLI usage.

    Args:
        argv: Raw CLI arguments (excluding program name).

    Returns:
        Outcome metrics from the run.
    """

    options = parse_args(argv)
    result = run(options)

    logger.info(
        "Completed status backfill: processed=%s updated=%s skipped_missing_summary=%s",
        result.processed,
        result.updated,
        result.skipped_missing_summary,
    )

    print(
        (
            "Processed {processed} rows | Updated {updated} | "
            "Skipped (missing summary) {skipped}"
        ).format(
            processed=result.processed,
            updated=result.updated,
            skipped=result.skipped_missing_summary,
        )
    )

    return result


if __name__ == "__main__":
    main(sys.argv[1:])
