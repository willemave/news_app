"""Tests for LLM model resolution helpers."""

from app.services.llm_models import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    PROVIDER_DEFAULTS,
    resolve_model,
)


def test_resolve_model_defaults() -> None:
    """Defaults resolve to the configured provider + model."""
    provider, model_spec = resolve_model(None, None)
    assert provider == DEFAULT_PROVIDER
    assert model_spec == DEFAULT_MODEL


def test_resolve_model_prefixed_hint_overrides_provider() -> None:
    """Prefixed hints take precedence over the provider argument."""
    provider, model_spec = resolve_model("openai", "anthropic:claude-opus-4-5-20251101")
    assert provider == "anthropic"
    assert model_spec == "anthropic:claude-opus-4-5-20251101"


def test_resolve_model_provider_prefix_normalization() -> None:
    """Provider prefixes normalize to canonical provider names."""
    provider, model_spec = resolve_model("google-gla", None)
    assert provider == "google"
    assert model_spec == PROVIDER_DEFAULTS["google"]


def test_resolve_model_hint_without_prefix_uses_provider() -> None:
    """Unprefixed hints attach the provider prefix."""
    provider, model_spec = resolve_model("google", "gemini-3-pro-preview")
    assert provider == "google"
    assert model_spec == "google-gla:gemini-3-pro-preview"


def test_resolve_model_with_unprefixed_openai_hint() -> None:
    """OpenAI hints are prefixed with openai."""
    provider, model_spec = resolve_model("openai", "gpt-4o")
    assert provider == "openai"
    assert model_spec == "openai:gpt-4o"
