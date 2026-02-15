"""Tests for voice turn routing in the streaming agent."""

from __future__ import annotations

from app.services.voice import agent_streaming


def test_build_turn_instructions_prefers_knowledge_for_personal_saved_queries() -> None:
    """Personal saved/favorite prompts should route to SearchKnowledge."""

    prompt = "What is my favorite Anthropic article?"
    instructions = agent_streaming._build_turn_instructions(prompt)

    assert instructions is not None
    assert "SearchKnowledge" in instructions


def test_build_turn_instructions_prefers_web_for_recent_general_queries() -> None:
    """Recent/factual prompts should route to SearchWeb."""

    prompt = "What is one recent Rust project?"
    instructions = agent_streaming._build_turn_instructions(prompt)

    assert instructions is not None
    assert "SearchWeb" in instructions


def test_build_turn_instructions_skips_small_talk() -> None:
    """Small talk should not force tools."""

    assert agent_streaming._build_turn_instructions("hello") is None


def test_knowledge_route_wins_over_web_route_when_both_present() -> None:
    """Knowledge-first rule should win for user-specific saved context."""

    prompt = "Find my favorite recent Anthropic article."
    instructions = agent_streaming._build_turn_instructions(prompt)

    assert instructions is not None
    assert "SearchKnowledge" in instructions
