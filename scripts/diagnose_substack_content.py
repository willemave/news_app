#!/usr/bin/env python3
"""Diagnose live Substack processing issues for specific content IDs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Sequence

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.core.db import get_session_factory
from app.core.logging import setup_logging
from app.http_client.robust_http_client import RobustHttpClient
from app.models.schema import Content
from app.processing_strategies.html_strategy import HtmlProcessorStrategy


class DiagnosisArgs(BaseModel):
    """CLI argument payload for diagnostics."""

    content_ids: list[int] = Field(..., min_length=1, description="Content IDs to inspect")
    timeout_seconds: float = Field(default=20.0, gt=0, description="HTTP timeout in seconds")


@dataclass
class FetchDebug:
    """Debug snapshot for a live HTTP fetch."""

    requested_url: str
    status_code: int | None
    final_url: str | None
    content_length: int
    text_sample: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert into JSON-compatible payload."""

        return {
            "requested_url": self.requested_url,
            "status_code": self.status_code,
            "final_url": self.final_url,
            "content_length": self.content_length,
            "text_sample": self.text_sample,
            "error": self.error,
        }


@dataclass
class StrategyDebug:
    """Snapshot of HTML strategy extraction."""

    processed_url: str
    title: str | None
    text_length: int
    exception: str | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert into JSON-compatible payload."""

        return {
            "processed_url": self.processed_url,
            "title": self.title,
            "text_length": self.text_length,
            "exception": self.exception,
            "metadata": self.metadata,
        }


@dataclass
class DiagnosisRecord:
    """Full diagnostic payload for a content record."""

    content_id: int
    db_status: str | None
    stored_word_count: int
    stored_text_snippet: str
    rss_word_count: int
    rss_text_snippet: str
    fetch_debug: FetchDebug
    strategy_debug: StrategyDebug

    def to_dict(self) -> dict[str, Any]:
        """Convert record into JSON-compatible form."""

        return {
            "content_id": self.content_id,
            "db_status": self.db_status,
            "stored_word_count": self.stored_word_count,
            "stored_text_snippet": self.stored_text_snippet,
            "rss_word_count": self.rss_word_count,
            "rss_text_snippet": self.rss_text_snippet,
            "fetch": self.fetch_debug.to_dict(),
            "strategy": self.strategy_debug.to_dict(),
        }


def parse_args(argv: Sequence[str] | None = None) -> DiagnosisArgs:
    """Parse CLI arguments.

    Args:
        argv: Optional list of raw CLI arguments.

    Returns:
        DiagnosisArgs: Validated argument payload.
    """

    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument("content_ids", nargs="+", type=int, help="Content IDs to diagnose")
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP client timeout in seconds (default: 20)",
    )
    parsed = parser.parse_args(argv)
    return DiagnosisArgs(content_ids=list(parsed.content_ids), timeout_seconds=parsed.timeout)


def _html_to_text(html: str) -> str:
    """Convert HTML into normalized plain text.

    Args:
        html: HTML string.

    Returns:
        str: Collapsed plaintext with newlines preserved between blocks.
    """

    soup = BeautifulSoup(html or "", "html.parser")
    text = soup.get_text("\n", strip=True)
    collapsed = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return collapsed.strip()


def fetch_live_page(url: str, timeout_seconds: float) -> FetchDebug:
    """Perform a live HTTP GET request to fetch the article.

    Args:
        url: Target URL.
        timeout_seconds: Request timeout.

    Returns:
        FetchDebug: Debug payload for the HTTP fetch.
    """

    try:
        headers = {
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
            ),
        }
        with httpx.Client(follow_redirects=True, timeout=timeout_seconds, headers=headers) as client:
            response = client.get(url)
        text_sample = response.text[:400]
        return FetchDebug(
            requested_url=url,
            status_code=response.status_code,
            final_url=str(response.url),
            content_length=len(response.text),
            text_sample=text_sample,
        )
    except Exception as exc:  # pragma: no cover - network failure handling
        return FetchDebug(
            requested_url=url,
            status_code=None,
            final_url=None,
            content_length=0,
            text_sample="",
            error=f"{type(exc).__name__}: {exc}",
        )


def run_html_strategy(url: str) -> StrategyDebug:
    """Execute HtmlProcessorStrategy to mirror worker behaviour.

    Args:
        url: Article URL to process.

    Returns:
        StrategyDebug: Debug payload from the strategy execution.
    """

    strategy = HtmlProcessorStrategy(RobustHttpClient())
    processed_url = strategy.preprocess_url(url)

    try:
        strategy.download_content(processed_url)
        extracted = strategy.extract_data(processed_url, processed_url)
        llm_payload = strategy.prepare_for_llm(extracted)
        text_content = extracted.get("text_content") or ""
        metadata_snapshot = {
            "content_type": extracted.get("content_type"),
            "source": extracted.get("source"),
            "final_url_after_redirects": extracted.get("final_url_after_redirects"),
            "publication_date": extracted.get("publication_date"),
            "llm_payload_length": len((llm_payload or {}).get("content_to_summarize", "")),
        }
        return StrategyDebug(
            processed_url=processed_url,
            title=extracted.get("title"),
            text_length=len(text_content),
            exception=None,
            metadata=metadata_snapshot,
        )
    except Exception as exc:  # pragma: no cover - diagnostic path
        return StrategyDebug(
            processed_url=processed_url,
            title=None,
            text_length=0,
            exception=f"{type(exc).__name__}: {exc}",
            metadata={},
        )


def diagnose_content(
    session_factory, content_id: int, timeout_seconds: float
) -> DiagnosisRecord:
    """Produce a diagnostic record for a single content row.

    Args:
        session_factory: SQLAlchemy session factory.
        content_id: Target content identifier.
        timeout_seconds: Timeout for live HTTP fetches.

    Returns:
        DiagnosisRecord: Detailed diagnostic payload.
    """

    with session_factory() as session:
        content = session.get(Content, content_id)

    if content is None:
        fetch_debug = FetchDebug(
            requested_url="<unknown>",
            status_code=None,
            final_url=None,
            content_length=0,
            text_sample="",
            error="Content not found",
        )
        strategy_debug = StrategyDebug(
            processed_url="<unknown>",
            title=None,
            text_length=0,
            exception="Content not found",
            metadata={},
        )
        return DiagnosisRecord(
            content_id=content_id,
            db_status=None,
            stored_word_count=0,
            stored_text_snippet="",
            rss_word_count=0,
            rss_text_snippet="",
            fetch_debug=fetch_debug,
            strategy_debug=strategy_debug,
        )

    metadata = content.content_metadata or {}
    stored_text = (metadata.get("content") or "").strip()
    rss_html = metadata.get("rss_content") or ""
    rss_text = _html_to_text(rss_html) if rss_html else ""

    fetch_debug = fetch_live_page(content.url, timeout_seconds)
    strategy_debug = run_html_strategy(content.url)

    return DiagnosisRecord(
        content_id=content.id,
        db_status=content.status,
        stored_word_count=len(stored_text.split()),
        stored_text_snippet=stored_text[:200],
        rss_word_count=len(rss_text.split()),
        rss_text_snippet=rss_text[:200],
        fetch_debug=fetch_debug,
        strategy_debug=strategy_debug,
    )


def run_diagnostics(args: DiagnosisArgs) -> list[DiagnosisRecord]:
    """Run diagnostics for all requested content IDs.

    Args:
        args: Validated CLI arguments.

    Returns:
        list[DiagnosisRecord]: Diagnostic records.
    """

    session_factory = get_session_factory()
    return [diagnose_content(session_factory, cid, args.timeout_seconds) for cid in args.content_ids]


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point.

    Args:
        argv: Optional raw CLI arguments.

    Returns:
        int: Process exit code.
    """

    args = parse_args(argv)
    setup_logging(level="DEBUG")
    records = run_diagnostics(args)
    payload = [record.to_dict() for record in records]
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry guard
    raise SystemExit(main())
