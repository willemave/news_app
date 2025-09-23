"""Tests for OpenAI summarization JSON repair behaviour."""

import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.models.metadata import StructuredSummary
from app.services import openai_llm
from app.services.openai_llm import OpenAISummarizationService
from app.utils.json_repair import try_repair_truncated_json


def _build_structured_payload() -> dict[str, object]:
    """Return a minimal payload that satisfies StructuredSummary constraints."""

    return {
        "title": "Meta expands AI assistant for dating",
        "overview": "Meta is rolling out an AI assistant to streamline Facebook Dating and reduce swipe fatigue.",
        "bullet_points": [
            {"text": "Users can describe ideal matches in natural language", "category": "feature"},
            {"text": "Assistant suggests candidates aligned with preferences", "category": "impact"},
            {"text": "Rollout begins in US and Canada this month", "category": "timeline"},
        ],
        "quotes": [],
        "topics": ["Meta", "AI", "Dating"],
        "classification": "to_read",
        "full_markdown": "# Meta expands AI assistant for dating",
    }


@pytest.fixture(autouse=True)
def configure_settings() -> None:
    """Ensure the OpenAI API key is populated for service initialisation."""

    openai_llm.settings.openai_api_key = "test-key"


@pytest.fixture
def summarization_service(monkeypatch: pytest.MonkeyPatch) -> OpenAISummarizationService:
    """Provide an OpenAI summarization service with a mocked client."""

    mock_client = Mock()
    mock_client.responses = Mock()
    monkeypatch.setattr(openai_llm, "OpenAI", Mock(return_value=mock_client))
    service = OpenAISummarizationService()
    return service


class TestJsonRepair:
    """Unit tests for the shared JSON repair helper."""

    def test_balances_truncated_object(self) -> None:
        """Ensure truncated JSON objects are closed correctly."""

        payload = json.dumps(_build_structured_payload())[:-1]
        repaired = try_repair_truncated_json(payload)
        assert repaired is not None
        assert json.loads(repaired)["title"] == "Meta expands AI assistant for dating"


class TestOpenAiSummarizationFallback:
    """Behavioural tests for OpenAI fallback parsing."""

    def test_recovers_from_truncated_json(self, summarization_service: OpenAISummarizationService) -> None:
        """Summarization should succeed when OpenAI returns truncated structured output."""

        payload_dict = _build_structured_payload()
        truncated_json = json.dumps(payload_dict)[:-1]

        try:
            StructuredSummary.model_validate_json(truncated_json)
        except ValidationError as exc:  # pragma: no cover - only executed during test setup
            validation_error = exc
        else:  # pragma: no cover
            pytest.fail("Expected StructuredSummary.model_validate_json to raise ValidationError")

        def raise_validation_error(*_: object, **__: object) -> None:
            raise validation_error

        summarization_service.client.responses.parse.side_effect = raise_validation_error

        result = summarization_service.summarize_content("Sample article content for testing.")

        assert isinstance(result, StructuredSummary)
        assert result.title == payload_dict["title"]
        assert len(result.bullet_points) == len(payload_dict["bullet_points"])

    def test_returns_none_when_payload_irreparable(
        self, summarization_service: OpenAISummarizationService
    ) -> None:
        """Summarization should fail gracefully when payload cannot be repaired."""

        try:
            StructuredSummary.model_validate_json("this is not json")
        except ValidationError as exc:  # pragma: no cover - test setup path
            validation_error = exc
        else:  # pragma: no cover
            pytest.fail("Expected StructuredSummary.model_validate_json to raise ValidationError")

        def raise_validation_error(*_: object, **__: object) -> None:
            raise validation_error

        summarization_service.client.responses.parse.side_effect = raise_validation_error

        result = summarization_service.summarize_content("Another sample article")

        assert result is None
