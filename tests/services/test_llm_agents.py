"""Tests for LLM agent factory helpers."""

from __future__ import annotations

from app.services import llm_agents


def test_get_basic_agent_returns_fresh_agent_instances(monkeypatch) -> None:
    created: list[object] = []

    class _FakeAgent:
        def __class_getitem__(cls, _item):  # noqa: ANN001
            return cls

        def __init__(self, *_args, **_kwargs):  # noqa: ANN001
            created.append(self)

    monkeypatch.setattr(llm_agents, "Agent", _FakeAgent)
    monkeypatch.setattr(llm_agents, "build_pydantic_model", lambda _spec: ("model", {}))

    first = llm_agents.get_basic_agent("openai:gpt-5.2", dict, "system prompt")
    second = llm_agents.get_basic_agent("openai:gpt-5.2", dict, "system prompt")

    assert first is not second
    assert len(created) == 2
