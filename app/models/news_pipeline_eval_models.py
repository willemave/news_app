"""Structured models for end-to-end news pipeline eval cases and results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NewsPipelineEvalUserContext(BaseModel):
    """Target user context for one eval case."""

    model_config = ConfigDict(extra="forbid")

    user_id: int | None = None
    create_if_missing: bool = True
    apple_id: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    news_digest_timezone: str = "UTC"
    news_digest_preference_prompt: str | None = Field(default=None, max_length=4000)


class NewsPipelineEvalExpectations(BaseModel):
    """Optional case-specific assertions for deterministic synthetic evals."""

    model_config = ConfigDict(extra="forbid")

    expected_digest_count: int | None = Field(default=None, ge=0)
    minimum_processed_count: int | None = Field(default=None, ge=0)
    minimum_generated_summary_count: int | None = Field(default=None, ge=0)
    minimum_reused_summary_count: int | None = Field(default=None, ge=0)
    minimum_bullet_count: int | None = Field(default=None, ge=0)
    required_citation_validity: float | None = Field(default=None, ge=0.0, le=1.0)


class NewsPipelineEvalCase(BaseModel):
    """One portable end-to-end pipeline eval case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    mode: Literal["synthetic", "snapshot"]
    user: NewsPipelineEvalUserContext
    input_mode: Literal["scraped_items", "news_item_records"]
    scraped_items: list[dict[str, Any]] = Field(default_factory=list)
    news_item_records: list[dict[str, Any]] = Field(default_factory=list)
    expectations: NewsPipelineEvalExpectations | None = None

    @model_validator(mode="after")
    def validate_payload_shape(self) -> NewsPipelineEvalCase:
        """Ensure the selected input mode has the required payload."""
        if self.input_mode == "scraped_items" and not self.scraped_items:
            raise ValueError("scraped_items input_mode requires non-empty scraped_items")
        if self.input_mode == "news_item_records" and not self.news_item_records:
            raise ValueError("news_item_records input_mode requires non-empty news_item_records")
        return self


class NewsPipelineEvalItemResult(BaseModel):
    """Per-item processing outcome for one eval run."""

    news_item_id: int
    platform: str | None = None
    source_label: str | None = None
    visibility_scope: str
    final_status: str
    used_existing_summary: bool = False
    generated_summary: bool = False
    skipped: bool = False
    skipped_reason: str | None = None
    error_message: str | None = None


class NewsPipelineEvalBulletResult(BaseModel):
    """Persisted bullet output for one eval run."""

    position: int
    topic: str
    details: str
    news_item_ids: list[int] = Field(default_factory=list)


class NewsPipelineEvalRunConfig(BaseModel):
    """Execution configuration captured for one eval artifact."""

    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    base_case_id: str | None = None
    embedding_model: str | None = None
    primary_similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    secondary_similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    max_candidates: int | None = Field(default=None, ge=1)


class NewsPipelineEvalRunResult(BaseModel):
    """Full end-to-end result for one case."""

    case_id: str
    mode: Literal["synthetic", "snapshot"]
    run_config: NewsPipelineEvalRunConfig | None = None
    digest_id: int | None = None
    digest_title: str | None = None
    digest_summary: str | None = None
    source_count: int = 0
    curated_group_count: int = 0
    ingest_created_count: int = 0
    ingest_updated_count: int = 0
    processed_count: int = 0
    generated_summary_count: int = 0
    reused_summary_count: int = 0
    skipped_processing_count: int = 0
    failed_processing_count: int = 0
    citation_validity: float = 0.0
    bullets: list[NewsPipelineEvalBulletResult] = Field(default_factory=list)
    items: list[NewsPipelineEvalItemResult] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    passed: bool = False


class NewsPipelineEvalSuiteResult(BaseModel):
    """Aggregated result for one CLI eval run."""

    case_count: int
    passed: bool
    results: list[NewsPipelineEvalRunResult] = Field(default_factory=list)
