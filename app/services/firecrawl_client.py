"""Firecrawl scrape client for HTML extraction fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.services.vendor_costs import record_vendor_usage_out_of_band

logger = get_logger(__name__)

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"


class FirecrawlClientError(RuntimeError):
    """Base exception for Firecrawl client failures."""


class FirecrawlUnavailableError(FirecrawlClientError):
    """Raised when Firecrawl is required but not configured."""


class FirecrawlRequestError(FirecrawlClientError):
    """Raised when Firecrawl returns an error or invalid response."""


@dataclass(frozen=True)
class FirecrawlScrapeResult:
    """Normalized Firecrawl scrape result."""

    url: str
    markdown: str
    title: str | None = None
    source_url: str | None = None
    published_time: str | None = None


def _extract_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return cast(dict[str, Any], data) if isinstance(data, dict) else payload


def _extract_metadata(data: dict[str, Any]) -> dict[str, Any]:
    metadata = data.get("metadata")
    return cast(dict[str, Any], metadata) if isinstance(metadata, dict) else {}


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def scrape_url_with_firecrawl(
    url: str,
    *,
    telemetry: dict[str, Any] | None = None,
) -> FirecrawlScrapeResult:
    """Scrape a public URL with Firecrawl and return Markdown content."""

    settings = get_settings()
    if not settings.firecrawl_api_key:
        raise FirecrawlUnavailableError("Firecrawl API key is not configured")

    request_body = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "removeBase64Images": True,
        "blockAds": True,
        "proxy": "auto",
        "location": {"country": "US", "languages": ["en-US"]},
    }
    headers = {
        "Authorization": f"Bearer {settings.firecrawl_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            FIRECRAWL_SCRAPE_URL,
            headers=headers,
            json=request_body,
            timeout=float(settings.firecrawl_timeout_seconds),
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise FirecrawlRequestError(f"Firecrawl request failed for {url}: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise FirecrawlRequestError(
            f"Firecrawl returned non-JSON response for {url} (status={response.status_code})"
        ) from exc

    data = _extract_data(payload)
    error = payload.get("error") or data.get("error") or data.get("warning")
    if not response.is_success:
        raise FirecrawlRequestError(
            f"Firecrawl scrape failed for {url} (status={response.status_code}): {error or data}"
        )

    markdown = data.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise FirecrawlRequestError(f"Firecrawl scrape returned no markdown for {url}")

    metadata = _extract_metadata(data)
    _record_firecrawl_usage(url=url, telemetry=telemetry, status_code=response.status_code)
    return FirecrawlScrapeResult(
        url=url,
        markdown=markdown.strip(),
        title=_metadata_str(metadata, "title"),
        source_url=_metadata_str(metadata, "sourceURL"),
        published_time=_metadata_str(metadata, "publishedTime"),
    )


def _record_firecrawl_usage(
    *,
    url: str,
    telemetry: dict[str, Any] | None,
    status_code: int,
) -> None:
    context = telemetry or {}
    task_id = context.get("task_id")
    content_id = context.get("content_id")
    record_vendor_usage_out_of_band(
        provider="firecrawl",
        model="scrape-v2",
        feature="html_extraction",
        operation="firecrawl_scrape",
        source="html_strategy",
        usage={"request_count": 1, "resource_count": 1},
        task_id=task_id if isinstance(task_id, int) else None,
        content_id=content_id if isinstance(content_id, int) else None,
        metadata={"url": url, "status_code": status_code},
    )
