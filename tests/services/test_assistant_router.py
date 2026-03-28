"""Tests for Quick Assistant routing heuristics."""

from pydantic_ai.models.test import TestModel

from app.services import assistant_router


def test_build_turn_instructions_prefers_knowledge_for_favorites() -> None:
    """Favorite/saved prompts should route to SearchKnowledge."""

    instructions = assistant_router._build_turn_instructions("What is my favorite article?")

    assert instructions is not None
    assert "SearchKnowledge" in instructions


def test_build_turn_instructions_prefers_web_for_recent_questions() -> None:
    """Recent factual prompts should route to web search."""

    instructions = assistant_router._build_turn_instructions("What is the latest Rust release?")

    assert instructions is not None
    assert "search_web" in instructions


def test_build_turn_instructions_prefers_feed_finder_for_blog_subscription() -> None:
    """Feed/blog discovery prompts should route to the feed finder tool."""

    instructions = assistant_router._build_turn_instructions(
        "please find a blog by Armin Ronacher and subscribe to it"
    )

    assert instructions is not None
    assert "find_feed_options" in instructions
    assert "subscribe_to_feed" in instructions
    assert "recommendation mode" in instructions


def test_build_turn_instructions_keeps_feed_recommendations_non_mutating() -> None:
    """Feed recommendation prompts should stay in recommendation mode."""

    instructions = assistant_router._build_turn_instructions(
        "Recommend a few feeds, newsletters, or podcasts I should add "
        "based on what I've been reading."
    )

    assert instructions is not None
    assert "find_feed_options" in instructions
    assert "recommendation mode" in instructions
    assert "attached below for review" in instructions


def test_build_screen_aware_turn_instructions_prefers_content_search_for_digests() -> None:
    """Digest prompts should route to SearchContent before web search."""

    instructions = assistant_router._build_screen_aware_turn_instructions(
        "Can you summarize my recent daily news digests?",
        assistant_router.AssistantScreenContext(
            screen_type="daily_digest_list",
            screen_title="Daily News Digests",
        ),
    )

    assert instructions is not None
    assert "SearchContent" in instructions


def test_build_turn_instructions_skips_small_talk() -> None:
    """Small talk should not force a tool route."""

    assert assistant_router._build_turn_instructions("hello") is None


def test_get_or_create_agent_uses_shared_model_builder(monkeypatch) -> None:
    """Assistant agent construction should use the shared model factory."""

    assistant_router._agents.clear()
    calls: list[tuple[str, str | None]] = []
    sentinel_model = TestModel(custom_output_text="ok")

    def _fake_build(model_spec: str, *, api_key_override: str | None = None):
        calls.append((model_spec, api_key_override))
        return sentinel_model, {"timeout": 5}

    monkeypatch.setattr(assistant_router, "build_pydantic_model", _fake_build)

    agent = assistant_router._get_or_create_agent(
        "openai:gpt-5.4",
        api_key_override="user-key",
    )

    assert calls == [("openai:gpt-5.4", "user-key")]
    assert agent.model is sentinel_model

    assistant_router._agents.clear()
