"""Tests for LLM summarization service with interleaved summary support."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.metadata import (
    BulletedSummary,
    InterleavedInsight,
    InterleavedSummary,
    InterleavedSummaryV2,
    SummaryTextBullet,
)
from app.services.llm_agents import get_summarization_agent
from app.services.llm_prompts import generate_summary_prompt
from app.services.llm_summarization import DEFAULT_SUMMARIZATION_MODELS, SummarizationRequest


class TestInterleavedInsightModel:
    """Tests for InterleavedInsight Pydantic model validation."""

    def test_valid_insight(self):
        """Valid insight with all fields passes validation."""
        insight = InterleavedInsight(
            topic="AI Performance",
            insight=(
                "The new approach demonstrates a 40% improvement in processing speed "
                "while maintaining accuracy levels. This is significant for production use."
            ),
            supporting_quote=(
                "We were genuinely surprised by these improvements, which exceeded "
                "our expectations significantly."
            ),
            quote_attribution="Lead Researcher at TechCorp",
        )
        assert insight.topic == "AI Performance"
        assert len(insight.insight) >= 50
        assert len(insight.supporting_quote) >= 20

    def test_insight_without_quote(self):
        """Insight without optional quote fields passes validation."""
        insight = InterleavedInsight(
            topic="Market Impact",
            insight=(
                "Industry analysts predict this development could reshape competitive "
                "dynamics over the next 2-3 years. Companies slow to adopt risk falling behind."
            ),
        )
        assert insight.topic == "Market Impact"
        assert insight.supporting_quote is None
        assert insight.quote_attribution is None

    def test_topic_too_short_fails(self):
        """Topic shorter than 2 characters fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            InterleavedInsight(
                topic="A",  # Too short
                insight="X" * 60,  # Long enough
            )
        assert "topic" in str(exc_info.value)

    def test_topic_too_long_fails(self):
        """Topic longer than 50 characters fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            InterleavedInsight(
                topic="X" * 51,  # Too long
                insight="X" * 60,
            )
        assert "topic" in str(exc_info.value)

    def test_insight_too_short_fails(self):
        """Insight shorter than 50 characters fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            InterleavedInsight(
                topic="Valid Topic",
                insight="Too short",  # Less than 50 chars
            )
        assert "insight" in str(exc_info.value)

    def test_quote_too_short_fails(self):
        """Quote shorter than 10 characters fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            InterleavedInsight(
                topic="Valid Topic",
                insight="X" * 60,
                supporting_quote="tiny",  # Less than 10 chars
            )
        assert "supporting_quote" in str(exc_info.value)


class TestInterleavedSummaryModel:
    """Tests for InterleavedSummary Pydantic model validation."""

    def test_valid_summary(self):
        """Valid summary with all required fields passes validation."""
        summary = InterleavedSummary(
            title="The Future of AI Development",
            hook=(
                "This article explores how large language models are transforming "
                "software development, with implications for developers worldwide."
            ),
            insights=[
                InterleavedInsight(
                    topic="Productivity Gains",
                    insight=(
                        "Developers using AI assistants report 40% faster completion times "
                        "for routine coding tasks. This is changing how teams allocate resources."
                    ),
                    supporting_quote=(
                        "We've seen our junior developers become productive much faster "
                        "when they have AI pair programming tools available."
                    ),
                    quote_attribution="Engineering Lead",
                ),
                InterleavedInsight(
                    topic="Quality Concerns",
                    insight=(
                        "While speed increases are notable, some teams report challenges "
                        "with code maintainability when AI code isn't carefully reviewed."
                    ),
                ),
                InterleavedInsight(
                    topic="Adoption Patterns",
                    insight=(
                        "Adoption is highest among startups and mid-size companies, with "
                        "enterprises moving more cautiously due to security requirements."
                    ),
                ),
            ],
            takeaway=(
                "As AI coding tools mature, organizations that thoughtfully integrate them "
                "will likely see competitive advantages in talent and productivity."
            ),
            classification="to_read",
        )
        assert summary.summary_type == "interleaved"
        assert len(summary.insights) == 3
        assert summary.classification == "to_read"
        assert isinstance(summary.summarization_date, datetime)

    def test_summary_type_default(self):
        """summary_type defaults to 'interleaved'."""
        summary = InterleavedSummary(
            title="Test Title",
            hook="X" * 80,  # Min 80 chars
            insights=[
                InterleavedInsight(topic="Topic", insight="X" * 60),
                InterleavedInsight(topic="Topic2", insight="X" * 60),
                InterleavedInsight(topic="Topic3", insight="X" * 60),
            ],
            takeaway="X" * 80,  # Min 80 chars
        )
        assert summary.summary_type == "interleaved"

    def test_many_insights_allowed(self):
        """Summaries can include more than the old 8 insight cap."""
        insights = [InterleavedInsight(topic=f"Topic {idx}", insight="X" * 60) for idx in range(12)]
        summary = InterleavedSummary(
            title="Test Title",
            hook="X" * 80,
            insights=insights,
            takeaway="X" * 80,
        )
        assert len(summary.insights) == 12

    def test_hook_too_short_fails(self):
        """Hook shorter than 80 characters fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            InterleavedSummary(
                title="Test Title",
                hook="Too short hook",  # Less than 80 chars
                insights=[
                    InterleavedInsight(topic="T1", insight="X" * 60),
                    InterleavedInsight(topic="T2", insight="X" * 60),
                    InterleavedInsight(topic="T3", insight="X" * 60),
                ],
                takeaway="X" * 80,
            )
        assert "hook" in str(exc_info.value)

    def test_takeaway_too_short_fails(self):
        """Takeaway shorter than 80 characters fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            InterleavedSummary(
                title="Test Title",
                hook="X" * 80,
                insights=[
                    InterleavedInsight(topic="T1", insight="X" * 60),
                    InterleavedInsight(topic="T2", insight="X" * 60),
                    InterleavedInsight(topic="T3", insight="X" * 60),
                ],
                takeaway="Short takeaway",  # Less than 80 chars
            )
        assert "takeaway" in str(exc_info.value)

    def test_too_few_insights_fails(self):
        """Fewer than 3 insights fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            InterleavedSummary(
                title="Test Title",
                hook="X" * 80,
                insights=[
                    InterleavedInsight(topic="T1", insight="X" * 60),
                    InterleavedInsight(topic="T2", insight="X" * 60),
                ],  # Only 2 insights
                takeaway="X" * 80,
            )
        assert "insights" in str(exc_info.value)

    def test_invalid_classification_fails(self):
        """Invalid classification value fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            InterleavedSummary(
                title="Test Title",
                hook="X" * 80,
                insights=[
                    InterleavedInsight(topic="T1", insight="X" * 60),
                    InterleavedInsight(topic="T2", insight="X" * 60),
                    InterleavedInsight(topic="T3", insight="X" * 60),
                ],
                takeaway="X" * 80,
                classification="invalid",  # Not 'to_read' or 'skip'
            )
        assert "classification" in str(exc_info.value)


class TestInterleavedSummaryV2Model:
    """Tests for InterleavedSummaryV2 Pydantic model validation."""

    def test_valid_summary(self):
        summary = InterleavedSummaryV2(
            title="The Future of AI Development",
            hook="X" * 90,
            key_points=[
                SummaryTextBullet(text="Key point 1 with enough detail."),
                SummaryTextBullet(text="Key point 2 with enough detail."),
                SummaryTextBullet(text="Key point 3 with enough detail."),
            ],
            topics=[
                {
                    "topic": "Performance Gains",
                    "bullets": [
                        {"text": "Benchmark improvements are consistent across tasks."},
                        {"text": "Compute efficiency allows broader deployment."},
                    ],
                },
                {
                    "topic": "Operational Impact",
                    "bullets": [
                        {"text": "Teams can iterate on product flows much faster."},
                        {"text": "Quality gates shift toward data pipelines."},
                    ],
                },
            ],
            quotes=[
                {
                    "text": "We were surprised by the magnitude of the improvements.",
                    "attribution": "Lead Researcher",
                }
            ],
            takeaway="X" * 90,
            classification="to_read",
        )
        assert len(summary.key_points) == 3
        assert len(summary.topics) == 2
        assert summary.classification == "to_read"

    def test_key_points_too_few_fails(self):
        with pytest.raises(ValidationError):
            InterleavedSummaryV2(
                title="Test Title",
                hook="X" * 90,
                key_points=[SummaryTextBullet(text="Only one point")],
                topics=[
                    {
                        "topic": "Topic",
                        "bullets": [
                            {"text": "Bullet one"},
                            {"text": "Bullet two"},
                        ],
                    },
                    {
                        "topic": "Topic Two",
                        "bullets": [
                            {"text": "Bullet one"},
                            {"text": "Bullet two"},
                        ],
                    },
                ],
                quotes=[],
                takeaway="X" * 90,
            )


class TestGenerateSummaryPrompt:
    """Tests for generate_summary_prompt function."""

    def test_long_bullets_prompt_contains_guidelines(self):
        """Long bullets prompt contains specific guidelines."""
        system_prompt, _ = generate_summary_prompt(
            content_type="long_bullets",
            max_bullet_points=20,
            max_quotes=3,
        )

        assert "points" in system_prompt.lower()
        assert "detail" in system_prompt.lower()
        assert "quotes" in system_prompt.lower()

    def test_interleaved_prompt_contains_guidelines(self):
        """Interleaved prompt contains specific guidelines."""
        system_prompt, user_template = generate_summary_prompt(
            content_type="interleaved",
            max_bullet_points=6,
            max_quotes=8,
        )

        # Should contain interleaved-specific instructions
        assert "hook" in system_prompt.lower()
        assert "key_points" in system_prompt.lower()
        assert "topics" in system_prompt.lower()
        assert "takeaway" in system_prompt.lower()
        assert "to_read" in system_prompt.lower() or "skip" in system_prompt.lower()

    def test_editorial_narrative_prompt_contains_guidelines(self):
        """Editorial narrative prompt includes narrative/quote/key-point guidance."""
        system_prompt, _ = generate_summary_prompt(
            content_type="editorial_narrative",
            max_bullet_points=10,
            max_quotes=4,
        )

        assert "editorial_narrative" in system_prompt
        assert "key_points" in system_prompt
        assert "quotes" in system_prompt
        assert "information-dense" in system_prompt.lower()

    def test_article_prompt_matches_editorial_narrative(self):
        """Article prompt maps to editorial narrative prompt."""
        editorial_system, _ = generate_summary_prompt(
            content_type="editorial_narrative",
            max_bullet_points=10,
            max_quotes=4,
        )
        article_system, _ = generate_summary_prompt(
            content_type="article",
            max_bullet_points=10,
            max_quotes=4,
        )

        assert editorial_system == article_system


class TestGetSummarizationAgent:
    """Tests for get_summarization_agent function."""

    def test_interleaved_creates_agent(self):
        """Interleaved content kind creates an agent without errors."""
        system_prompt, _ = generate_summary_prompt("interleaved", 6, 8)
        agent = get_summarization_agent(
            model_spec="anthropic:claude-haiku-4-5-20251001",
            content_type="interleaved",
            system_prompt=system_prompt,
        )
        # Agent should be created successfully
        assert agent is not None

    def test_article_creates_agent(self):
        """Article content kind creates an agent without errors."""
        system_prompt, _ = generate_summary_prompt("article", 6, 8)
        agent = get_summarization_agent(
            model_spec="anthropic:claude-haiku-4-5-20251001",
            content_type="article",
            system_prompt=system_prompt,
        )
        assert agent is not None

    def test_podcast_creates_agent(self):
        """Podcast content kind creates an agent without errors."""
        system_prompt, _ = generate_summary_prompt("podcast", 6, 8)
        agent = get_summarization_agent(
            model_spec="anthropic:claude-haiku-4-5-20251001",
            content_type="podcast",
            system_prompt=system_prompt,
        )
        assert agent is not None

    def test_news_creates_agent(self):
        """News content kind creates an agent without errors."""
        system_prompt, _ = generate_summary_prompt("news", 6, 8)
        agent = get_summarization_agent(
            model_spec="anthropic:claude-haiku-4-5-20251001",
            content_type="news",
            system_prompt=system_prompt,
        )
        assert agent is not None


class TestSummarizationRequest:
    """Tests for SummarizationRequest dataclass."""

    def test_request_with_all_fields(self):
        """Request with all fields is created correctly."""
        request = SummarizationRequest(
            content="Test content",
            content_type="interleaved",
            model_spec="anthropic:claude-haiku-4-5-20251001",
            title="Test Title",
            max_bullet_points=6,
            max_quotes=8,
            content_id=123,
        )
        assert request.content == "Test content"
        assert request.content_type == "interleaved"
        assert request.title == "Test Title"
        assert request.content_id == 123

    def test_request_with_minimal_fields(self):
        """Request with only required fields uses defaults."""
        request = SummarizationRequest(
            content="Test content",
            content_type="article",
            model_spec="anthropic:claude-haiku-4-5-20251001",
        )
        assert request.title is None
        assert request.max_bullet_points == 6
        assert request.max_quotes == 8
        assert request.content_id is None


class TestDefaultSummarizationModels:
    """Tests for provider defaults in summarization routing."""

    def test_article_and_podcast_default_to_gpt_5_2(self):
        assert DEFAULT_SUMMARIZATION_MODELS["article"] == "openai:gpt-5.2"
        assert DEFAULT_SUMMARIZATION_MODELS["podcast"] == "openai:gpt-5.2"
        assert DEFAULT_SUMMARIZATION_MODELS["editorial_narrative"] == "openai:gpt-5.2"
        assert DEFAULT_SUMMARIZATION_MODELS["interleaved"] == "openai:gpt-5.2"
        assert DEFAULT_SUMMARIZATION_MODELS["long_bullets"] == "openai:gpt-5.2"

    def test_news_defaults_to_haiku_4_5(self):
        assert DEFAULT_SUMMARIZATION_MODELS["news"] == "anthropic:claude-haiku-4-5-20251001"
        assert (
            DEFAULT_SUMMARIZATION_MODELS["news_digest"]
            == "anthropic:claude-haiku-4-5-20251001"
        )


class TestBulletedSummaryModel:
    """Tests for BulletedSummary Pydantic model validation."""

    def test_valid_summary(self):
        points = [
            {
                "text": f"Point {idx + 1} describes a key claim from the article.",
                "detail": (
                    f"Detail for point {idx + 1} adds concrete context and implications. "
                    "It stays focused and provides supporting evidence."
                ),
                "quotes": [
                    {
                        "text": f"Supporting quote for point {idx + 1} with enough length.",
                        "context": "Source",
                    }
                ],
            }
            for idx in range(10)
        ]

        summary = BulletedSummary(
            title="Bulleted Summary Example",
            points=points,
            classification="to_read",
        )

        assert summary.title == "Bulleted Summary Example"
        assert len(summary.points) == 10
        assert summary.points[0].text.startswith("Point 1")
