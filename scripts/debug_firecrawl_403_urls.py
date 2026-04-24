#!/usr/bin/env python3
"""Probe Firecrawl scrape output for production 403 HTML URLs.

Usage:
    FIRECRAWL_API_KEY=fc-... .venv/bin/python scripts/debug_firecrawl_403_urls.py --defaults
    FIRECRAWL_API_KEY=fc-... .venv/bin/python scripts/debug_firecrawl_403_urls.py URL [URL ...]
    printf '%s\n' URL ... |
        FIRECRAWL_API_KEY=fc-... .venv/bin/python scripts/debug_firecrawl_403_urls.py

Tokenized/share URLs should be passed through argv or stdin instead of being
hardcoded here.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from textwrap import shorten
from typing import Any, cast

import httpx

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"
DEFAULT_URLS: tuple[str, ...] = (
    "https://www.politico.com",
    "https://www.politico.com/news/2026/04/22/sean-plankey-withdraws-nomination-cisa-00887136",
    "https://www.axios.com/pro/fintech-deals/2026/04/21/monk-25-million-startups-ai-accounts-receivable",
    "https://wheelfront.com/this-alberta-startup-sells-no-tech-tractors-for-half-price",
    "https://openai.com/business/workspace-agents",
)


@dataclass(frozen=True)
class FirecrawlResult:
    url: str
    ok: bool
    status_code: int | None
    markdown_length: int
    title: str | None
    source_url: str | None
    error: str | None = None
    preview: str | None = None


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) else None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="URLs to scrape")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("FIRECRAWL_API_KEY"),
        help="Firecrawl API key. Defaults to FIRECRAWL_API_KEY.",
    )
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Include the non-tokenized production 403 URL set.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="Per-request timeout in seconds.",
    )
    return parser.parse_args()


def _read_stdin_urls() -> list[str]:
    if sys.stdin.isatty():
        return []
    return [line.strip() for line in sys.stdin if line.strip()]


def _collect_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []
    if args.defaults:
        urls.extend(DEFAULT_URLS)
    urls.extend(args.urls)
    urls.extend(_read_stdin_urls())
    return list(dict.fromkeys(urls))


def _extract_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return cast(dict[str, Any], data) if isinstance(data, dict) else payload


def _extract_metadata(data: dict[str, Any]) -> dict[str, Any]:
    metadata = data.get("metadata")
    return cast(dict[str, Any], metadata) if isinstance(metadata, dict) else {}


def _scrape_url(client: httpx.Client, api_key: str, url: str) -> FirecrawlResult:
    body = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "removeBase64Images": True,
        "blockAds": True,
        "proxy": "auto",
        "location": {"country": "US", "languages": ["en-US"]},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = client.post(FIRECRAWL_SCRAPE_URL, headers=headers, json=body)
    except httpx.HTTPError as exc:
        return FirecrawlResult(
            url=url,
            ok=False,
            status_code=None,
            markdown_length=0,
            title=None,
            source_url=None,
            error=f"{type(exc).__name__}: {exc}",
        )

    try:
        payload = response.json()
    except ValueError:
        return FirecrawlResult(
            url=url,
            ok=False,
            status_code=response.status_code,
            markdown_length=0,
            title=None,
            source_url=None,
            error=shorten(response.text.strip(), width=240, placeholder="..."),
        )

    data = _extract_data(payload)
    metadata = _extract_metadata(data)
    raw_markdown = data.get("markdown")
    markdown = raw_markdown if isinstance(raw_markdown, str) else ""
    error = payload.get("error") or data.get("error") or data.get("warning")
    normalized_text = " ".join(markdown.split())

    return FirecrawlResult(
        url=url,
        ok=response.is_success and bool(markdown.strip()),
        status_code=response.status_code,
        markdown_length=len(markdown),
        title=_metadata_str(metadata, "title"),
        source_url=_metadata_str(metadata, "sourceURL"),
        error=str(error) if error else None,
        preview=shorten(normalized_text, width=320, placeholder="...") if normalized_text else None,
    )


def main() -> int:
    args = _parse_args()
    if not args.api_key:
        print(
            "Missing Firecrawl API key. Set FIRECRAWL_API_KEY or pass --api-key.",
            file=sys.stderr,
        )
        return 2

    urls = _collect_urls(args)
    if not urls:
        print("Provide URLs, stdin URLs, or --defaults.", file=sys.stderr)
        return 2

    with httpx.Client(timeout=args.timeout, follow_redirects=True) as client:
        for index, url in enumerate(urls, start=1):
            result = _scrape_url(client, args.api_key, url)
            print(f"\n[{index}] {result.url}")
            print(f"  ok: {result.ok}")
            print(f"  status_code: {result.status_code}")
            print(f"  markdown_length: {result.markdown_length}")
            print(f"  title: {result.title!r}")
            print(f"  source_url: {result.source_url!r}")
            if result.error:
                print(f"  error: {result.error}")
            print(f"  preview: {result.preview!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
