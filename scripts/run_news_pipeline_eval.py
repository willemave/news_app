"""Run end-to-end news pipeline eval cases through the real news-native flow."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.news_pipeline_eval import load_eval_cases, run_eval_cases, write_eval_artifact
from app.services.news_pipeline_eval_report import write_news_pipeline_eval_html_report

from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run end-to-end news pipeline eval cases")
    parser.add_argument(
        "--input",
        action="append",
        dest="inputs",
        required=True,
        help="Path to an eval case JSON file (repeatable)",
    )
    parser.add_argument(
        "--mode",
        choices=("synthetic", "snapshot"),
        default=None,
        help="Optional mode filter; all inputs must match when provided",
    )
    parser.add_argument(
        "--allow-summary-generation",
        action="store_true",
        help="Allow snapshot cases to generate new summaries for incomplete items",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path(".tmp/news_pipeline_eval"),
        help="Directory for per-case JSON artifacts",
    )
    parser.add_argument(
        "--no-write-artifacts",
        action="store_true",
        help="Skip writing per-case artifacts",
    )
    parser.add_argument(
        "--html-report",
        type=Path,
        default=None,
        help="Optional path to a generated HTML report for the run",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = _parse_args(argv)
    paths = [Path(raw_path) for raw_path in args.inputs]
    cases = load_eval_cases(paths)
    if args.mode is not None:
        mismatched = [case.case_id for case in cases if case.mode != args.mode]
        if mismatched:
            raise SystemExit(
                f"--mode {args.mode} does not match case mode for: {', '.join(mismatched)}"
            )

    suite = run_eval_cases(
        cases=cases,
        allow_summary_generation=args.allow_summary_generation,
    )
    if not args.no_write_artifacts:
        for result in suite.results:
            write_eval_artifact(result, artifacts_dir=args.artifacts_dir)
    if args.html_report is not None:
        write_news_pipeline_eval_html_report(
            cases=cases,
            suite=suite,
            output_path=args.html_report,
        )

    summary = suite.model_dump(mode="json")
    print(json.dumps(summary, indent=2, sort_keys=True))
    logger.info(
        "Completed news pipeline eval",
        extra={
            "component": "news_pipeline_eval",
            "operation": "run_cases",
            "context_data": {
                "case_count": suite.case_count,
                "passed": suite.passed,
                "artifacts_dir": str(args.artifacts_dir.resolve()),
            },
        },
    )
    return 0 if suite.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
