"""Tests for OpenAI summarization JSON repair behaviour."""

import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from tenacity import RetryError

from app.models.metadata import StructuredSummary
from app.services import openai_llm
from app.services.openai_llm import (
    OpenAISummarizationService,
    StructuredSummaryRetryableError,
)
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


class TestOpenAiSummarizationRetries:
    """Behavioural tests for the retry path on structured output failures."""

    def test_retries_and_raises_after_exhaustion(
        self,
        summarization_service: OpenAISummarizationService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Service should retry and surface RetryError after repeated JSON failures."""

        payload_dict = _build_structured_payload()
        truncated_json = json.dumps(payload_dict)[:-1]

        try:
            StructuredSummary.model_validate_json(truncated_json)
        except ValidationError as exc:  # pragma: no cover - only executed during setup
            validation_error = exc
        else:  # pragma: no cover
            pytest.fail("Expected StructuredSummary.model_validate_json to raise ValidationError")

        def raise_validation_error(*_: object, **__: object) -> None:
            raise validation_error

        summarization_service.client.responses.parse.side_effect = raise_validation_error
        monkeypatch.setattr("tenacity.nap.sleep", lambda _: None)

        with pytest.raises(RetryError) as exc_info:
            summarization_service.summarize_content("Sample article content for testing.")

        assert summarization_service.client.responses.parse.call_count == 3
        last_exception = exc_info.value.last_attempt.exception()
        assert isinstance(last_exception, StructuredSummaryRetryableError)

    def test_succeeds_after_retry(
        self,
        summarization_service: OpenAISummarizationService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Second attempt should succeed when OpenAI returns a valid payload after a retry."""

        payload_dict = _build_structured_payload()
        truncated_json = json.dumps(payload_dict)[:-1]

        try:
            StructuredSummary.model_validate_json(truncated_json)
        except ValidationError as exc:  # pragma: no cover - only executed during setup
            validation_error = exc
        else:  # pragma: no cover
            pytest.fail("Expected StructuredSummary.model_validate_json to raise ValidationError")

        structured = StructuredSummary(**payload_dict)
        mock_response = Mock()
        mock_response.output = [Mock()]
        mock_response.output_parsed = structured

        summarization_service.client.responses.parse.side_effect = [
            validation_error,
            mock_response,
        ]
        monkeypatch.setattr("tenacity.nap.sleep", lambda _: None)

        result = summarization_service.summarize_content("Sample article content for retry.")

        assert isinstance(result, StructuredSummary)
        assert summarization_service.client.responses.parse.call_count == 2

    def test_recovery_handles_short_overview_sentences(self) -> None:
        """Recovery should synthesise bullet points even when sentences are terse."""

        payload = {
            "title": "Concise update on AI progress",
            "overview": (
                "Short. Short. Short. Short. Short. Short. Short. Short. Short. Short."
            ),
        }

        repaired = OpenAISummarizationService._attempt_structured_summary_recovery(
            payload,
            StructuredSummary,
            "demo",
        )

        assert repaired is not None
        assert len(repaired.bullet_points) == 3
        assert all(len(point.text) >= 10 for point in repaired.bullet_points)
