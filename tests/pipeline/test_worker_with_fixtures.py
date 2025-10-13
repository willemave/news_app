"""Unit tests for ContentWorker using real data fixtures.

Demonstrates how to use content_samples fixtures in unit tests for more
realistic testing scenarios.
"""
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from app.models.metadata import ContentStatus, ContentType, StructuredSummary, SummaryBulletPoint, ContentQuote
from app.pipeline.worker import ContentWorker


def test_extract_content_metadata_from_article_fixture(sample_article_long: Dict[str, Any]):
    """Test that we can extract and validate metadata from article fixtures."""
    metadata = sample_article_long["content_metadata"]

    # Verify metadata structure matches what worker expects
    assert "content" in metadata
    assert "summary" in metadata
    assert "content_type" in metadata

    # Verify content is HTML as expected
    assert metadata["content_type"] == "html"

    # Verify summary structure
    summary = metadata["summary"]
    assert "title" in summary
    assert "overview" in summary
    assert "bullet_points" in summary
    assert len(summary["bullet_points"]) > 0


def test_extract_podcast_metadata_from_fixture(sample_podcast: Dict[str, Any]):
    """Test that podcast fixtures have all required metadata fields."""
    metadata = sample_podcast["content_metadata"]

    # Verify podcast-specific fields
    required_fields = [
        "transcript",
        "audio_url",
        "duration_seconds",
        "feed_name",
        "summary",
    ]

    for field in required_fields:
        assert field in metadata, f"Missing required field: {field}"

    # Verify transcript is a string
    assert isinstance(metadata["transcript"], str)
    assert len(metadata["transcript"]) > 0


@pytest.mark.parametrize(
    "fixture_name,expected_type,expected_status",
    [
        ("sample_article_long", "article", "completed"),
        ("sample_article_short", "article", "completed"),
        ("sample_podcast", "podcast", "completed"),
        ("sample_unprocessed_article", "article", "new"),
        ("sample_unprocessed_podcast", "podcast", "transcribed"),
    ],
)
def test_fixture_content_types_and_statuses(
    fixture_name: str,
    expected_type: str,
    expected_status: str,
    request,
):
    """Verify all fixtures have correct content_type and status."""
    fixture_data = request.getfixturevalue(fixture_name)

    assert fixture_data["content_type"] == expected_type
    assert fixture_data["status"] == expected_status


def test_worker_processing_with_article_fixture(sample_unprocessed_article: Dict[str, Any]):
    """Test that unprocessed article fixture has expected structure for processing."""
    # Verify fixture has the content needed for processing
    assert "content" in sample_unprocessed_article["content_metadata"]
    assert sample_unprocessed_article["status"] == "new"
    assert sample_unprocessed_article["content_type"] == "article"

    # Verify content is meaningful text for LLM processing
    content_text = sample_unprocessed_article["content_metadata"]["content"]
    assert len(content_text) > 100  # Has substantial content
    assert "# Sample Article" in content_text  # Has structure

    # This fixture can be used with ContentWorker by:
    # 1. Creating content in DB from fixture
    # 2. Mocking strategy.extract_data to return the fixture's content
    # 3. Processing with worker.process_content(content_id)


def test_worker_processing_with_podcast_fixture(sample_unprocessed_podcast: Dict[str, Any]):
    """Test that unprocessed podcast fixture has expected structure for processing."""
    # Verify fixture has transcript for processing
    assert "transcript" in sample_unprocessed_podcast["content_metadata"]
    assert sample_unprocessed_podcast["status"] == "transcribed"
    assert sample_unprocessed_podcast["content_type"] == "podcast"

    # Verify transcript is meaningful text for LLM processing
    transcript = sample_unprocessed_podcast["content_metadata"]["transcript"]
    assert len(transcript) > 100  # Has substantial content
    assert "test" in transcript.lower()  # Has actual content

    # Verify podcast-specific metadata is present
    metadata = sample_unprocessed_podcast["content_metadata"]
    assert "audio_url" in metadata
    assert "duration_seconds" in metadata
    assert isinstance(metadata["duration_seconds"], int)

    # This fixture can be used with ContentWorker by:
    # 1. Creating content in DB from fixture (status='transcribed')
    # 2. Worker will detect transcript and proceed to summarization
    # 3. Processing with worker.process_content(content_id)


def test_completed_fixture_has_valid_summary_structure(sample_article_long: Dict[str, Any]):
    """Validate that completed fixture summaries match expected StructuredSummary format."""
    summary = sample_article_long["content_metadata"]["summary"]

    # Verify all required StructuredSummary fields are present
    required_fields = ["title", "overview", "bullet_points", "topics", "classification"]
    for field in required_fields:
        assert field in summary, f"Missing required summary field: {field}"

    # Verify bullet points structure
    assert len(summary["bullet_points"]) > 0
    for bp in summary["bullet_points"]:
        assert "text" in bp
        assert "category" in bp
        # Verify category is valid
        valid_categories = [
            "key_finding", "methodology", "context", "implication",
            "insight", "review", "related_work", "availability"
        ]
        assert bp["category"] in valid_categories, f"Invalid category: {bp['category']}"

    # Verify quotes structure (if present)
    if "quotes" in summary and summary["quotes"]:
        for quote in summary["quotes"]:
            assert "text" in quote
            assert "context" in quote

    # Verify topics are strings
    assert all(isinstance(topic, str) for topic in summary["topics"])

    # Verify classification is valid
    valid_classifications = ["to_read", "read", "archive", "skip"]
    assert summary["classification"] in valid_classifications
