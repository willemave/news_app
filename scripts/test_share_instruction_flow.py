#!/usr/bin/env python3
"""Quick script to exercise share-sheet instruction submission via the API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit a URL with instruction to Newsly")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", required=True, help="Bearer access token")
    parser.add_argument("--url", required=True, help="URL to submit")
    parser.add_argument(
        "--instruction",
        default="",
        help="Instruction for the analyzer (optional)",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    payload = {"url": args.url}
    if args.instruction:
        payload["instruction"] = args.instruction

    endpoint = args.base_url.rstrip("/") + "/api/content/submit"
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {args.token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            print(f"Status: {response.status}")
            print(body)
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        print(f"HTTPError: {exc.code}")
        print(body)
        return 1
    except urllib.error.URLError as exc:
        print(f"Request failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
