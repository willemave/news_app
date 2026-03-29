"""Smoke tests for the news pipeline eval scripts."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.models.news_pipeline_eval_models import (
    NewsPipelineEvalRunResult,
    NewsPipelineEvalSuiteResult,
)
from app.models.schema import NewsItem
from app.services.news_pipeline_eval import load_eval_case
from scripts import (
    export_news_pipeline_eval_cases,
    generate_news_pipeline_eval_html_report,
    run_news_pipeline_embedding_matrix,
    run_news_pipeline_eval,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "evals"
    / "news_shortform"
    / "pipeline_cases"
    / "synthetic_smoke.json"
)


def test_export_news_pipeline_eval_cases_writes_snapshot_case(
    db_session,
    test_user,
    monkeypatch,
    tmp_path,
) -> None:
    global_item = NewsItem(
        ingest_key="global-item",
        visibility_scope="global",
        platform="hackernews",
        source_type="hackernews",
        source_label="Hacker News",
        source_external_id="global-1",
        canonical_item_url="https://news.ycombinator.com/item?id=1",
        canonical_story_url="https://example.com/global-story",
        article_url="https://example.com/global-story",
        article_title="Global story",
        article_domain="example.com",
        discussion_url="https://news.ycombinator.com/item?id=1",
        summary_title="Global story",
        summary_key_points=["Global point."],
        summary_text="Global summary.",
        raw_metadata={"discussion_payload": {"compact_comments": []}},
        status="ready",
        ingested_at=datetime.now(UTC).replace(tzinfo=None),
    )
    user_item = NewsItem(
        ingest_key="user-item",
        visibility_scope="user",
        owner_user_id=test_user.id,
        platform="twitter",
        source_type="x_timeline",
        source_label="X Following",
        source_external_id="user-1",
        canonical_item_url="https://x.com/i/status/user-1",
        canonical_story_url="https://x.com/i/status/user-1",
        article_url="https://x.com/i/status/user-1",
        article_title="User story",
        article_domain="x.com",
        discussion_url="https://x.com/i/status/user-1",
        summary_title="User story",
        summary_key_points=["User point."],
        summary_text="User summary.",
        raw_metadata={
            "discussion_payload": {"compact_comments": []},
            "submitted_by_user_id": test_user.id,
        },
        status="ready",
        ingested_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add_all([global_item, user_item])
    db_session.commit()

    @contextmanager
    def fake_get_db():
        yield db_session

    monkeypatch.setattr(export_news_pipeline_eval_cases, "get_db", fake_get_db)

    output_path = tmp_path / "snapshot_case.json"
    exit_code = export_news_pipeline_eval_cases.main(
        [
            "--output",
            str(output_path),
            "--user-id",
            str(test_user.id),
            "--include-global",
            "--include-user-scoped",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["mode"] == "snapshot"
    assert payload["input_mode"] == "news_item_records"
    assert payload["user"]["user_id"] == test_user.id
    assert len(payload["news_item_records"]) == 2


def test_run_news_pipeline_eval_writes_artifact(monkeypatch, tmp_path) -> None:
    result = NewsPipelineEvalRunResult(
        case_id="synthetic_smoke",
        mode="synthetic",
        digest_id=1,
        digest_title="Synthetic digest",
        digest_summary="Synthetic summary.",
        source_count=5,
        curated_group_count=2,
        ingest_created_count=5,
        ingest_updated_count=0,
        processed_count=5,
        generated_summary_count=2,
        reused_summary_count=2,
        skipped_processing_count=0,
        failed_processing_count=0,
        citation_validity=1.0,
        failures=[],
        passed=True,
    )
    suite = NewsPipelineEvalSuiteResult(case_count=1, passed=True, results=[result])
    monkeypatch.setattr(
        run_news_pipeline_eval,
        "run_eval_cases",
        lambda **kwargs: suite,
    )

    artifacts_dir = tmp_path / "artifacts"
    html_report_path = tmp_path / "eval-report.html"
    exit_code = run_news_pipeline_eval.main(
        [
            "--input",
            str(FIXTURE_PATH),
            "--artifacts-dir",
            str(artifacts_dir),
            "--html-report",
            str(html_report_path),
        ]
    )

    artifact_payload = json.loads((artifacts_dir / "synthetic_smoke.json").read_text("utf-8"))

    assert exit_code == 0
    assert artifact_payload["case_id"] == "synthetic_smoke"
    assert artifact_payload["passed"] is True
    assert html_report_path.exists()
    assert "synthetic_smoke" in html_report_path.read_text(encoding="utf-8")


def test_generate_news_pipeline_eval_html_report_from_saved_artifacts(tmp_path) -> None:
    case = load_eval_case(FIXTURE_PATH)
    artifact = NewsPipelineEvalRunResult(
        case_id=case.case_id,
        mode=case.mode,
        digest_id=1,
        digest_title="Synthetic digest",
        digest_summary="Synthetic summary.",
        source_count=5,
        curated_group_count=2,
        ingest_created_count=5,
        ingest_updated_count=0,
        processed_count=5,
        generated_summary_count=2,
        reused_summary_count=2,
        skipped_processing_count=0,
        failed_processing_count=0,
        citation_validity=1.0,
        bullets=[
            {
                "position": 1,
                "topic": "Top story",
                "details": "One grounded bullet.",
                "news_item_ids": [1, 2],
            }
        ],
        items=[],
        failures=[],
        passed=True,
    )
    cases_dir = tmp_path / "cases"
    artifacts_dir = tmp_path / "artifacts"
    cases_dir.mkdir()
    artifacts_dir.mkdir()
    case_path = cases_dir / "synthetic_smoke.json"
    case_path.write_text(case.model_dump_json(indent=2), encoding="utf-8")
    (artifacts_dir / "synthetic_smoke.json").write_text(
        artifact.model_dump_json(indent=2),
        encoding="utf-8",
    )
    output_path = tmp_path / "report.html"

    exit_code = generate_news_pipeline_eval_html_report.main(
        [
            "--input",
            str(case_path),
            "--artifacts-dir",
            str(artifacts_dir),
            "--output",
            str(output_path),
            "--title",
            "Synthetic Eval",
        ]
    )

    html = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "Synthetic Eval" in html
    assert "Top story" in html


def test_run_news_pipeline_embedding_matrix_writes_comparison_report(monkeypatch, tmp_path) -> None:
    def fake_build_variant_result(
        *,
        case,
        embedding_model,
        threshold,
        max_candidates,
        allow_summary_generation,
    ):
        del allow_summary_generation
        return NewsPipelineEvalRunResult(
            case_id=f"{case.case_id}__{embedding_model.replace('/', '-')}__{threshold.label}",
            mode=case.mode,
            run_config={
                "label": threshold.label,
                "base_case_id": case.case_id,
                "embedding_model": embedding_model,
                "primary_similarity_threshold": threshold.primary,
                "secondary_similarity_threshold": threshold.secondary,
                "max_candidates": max_candidates,
            },
            digest_id=1,
            digest_title=f"{embedding_model} / {threshold.label}",
            digest_summary="Synthetic comparison run.",
            source_count=5,
            curated_group_count=2,
            ingest_created_count=5,
            ingest_updated_count=0,
            processed_count=5,
            generated_summary_count=0,
            reused_summary_count=5,
            skipped_processing_count=0,
            failed_processing_count=0,
            citation_validity=1.0,
            bullets=[
                {
                    "position": 1,
                    "topic": "Top story",
                    "details": "One grounded bullet.",
                    "news_item_ids": [1, 2],
                }
            ],
            items=[],
            failures=[],
            passed=True,
        )

    monkeypatch.setattr(
        run_news_pipeline_embedding_matrix,
        "_build_variant_result",
        fake_build_variant_result,
    )

    html_report_path = tmp_path / "matrix-report.html"
    artifacts_dir = tmp_path / "artifacts"
    exit_code = run_news_pipeline_embedding_matrix.main(
        [
            "--input",
            str(FIXTURE_PATH),
            "--embedding-model",
            "Qwen/Qwen3-Embedding-0.6B",
            "--embedding-model",
            "google/embeddinggemma-300m",
            "--threshold",
            "default:0.86:0.82",
            "--threshold",
            "strict:0.90:0.86",
            "--artifacts-dir",
            str(artifacts_dir),
            "--html-report",
            str(html_report_path),
        ]
    )

    html = html_report_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "Run Comparison" in html
    assert "google/embeddinggemma-300m" in html
    assert "Qwen/Qwen3-Embedding-0.6B" in html
