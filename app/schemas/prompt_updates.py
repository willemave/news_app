"""Schemas for summarization prompt update suggestions."""

from datetime import datetime

from pydantic import BaseModel, Field


class PromptUpdateRequest(BaseModel):
    """Request payload for generating a summarization prompt update."""

    lookback_days: int = Field(
        default=7,
        ge=1,
        le=60,
        description="Number of days to look back when gathering unliked content.",
    )
    max_examples: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum number of unliked content examples to include in the analysis.",
    )


class PromptExample(BaseModel):
    """Serialized representation of an unliked content item for prompt tuning."""

    content_id: int = Field(..., description="Unique identifier for the content item.")
    unliked_at: datetime = Field(..., description="Timestamp when the content was unliked.")
    content_type: str = Field(..., description="Type of the content (article, podcast, etc.).")
    title: str = Field(..., description="Title of the content item.")
    source: str | None = Field(
        default=None, description="Content source or publication if available."
    )
    short_summary: str | None = Field(
        default=None, description="Short summary or teaser for quick reference."
    )
    summary: str | None = Field(
        default=None, description="Full summary text if available."
    )
    topics: list[str] = Field(default_factory=list, description="Topic tags attached to the content.")
    bullet_points: list[str] = Field(
        default_factory=list,
        description="Key bullet points extracted during summarization.",
    )
    classification: str | None = Field(
        default=None,
        description="LLM-generated classification such as to_read or skip.",
    )


class PromptUpdateSuggestion(BaseModel):
    """Structured response describing proposed summarization prompt updates."""

    analysis: str = Field(
        ..., description="Narrative summary of patterns observed in unliked content."
    )
    change_recommendations: list[str] = Field(
        default_factory=list,
        description="Concrete recommendations for adjusting the summarization prompt.",
    )
    revised_prompt: str = Field(
        ..., description="Updated summarization prompt text proposed by the model."
    )
    evaluation_plan: list[str] = Field(
        default_factory=list,
        description="Suggested steps for validating the updated prompt before rollout.",
    )
    guardrails: list[str] = Field(
        default_factory=list,
        description="Risks or guardrails to monitor when adopting the update.",
    )


class PromptUpdateResult(BaseModel):
    """Composite object returned to the web layer for rendering."""

    request: PromptUpdateRequest
    examples: list[PromptExample]
    suggestion: PromptUpdateSuggestion | None = None
    error: str | None = Field(
        default=None, description="User-friendly error message if generation failed."
    )

