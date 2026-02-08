from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.onboarding import (
    AUDIO_PLAN_FALLBACK_MODELS,
    AUDIO_PLAN_MODEL,
    DISCOVERY_FALLBACK_MODELS,
    FAST_DISCOVER_MODEL,
    _AudioLane,
    _AudioPlanOutput,
    _DiscoverOutput,
    _DiscoverSuggestion,
    _run_audio_plan_with_fallback,
    _run_discover_output_with_fallback,
)


def test_default_onboarding_fallback_order() -> None:
    assert DISCOVERY_FALLBACK_MODELS == (
        "google-gla:gemini-2.5-flash",
        "openai:gpt-5-mini",
    )
    assert AUDIO_PLAN_FALLBACK_MODELS == (
        "google-gla:gemini-2.5-flash",
        "openai:gpt-5-mini",
    )


def test_discover_fallback_uses_secondary_model(monkeypatch):
    attempts: list[str] = []

    class FailingAgent:
        def run_sync(self, _prompt, model_settings=None):  # noqa: ANN001
            raise TimeoutError("primary timeout")

    class SuccessAgent:
        def run_sync(self, _prompt, model_settings=None):  # noqa: ANN001
            return SimpleNamespace(
                data=_DiscoverOutput(
                    substacks=[
                        _DiscoverSuggestion(
                            title="Example",
                            feed_url="https://example.com/feed",
                        )
                    ]
                )
            )

    def fake_get_basic_agent(model_spec, _output_cls, _system_prompt):
        attempts.append(model_spec)
        if model_spec == FAST_DISCOVER_MODEL:
            return FailingAgent()
        return SuccessAgent()

    monkeypatch.setattr("app.services.onboarding.DISCOVERY_FALLBACK_MODELS", ("openai:gpt-5-mini",))
    monkeypatch.setattr("app.services.onboarding.get_basic_agent", fake_get_basic_agent)

    output = _run_discover_output_with_fallback(
        prompt="test prompt",
        timeout_seconds=12,
        operation="test_discover_fallback",
    )

    assert attempts == [FAST_DISCOVER_MODEL, "openai:gpt-5-mini"]
    assert output.substacks
    assert output.substacks[0].feed_url == "https://example.com/feed"


@pytest.mark.asyncio
async def test_audio_plan_fallback_uses_secondary_model(monkeypatch):
    attempts: list[str] = []

    class FailingAgent:
        async def run(self, _prompt, model_settings=None):  # noqa: ANN001
            raise TimeoutError("primary timeout")

    class SuccessAgent:
        async def run(self, _prompt, model_settings=None):  # noqa: ANN001
            return SimpleNamespace(
                data=_AudioPlanOutput(
                    topic_summary="AI topics",
                    inferred_topics=["AI"],
                    lanes=[
                        _AudioLane(
                            name="Lane",
                            goal="Goal",
                            target="feeds",
                            queries=["ai newsletter updates", "ai rss feeds"],
                        )
                    ],
                )
            )

    def fake_get_basic_agent(model_spec, _output_cls, _system_prompt):
        attempts.append(model_spec)
        if model_spec == AUDIO_PLAN_MODEL:
            return FailingAgent()
        return SuccessAgent()

    monkeypatch.setattr(
        "app.services.onboarding.AUDIO_PLAN_FALLBACK_MODELS", ("openai:gpt-5-mini",)
    )
    monkeypatch.setattr("app.services.onboarding.get_basic_agent", fake_get_basic_agent)

    output = await _run_audio_plan_with_fallback(
        prompt="test prompt",
        timeout_seconds=8,
    )

    assert attempts == [AUDIO_PLAN_MODEL, "openai:gpt-5-mini"]
    assert output.topic_summary == "AI topics"
    assert output.lanes[0].name == "Lane"
