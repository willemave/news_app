"""Tests for analyze_url task handling in the sequential task processor."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import Mock

from app.constants import SELF_SUBMISSION_SOURCE
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.pipeline import sequential_task_processor as stp
from app.services.content_analyzer import (
    ContentAnalysisOutput,
    ContentAnalysisResult,
    InstructionLink,
    InstructionResult,
)


def _build_analysis_output(url: str) -> ContentAnalysisOutput:
    """Create a deterministic analyzer output with instruction links."""
    return ContentAnalysisOutput(
        analysis=ContentAnalysisResult(content_type="article", original_url=url),
        instruction=InstructionResult(
            text="Related links",
            links=[InstructionLink(url="https://example.com/related")],
        ),
    )


def _create_content(db_session, user_id: int, url: str) -> Content:
    """Create a minimal content row for analyze_url tests."""
    content = Content(
        url=url,
        content_type=ContentType.UNKNOWN.value,
        status=ContentStatus.NEW.value,
        source=SELF_SUBMISSION_SOURCE,
        content_metadata={
            "submitted_by_user_id": user_id,
            "submitted_via": "share_sheet",
        },
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


def _patch_processor_dependencies(db_session, monkeypatch, analyzer_output: ContentAnalysisOutput):
    stub_analyzer = Mock()
    stub_analyzer.analyze_url.return_value = analyzer_output

    @contextmanager
    def _db_context():
        yield db_session

    monkeypatch.setattr(stp, "get_db", _db_context)
    monkeypatch.setattr(stp, "get_content_analyzer", lambda: stub_analyzer)
    monkeypatch.setattr(stp, "get_llm_service", lambda: None)

    return stub_analyzer


def test_analyze_url_skips_instruction_links_when_crawl_disabled(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://example.com/article")
    analysis_output = _build_analysis_output(content.url)

    stub_analyzer = _patch_processor_dependencies(db_session, monkeypatch, analysis_output)
    create_mock = Mock(return_value=[])
    monkeypatch.setattr(stp, "create_contents_from_instruction_links", create_mock)

    processor = stp.SequentialTaskProcessor()
    processor.queue_service.enqueue = Mock()

    task_data = {
        "task_type": stp.TaskType.ANALYZE_URL.value,
        "payload": {
            "content_id": content.id,
            "instruction": "Find related links",
            "crawl_links": False,
        },
    }

    assert processor._process_analyze_url_task(task_data) is True
    stub_analyzer.analyze_url.assert_called_once()
    create_mock.assert_not_called()


def test_analyze_url_creates_instruction_links_when_crawl_enabled(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://example.com/article")
    analysis_output = _build_analysis_output(content.url)

    stub_analyzer = _patch_processor_dependencies(db_session, monkeypatch, analysis_output)
    create_mock = Mock(return_value=[])
    monkeypatch.setattr(stp, "create_contents_from_instruction_links", create_mock)

    processor = stp.SequentialTaskProcessor()
    processor.queue_service.enqueue = Mock()

    task_data = {
        "task_type": stp.TaskType.ANALYZE_URL.value,
        "payload": {
            "content_id": content.id,
            "crawl_links": True,
        },
    }

    assert processor._process_analyze_url_task(task_data) is True
    stub_analyzer.analyze_url.assert_called_once_with(
        content.url,
        instruction="Extract relevant links from the submitted page.",
    )
    create_mock.assert_called_once()
