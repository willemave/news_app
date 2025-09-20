"""Tests for prompt tuning services."""

from datetime import datetime, timedelta

import pytest

from app.models.schema import Content, ContentUnlikes
from app.schemas.prompt_updates import PromptUpdateRequest
from app.services.prompt_tuning import (
    PromptTuningError,
    build_prompt_update,
    collect_unliked_examples,
    generate_prompt_update_result,
)


def _build_summary_payload() -> dict:
    """Create a structured summary payload suitable for tests."""

    return {
        "title": "AI Funding Slowdown Signals Reset",
        "overview": "A brief summary of why AI funding cooled and what matters now.",
        "bullet_points": [
            {"text": "Funding volumes declined 30% quarter over quarter."},
            {"text": "Investors shifting focus to efficiency and defensibility."},
            {"text": "Founders exploring alternative financing structures."},
        ],
        "quotes": [],
        "topics": ["AI", "Funding"],
        "classification": "skip",
        "full_markdown": "",
    }


def test_collect_unliked_examples(db_session):
    """Ensure unliked examples are collected and normalized."""

    content = Content(
        content_type="article",
        url="https://example.com/ai-funding",
        title="AI funding slows",
        source="TechCrunch",
        status="completed",
        content_metadata={"summary": _build_summary_payload()},
    )
    db_session.add(content)
    db_session.flush()

    unlike = ContentUnlikes(
        session_id="default",
        content_id=content.id,
        unliked_at=datetime.utcnow(),
    )
    db_session.add(unlike)
    db_session.commit()

    request = PromptUpdateRequest(lookback_days=7, max_examples=10)
    examples = collect_unliked_examples(db_session, request)

    assert len(examples) == 1
    example = examples[0]
    assert example.content_id == content.id
    assert example.source == "TechCrunch"
    assert example.bullet_points
    assert "Funding" in example.topics


def test_build_prompt_update_requires_examples(db_session):
    """Ensure the builder raises when no examples are provided."""

    request = PromptUpdateRequest(lookback_days=3, max_examples=5)
    with pytest.raises(PromptTuningError):
        build_prompt_update(request, [])


def test_generate_prompt_update_result_handles_error(monkeypatch, db_session):
    """The result object should surface PromptTuningError as a message."""

    content = Content(
        content_type="article",
        url="https://example.com/llm",
        title="LLM critique",
        source="AI Weekly",
        status="completed",
        content_metadata={"summary": _build_summary_payload()},
    )
    db_session.add(content)
    db_session.flush()

    unlike = ContentUnlikes(
        session_id="default",
        content_id=content.id,
        unliked_at=datetime.utcnow() - timedelta(hours=2),
    )
    db_session.add(unlike)
    db_session.commit()

    def _fake_build_prompt_update(*args, **kwargs):  # noqa: D401 - helper stub
        raise PromptTuningError("Model response could not be parsed as JSON.")

    monkeypatch.setattr(
        "app.services.prompt_tuning.build_prompt_update",
        _fake_build_prompt_update,
    )

    request = PromptUpdateRequest(lookback_days=7, max_examples=5)
    result = generate_prompt_update_result(db_session, request, should_generate=True)

    assert result.error == "Model response could not be parsed as JSON."
    assert result.suggestion is None
