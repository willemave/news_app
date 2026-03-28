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
