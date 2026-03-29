"""Tests for LLM usage persistence helpers."""

from app.models.schema import LlmUsageRecord
from app.services import llm_costs


def test_record_llm_usage_persists_row_and_cost(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        llm_costs,
        "MODEL_PRICING",
        {
            "openai:gpt-5.4": llm_costs.ModelPricing(
                input_per_million_usd=2.0,
                output_per_million_usd=8.0,
            )
        },
    )

    record = llm_costs.record_llm_usage(
        db_session,
        provider="openai",
        model="gpt-5.4",
        feature="chat",
        operation="chat.async",
        source="realtime",
        usage={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
        content_id=42,
        session_id=7,
        message_id=9,
        user_id=3,
    )
    db_session.commit()

    persisted = db_session.query(LlmUsageRecord).filter(LlmUsageRecord.id == record.id).one()
    assert persisted.total_tokens == 1500
    assert persisted.cost_usd == 0.006


def test_record_llm_usage_allows_unknown_pricing(db_session, monkeypatch) -> None:
    monkeypatch.setattr(llm_costs, "MODEL_PRICING", {})

    record = llm_costs.record_llm_usage(
        db_session,
        provider="openai",
        model="unknown-model",
        feature="chat",
        operation="chat.async",
        usage={"input": 12, "output": 8, "total": 20},
    )
    db_session.commit()

    persisted = db_session.query(LlmUsageRecord).filter(LlmUsageRecord.id == record.id).one()
    assert persisted.input_tokens == 12
    assert persisted.output_tokens == 8
    assert persisted.total_tokens == 20
    assert persisted.cost_usd is None


def test_estimate_cost_uses_google_alias_pricing(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_costs,
        "MODEL_PRICING",
        {
            "gemini-3.1-pro-preview": llm_costs.ModelPricing(
                input_per_million_usd=2.0,
                output_per_million_usd=12.0,
            )
        },
    )
    monkeypatch.setattr(
        llm_costs,
        "MODEL_ALIASES",
        {"gemini-3-pro-preview": "gemini-3.1-pro-preview"},
    )

    cost = llm_costs.estimate_cost_usd(
        provider="google",
        model="google-gla:gemini-3-pro-preview",
        input_tokens=1_000,
        output_tokens=500,
    )

    assert cost == 0.008


def test_estimate_cost_uses_long_context_rates(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_costs,
        "MODEL_PRICING",
        {
            "gpt-5.4": llm_costs.ModelPricing(
                input_per_million_usd=2.5,
                output_per_million_usd=15.0,
                long_context_threshold_tokens=272_000,
                long_context_input_per_million_usd=5.0,
                long_context_output_per_million_usd=22.5,
            )
        },
    )

    cost = llm_costs.estimate_cost_usd(
        provider="openai",
        model="gpt-5.4",
        input_tokens=300_000,
        output_tokens=10_000,
    )

    assert cost == 1.725


def test_estimate_cost_uses_snapshot_aliases(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_costs,
        "MODEL_PRICING",
        {
            "o4-mini-deep-research": llm_costs.ModelPricing(
                input_per_million_usd=2.0,
                output_per_million_usd=8.0,
            )
        },
    )
    monkeypatch.setattr(
        llm_costs,
        "MODEL_ALIASES",
        {"o4-mini-deep-research-2025-06-26": "o4-mini-deep-research"},
    )

    cost = llm_costs.estimate_cost_usd(
        provider="deep_research",
        model="o4-mini-deep-research-2025-06-26",
        input_tokens=1_000,
        output_tokens=500,
    )

    assert cost == 0.006
