"""Router tests for prompt tuning views."""

from datetime import datetime

from app.schemas.prompt_updates import (
    PromptExample,
    PromptUpdateRequest,
    PromptUpdateResult,
    PromptUpdateSuggestion,
)


def test_prompt_tuning_page_loads(client, monkeypatch):
    """Ensure the prompt tuning page renders without data."""

    empty_result = PromptUpdateResult(
        request=PromptUpdateRequest(lookback_days=7, max_examples=25),
        examples=[],
        suggestion=None,
        error=None,
    )

    monkeypatch.setattr(
        "app.routers.admin.generate_prompt_update_result",
        lambda db, request, should_generate: empty_result,
    )

    response = client.get("/admin/prompt-tuning")
    assert response.status_code == 200
    assert "Summarization Prompt Tuning" in response.text


def test_prompt_tuning_generate_suggestion(client, monkeypatch):
    """Verify that the view displays suggestion data from the service layer."""

    example = PromptExample(
        content_id=42,
        unliked_at=datetime.utcnow(),
        content_type="article",
        title="Synthetic data backlash grows",
        source="AI Pulse",
        short_summary="Synthetic data quality concerns drive negative feedback.",
        summary="Longer summary text.",
        topics=["AI", "Synthetic Data"],
        bullet_points=["Synthetic datasets introduced subtle hallucinations."],
        classification="skip",
    )

    suggestion = PromptUpdateSuggestion(
        analysis="Users dislike repetitive synthetic data coverage.",
        change_recommendations=["Weight novelty higher in summarization logic."],
        revised_prompt="New prompt text",
        evaluation_plan=["Run A/B test on 50 articles."],
        guardrails=["Ensure technical depth remains high."],
    )

    fake_result = PromptUpdateResult(
        request=PromptUpdateRequest(lookback_days=7, max_examples=10),
        examples=[example],
        suggestion=suggestion,
        error=None,
    )

    def _fake_generate_prompt_update_result(db, request, should_generate):  # noqa: D401 - helper
        return fake_result

    monkeypatch.setattr(
        "app.routers.admin.generate_prompt_update_result",
        _fake_generate_prompt_update_result,
    )

    response = client.get("/admin/prompt-tuning?lookback_days=7&max_examples=10&generate=1")
    assert response.status_code == 200
    assert "Suggested Prompt" in response.text
    assert "Weight novelty higher" in response.text
