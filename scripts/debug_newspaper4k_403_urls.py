#!/usr/bin/env python3
"""Probe newspaper4k behavior for production 403 HTML URLs.

Usage:
    .venv/bin/python scripts/debug_newspaper4k_403_urls.py URL [URL ...]
    printf '%s\n' URL ... | .venv/bin/python scripts/debug_newspaper4k_403_urls.py

The script intentionally accepts URLs as input instead of hardcoding tokenized
share links into the repository.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from textwrap import shorten

import newspaper


@dataclass(frozen=True)
class ProbeResult:
    url: str
    ok: bool
    title: str | None = None
    text_length: int = 0
    authors: tuple[str, ...] = ()
    publish_date: str | None = None
    error: str | None = None
    preview: str | None = None


def _read_urls(argv: list[str]) -> list[str]:
    if argv:
        return argv
    return [line.strip() for line in sys.stdin if line.strip()]


def _probe_url(url: str) -> ProbeResult:
    try:
        article = newspaper.article(url)
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic script.
        return ProbeResult(
            url=url,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    title = (getattr(article, "title", None) or "").strip() or None
    text = (getattr(article, "text", None) or "").strip()
    authors = tuple(getattr(article, "authors", None) or ())
    publish_date = getattr(article, "publish_date", None)
    return ProbeResult(
        url=url,
        ok=bool(text),
        title=title,
        text_length=len(text),
        authors=authors,
        publish_date=str(publish_date) if publish_date else None,
        preview=shorten(" ".join(text.split()), width=220, placeholder="...") if text else None,
    )


def main() -> int:
    urls = _read_urls(sys.argv[1:])
    if not urls:
        print("Provide URLs as args or newline-delimited stdin.", file=sys.stderr)
        return 2

    for index, result in enumerate((_probe_url(url) for url in urls), start=1):
        print(f"\n[{index}] {result.url}")
        print(f"  newspaper4k_ok: {result.ok}")
        if result.error:
            print(f"  error: {result.error}")
            continue
        print(f"  title: {result.title!r}")
        print(f"  text_length: {result.text_length}")
        print(f"  authors: {list(result.authors)!r}")
        print(f"  publish_date: {result.publish_date!r}")
        print(f"  preview: {result.preview!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
