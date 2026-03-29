"""Generate a static HTML report from saved news pipeline eval artifacts."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import get_logger, setup_logging
from app.models.news_pipeline_eval_models import (
    NewsPipelineEvalRunResult,
    NewsPipelineEvalSuiteResult,
)
from app.services.news_pipeline_eval import load_eval_cases
from app.services.news_pipeline_eval_report import write_news_pipeline_eval_html_report

logger = get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an HTML report from saved news pipeline eval artifacts"
    )
    parser.add_argument(
        "--input",
        action="append",
        dest="inputs",
        required=True,
        help="Path to an eval case JSON file (repeatable)",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path(".tmp/news_pipeline_eval"),
        help="Directory containing saved per-case artifact JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to the generated HTML report",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Optional report title override",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = _parse_args(argv)
    cases = load_eval_cases([Path(raw_path) for raw_path in args.inputs])
    results = [
        NewsPipelineEvalRunResult.model_validate_json(
            (args.artifacts_dir / f"{case.case_id}.json").read_text(encoding="utf-8")
        )
        for case in cases
    ]
    suite = NewsPipelineEvalSuiteResult(
        case_count=len(results),
        passed=all(result.passed for result in results),
        results=results,
    )
    output_path = write_news_pipeline_eval_html_report(
        cases=cases,
        suite=suite,
        output_path=args.output,
        report_title=args.title,
    )
    logger.info(
        "Generated news pipeline eval HTML report",
        extra={
            "component": "news_pipeline_eval",
            "operation": "generate_html_report",
            "context_data": {
                "case_count": len(results),
                "output": str(output_path.resolve()),
            },
        },
    )
    print(output_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
