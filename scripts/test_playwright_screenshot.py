#!/usr/bin/env python3
"""Playwright smoke test for screenshot capture.

Usage:
    python scripts/test_playwright_screenshot.py --url https://example.com \
        --output static/images/news_thumbnails/playwright_test.png

    python scripts/test_playwright_screenshot.py --url https://example.com \
        --output static/images/news_thumbnails/playwright_test.png --channel chrome
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TypedDict

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


class ScreenshotRequest(TypedDict):
    url: str
    output_path: Path
    viewport_width: int
    viewport_height: int
    timeout_ms: int
    network_idle_timeout_ms: int
    headless: bool
    channel: str | None
    no_sandbox: bool
    wait_ms: int


class ScreenshotResult(TypedDict):
    success: bool
    output_path: str | None
    error_message: str | None


def _build_request(args: argparse.Namespace) -> ScreenshotRequest:
    return {
        "url": args.url,
        "output_path": Path(args.output),
        "viewport_width": args.viewport_width,
        "viewport_height": args.viewport_height,
        "timeout_ms": args.timeout_ms,
        "network_idle_timeout_ms": args.network_idle_timeout_ms,
        "headless": not args.headful,
        "channel": args.channel,
        "no_sandbox": args.no_sandbox,
        "wait_ms": args.wait_ms,
    }


def _capture_screenshot(request: ScreenshotRequest) -> ScreenshotResult:
    output_path = request["output_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    launch_args = []
    if request["no_sandbox"]:
        launch_args.append("--no-sandbox")

    try:
        with sync_playwright() as playwright:
            if request["channel"]:
                browser = playwright.chromium.launch(
                    headless=request["headless"],
                    channel=request["channel"],
                    args=launch_args,
                )
            else:
                browser = playwright.chromium.launch(
                    headless=request["headless"],
                    args=launch_args,
                )

            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size(
                {
                    "width": request["viewport_width"],
                    "height": request["viewport_height"],
                }
            )

            page.goto(request["url"], wait_until="domcontentloaded", timeout=request["timeout_ms"])
            try:
                page.wait_for_load_state("networkidle", timeout=request["network_idle_timeout_ms"])
            except PlaywrightTimeoutError:
                print("[warn] networkidle timeout, continuing")

            if request["wait_ms"]:
                page.wait_for_timeout(request["wait_ms"])

            page.screenshot(path=str(output_path), full_page=False, type="png")

            context.close()
            browser.close()

        return {
            "success": True,
            "output_path": str(output_path),
            "error_message": None,
        }

    except PlaywrightTimeoutError as exc:
        return {
            "success": False,
            "output_path": None,
            "error_message": f"Timeout: {exc}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "output_path": None,
            "error_message": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Playwright screenshot smoke test")
    parser.add_argument("--url", required=True, help="Target URL to capture")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--viewport-width", type=int, default=1024)
    parser.add_argument("--viewport-height", type=int, default=1024)
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--network-idle-timeout-ms", type=int, default=5000)
    parser.add_argument("--wait-ms", type=int, default=1000, help="Extra wait before screenshot")
    parser.add_argument("--headful", action="store_true", help="Run non-headless")
    parser.add_argument("--channel", default=None, help="Playwright browser channel (e.g., chrome)")
    parser.add_argument("--no-sandbox", action="store_true", help="Launch with --no-sandbox")
    args = parser.parse_args()

    request = _build_request(args)
    result = _capture_screenshot(request)

    if result["success"]:
        print(f"[ok] screenshot saved: {result['output_path']}")
        return 0

    print(f"[error] screenshot failed: {result['error_message']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
