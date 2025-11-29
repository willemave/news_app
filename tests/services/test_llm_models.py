from types import SimpleNamespace

import pytest
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.models.openai import OpenAIModel

from app.services import llm_models


def _settings(**kwargs):
    """Helper to create a stub settings object."""
    return SimpleNamespace(
        openai_api_key=kwargs.get("openai_api_key"),
        anthropic_api_key=kwargs.get("anthropic_api_key"),
        google_api_key=kwargs.get("google_api_key"),
    )


def test_build_pydantic_model_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_models, "get_settings", lambda: _settings(openai_api_key="test-key"))

    model, model_settings = llm_models.build_pydantic_model("gpt-5-mini")

    assert isinstance(model, OpenAIModel)
    assert model_settings is None


def test_build_pydantic_model_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_models,
        "get_settings",
        lambda: _settings(anthropic_api_key="test-key"),
    )

    model, model_settings = llm_models.build_pydantic_model("claude-haiku-4-5-20251001")

    assert isinstance(model, AnthropicModel)
    assert model_settings is None


def test_build_pydantic_model_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_models, "get_settings", lambda: _settings(google_api_key="test-key"))

    model, model_settings = llm_models.build_pydantic_model("gemini-2.5-flash-lite-preview-06-17")

    assert isinstance(model, GoogleModel)
    assert model_settings is not None
    assert model_settings["google_thinking_config"] == {"include_thoughts": False}
