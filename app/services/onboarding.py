"""Service helpers for agentic onboarding."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants import DEFAULT_NEW_FEED_LIMIT
from app.core.logging import get_logger
from app.models.schema import (
    Content,
    FeedDiscoveryRun,
    FeedDiscoverySuggestion,
    OnboardingDiscoveryLane,
    OnboardingDiscoveryRun,
    OnboardingDiscoverySuggestion,
)
from app.repositories.content_repository import apply_visibility_filters, build_visibility_context
from app.routers.api.models import (
    OnboardingAudioDiscoverRequest,
    OnboardingAudioDiscoverResponse,
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
    OnboardingDiscoveryLaneStatus,
    OnboardingDiscoveryStatusResponse,
    OnboardingFastDiscoverRequest,
    OnboardingFastDiscoverResponse,
    OnboardingProfileRequest,
    OnboardingProfileResponse,
    OnboardingSelectedSource,
    OnboardingSuggestion,
    OnboardingVoiceParseRequest,
    OnboardingVoiceParseResponse,
)
from app.scraping.atom_unified import load_atom_feeds
from app.scraping.substack_unified import load_substack_feeds
from app.services.exa_client import ExaSearchResult, exa_search
from app.services.llm_agents import get_basic_agent
from app.services.queue import QueueService, TaskType
from app.services.scraper_configs import CreateUserScraperConfig, create_user_scraper_config
from app.utils.paths import resolve_config_path

logger = get_logger(__name__)

PROFILE_MODEL = "anthropic:claude-haiku-4-5-20251001"
FAST_DISCOVER_MODEL = "anthropic:claude-haiku-4-5-20251001"
VOICE_PARSE_MODEL = "anthropic:claude-haiku-4-5-20251001"
AUDIO_PLAN_MODEL = "anthropic:claude-haiku-4-5-20251001"

PROFILE_TIMEOUT_SECONDS = 8
FAST_DISCOVER_TIMEOUT_SECONDS = 12
VOICE_PARSE_TIMEOUT_SECONDS = 6
AUDIO_PLAN_TIMEOUT_SECONDS = 8
ENRICH_TIMEOUT_SECONDS = 25

FAST_DISCOVER_MAX_QUERIES = 6
FAST_DISCOVER_EXA_RESULTS = 3
ENRICH_MAX_QUERIES = 10
ENRICH_EXA_RESULTS = 6

DEFAULT_SOURCE_LIMITS = {
    "substack": 8,
    "podcast_rss": 6,
    "atom": 6,
    "reddit": 8,
}

SCRAPER_SOURCE_BY_TYPE = {
    "substack": "Substack",
    "podcast_rss": "Podcast",
    "atom": "Atom",
    "reddit": "Reddit",
}

PROFILE_SYSTEM_PROMPT = (
    "You are building a short onboarding profile for a user. "
    "Use the provided interests and web snippets to infer a concise profile summary "
    "and 3-6 topical interests. "
    "Do not invent interests that contradict the user-provided topics. "
    "Return structured output only."
)

FAST_DISCOVER_SYSTEM_PROMPT = (
    "You are selecting high-quality sources for a new user. "
    "Use the profile summary, topics, and search snippets to suggest Substack feeds, "
    "podcast RSS feeds, and relevant subreddits. Prefer sources with clear RSS URLs when possible. "
    "Return structured output only."
)

VOICE_PARSE_SYSTEM_PROMPT = (
    "You extract onboarding fields from a transcript. "
    "Return a first name if explicitly stated and a concise list of interest topics. "
    "Do not guess missing information. "
    "Return structured output only."
)

AUDIO_PLAN_SYSTEM_PROMPT = (
    "You design onboarding discovery lanes based on a user's spoken interests. "
    "Return a concise topic_summary, 3-6 inferred_topics, and 3-5 lanes. "
    "Each lane must include name, goal, target (feeds, podcasts, reddit), "
    "and 2-4 web search queries. Include at least one reddit lane. "
    "Return structured output only."
)


class _ProfileOutput(BaseModel):
    """LLM output for onboarding profile creation."""

    profile_summary: str
    inferred_topics: list[str] = Field(default_factory=list)
    candidate_sources: list[str] = Field(default_factory=list)


class _DiscoverSuggestion(BaseModel):
    """LLM output suggestion seed."""

    title: str | None = None
    site_url: str | None = None
    feed_url: str | None = None
    subreddit: str | None = None
    rationale: str | None = None
    score: float | None = None


class _DiscoverOutput(BaseModel):
    """LLM output for onboarding discovery."""

    substacks: list[_DiscoverSuggestion] = Field(default_factory=list)
    podcasts: list[_DiscoverSuggestion] = Field(default_factory=list)
    subreddits: list[_DiscoverSuggestion] = Field(default_factory=list)


class _VoiceParseOutput(BaseModel):
    """LLM output for onboarding voice parsing."""

    first_name: str | None = None
    interest_topics: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class _AudioLane(BaseModel):
    """LLM output for a single onboarding discovery lane."""

    name: str
    goal: str
    target: Literal["feeds", "podcasts", "reddit"]
    queries: list[str] = Field(default_factory=list)


class _AudioPlanOutput(BaseModel):
    """LLM output for onboarding audio discovery planning."""

    topic_summary: str
    inferred_topics: list[str] = Field(default_factory=list)
    lanes: list[_AudioLane] = Field(default_factory=list)


def build_onboarding_profile(request: OnboardingProfileRequest) -> OnboardingProfileResponse:
    """Build a quick profile from name + interest topics using Exa + LLM.

    Args:
        request: OnboardingProfileRequest payload.

    Returns:
        OnboardingProfileResponse with summary and inferred topics.
    """
    queries = _build_profile_queries(request)
    results = _run_exa_queries(queries, num_results=FAST_DISCOVER_EXA_RESULTS, include_social=False)

    if not results:
        fallback_summary = _build_profile_fallback_summary(
            request.first_name, request.interest_topics
        )
        return OnboardingProfileResponse(
            profile_summary=fallback_summary,
            inferred_topics=_merge_topics(request.interest_topics),
            candidate_sources=[],
        )

    try:
        prompt = _format_profile_prompt(request, results)
        agent = get_basic_agent(PROFILE_MODEL, _ProfileOutput, PROFILE_SYSTEM_PROMPT)
        result = agent.run_sync(prompt, model_settings={"timeout": PROFILE_TIMEOUT_SECONDS})
        output = _get_agent_output(result)
        merged_topics = _merge_topics(output.inferred_topics, request.interest_topics)
        return OnboardingProfileResponse(
            profile_summary=output.profile_summary,
            inferred_topics=merged_topics,
            candidate_sources=output.candidate_sources,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Onboarding profile build failed",
            extra={
                "component": "onboarding",
                "operation": "profile_build",
                "context_data": {"error": str(exc)},
            },
        )
        fallback_summary = _build_profile_fallback_summary(
            request.first_name, request.interest_topics
        )
        return OnboardingProfileResponse(
            profile_summary=fallback_summary,
            inferred_topics=_merge_topics(request.interest_topics),
            candidate_sources=[],
        )


def parse_onboarding_voice(request: OnboardingVoiceParseRequest) -> OnboardingVoiceParseResponse:
    """Parse a voice transcript into onboarding fields.

    Args:
        request: OnboardingVoiceParseRequest payload.

    Returns:
        OnboardingVoiceParseResponse with extracted fields.
    """
    transcript = request.transcript.strip()
    if not transcript:
        return OnboardingVoiceParseResponse(
            first_name=None,
            interest_topics=[],
            confidence=0,
            missing_fields=["first_name", "interest_topics"],
        )

    try:
        prompt = _format_voice_parse_prompt(transcript, request.locale)
        agent = get_basic_agent(VOICE_PARSE_MODEL, _VoiceParseOutput, VOICE_PARSE_SYSTEM_PROMPT)
        result = agent.run_sync(prompt, model_settings={"timeout": VOICE_PARSE_TIMEOUT_SECONDS})
        output = _get_agent_output(result)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Onboarding voice parse failed",
            extra={
                "component": "onboarding",
                "operation": "voice_parse",
                "context_data": {"error": str(exc)},
            },
        )
        return OnboardingVoiceParseResponse(
            first_name=None,
            interest_topics=[],
            confidence=0,
            missing_fields=["first_name", "interest_topics"],
        )

    first_name = (output.first_name or "").strip() or None
    topics = _merge_topics(output.interest_topics)
    missing_fields: list[str] = []
    if not first_name:
        missing_fields.append("first_name")
    if not topics:
        missing_fields.append("interest_topics")

    return OnboardingVoiceParseResponse(
        first_name=first_name,
        interest_topics=topics,
        confidence=output.confidence,
        missing_fields=missing_fields,
    )


async def start_audio_discovery(
    db: Session, user_id: int, request: OnboardingAudioDiscoverRequest
) -> OnboardingAudioDiscoverResponse:
    """Start onboarding discovery from an audio transcript.

    Args:
        db: Database session.
        user_id: Current user id.
        request: OnboardingAudioDiscoverRequest payload.

    Returns:
        OnboardingAudioDiscoverResponse with run and lane status.
    """
    transcript = request.transcript.strip()
    if not transcript:
        raise ValueError("Transcript is required")

    plan = await _build_audio_lane_plan(transcript, request.locale)

    run = OnboardingDiscoveryRun(
        user_id=user_id,
        status="pending",
        topic_summary=plan.topic_summary,
        inferred_topics=plan.inferred_topics,
    )
    db.add(run)
    db.flush()

    lanes: list[OnboardingDiscoveryLane] = []
    for lane in plan.lanes:
        lane_row = OnboardingDiscoveryLane(
            run_id=run.id,
            lane_name=lane.name,
            goal=lane.goal,
            target=lane.target,
            status="queued",
            query_count=len(lane.queries),
            completed_queries=0,
            queries=lane.queries,
        )
        db.add(lane_row)
        lanes.append(lane_row)

    db.commit()

    QueueService().enqueue(
        TaskType.ONBOARDING_DISCOVER,
        payload={"user_id": user_id, "run_id": run.id},
    )

    return OnboardingAudioDiscoverResponse(
        run_id=run.id,
        run_status=run.status,
        topic_summary=run.topic_summary,
        inferred_topics=list(run.inferred_topics or []),
        lanes=[_serialize_lane_status(lane) for lane in lanes],
    )


def get_onboarding_discovery_status(
    db: Session, user_id: int, run_id: int
) -> OnboardingDiscoveryStatusResponse:
    """Return the latest onboarding discovery status for a run.

    Args:
        db: Database session.
        user_id: Current user id.
        run_id: Discovery run id.

    Returns:
        OnboardingDiscoveryStatusResponse with lane status and suggestions when ready.
    """
    run = (
        db.query(OnboardingDiscoveryRun)
        .filter(OnboardingDiscoveryRun.id == run_id, OnboardingDiscoveryRun.user_id == user_id)
        .first()
    )
    if not run:
        raise ValueError("Discovery run not found")

    lanes = (
        db.query(OnboardingDiscoveryLane)
        .filter(OnboardingDiscoveryLane.run_id == run.id)
        .order_by(OnboardingDiscoveryLane.id.asc())
        .all()
    )

    suggestions: OnboardingFastDiscoverResponse | None = None
    if run.status == "completed":
        suggestions = _load_onboarding_suggestions(db, run.id)

    return OnboardingDiscoveryStatusResponse(
        run_id=run.id,
        run_status=run.status,
        topic_summary=run.topic_summary,
        inferred_topics=list(run.inferred_topics or []),
        lanes=[_serialize_lane_status(lane) for lane in lanes],
        suggestions=suggestions,
        error_message=run.error_message,
    )


def fast_discover(request: OnboardingFastDiscoverRequest) -> OnboardingFastDiscoverResponse:
    """Run fast discovery to return onboarding suggestions.

    Args:
        request: OnboardingFastDiscoverRequest payload.

    Returns:
        OnboardingFastDiscoverResponse with grouped recommendations.
    """
    curated = _load_curated_defaults()
    queries = _build_discovery_queries(request)
    results = _run_exa_queries(queries, num_results=FAST_DISCOVER_EXA_RESULTS)

    if not results:
        return _fast_discover_from_defaults(curated)

    try:
        prompt = _format_discovery_prompt(request, results)
        agent = get_basic_agent(FAST_DISCOVER_MODEL, _DiscoverOutput, FAST_DISCOVER_SYSTEM_PROMPT)
        result = agent.run_sync(prompt, model_settings={"timeout": FAST_DISCOVER_TIMEOUT_SECONDS})
        output = _get_agent_output(result)
        return _build_discovery_response(output, curated)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Fast onboarding discovery failed",
            extra={
                "component": "onboarding",
                "operation": "fast_discover",
                "context_data": {"error": str(exc)},
            },
        )
        return _fast_discover_from_defaults(curated)


def complete_onboarding(
    db: Session, user_id: int, request: OnboardingCompleteRequest
) -> OnboardingCompleteResponse:
    """Finalize onboarding selections, create scraper configs, and queue crawlers.

    Args:
        db: Database session.
        user_id: Current user id.
        request: OnboardingCompleteRequest payload.

    Returns:
        OnboardingCompleteResponse with status and inbox count.
    """
    created_types: set[str] = set()
    selections = request.selected_sources

    if not selections:
        curated = _load_curated_defaults()
        selections = _defaults_to_selected_sources(curated)

    for selection in selections:
        config_payload = {**(selection.config or {})}
        if not config_payload.get("feed_url"):
            config_payload["feed_url"] = selection.feed_url
        if "limit" not in config_payload:
            config_payload["limit"] = DEFAULT_NEW_FEED_LIMIT

        try:
            create_user_scraper_config(
                db,
                user_id=user_id,
                data=CreateUserScraperConfig(
                    scraper_type=selection.suggestion_type,
                    display_name=selection.title,
                    config=config_payload,
                ),
            )
            created_types.add(selection.suggestion_type)
        except ValueError as exc:
            if "already exists" in str(exc):
                created_types.add(selection.suggestion_type)
                continue
            logger.error(
                "Failed to create onboarding scraper config",
                extra={
                    "component": "onboarding",
                    "operation": "create_scraper_config",
                    "item_id": str(user_id),
                    "context_data": {"error": str(exc)},
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Unexpected error creating scraper config",
                extra={
                    "component": "onboarding",
                    "operation": "create_scraper_config",
                    "item_id": str(user_id),
                    "context_data": {"error": str(exc)},
                },
            )

    if request.selected_subreddits:
        created_types.add("reddit")
        _create_reddit_configs(db, user_id, request.selected_subreddits)

    sources_to_scrape = _resolve_scraper_sources(created_types)
    task_id = None
    if sources_to_scrape:
        task_id = QueueService().enqueue(
            TaskType.SCRAPE,
            payload={"sources": sources_to_scrape},
        )

    if request.profile_summary:
        QueueService().enqueue(
            TaskType.ONBOARDING_DISCOVER,
            payload={
                "user_id": user_id,
                "profile_summary": request.profile_summary,
                "inferred_topics": request.inferred_topics or [],
            },
        )

    inbox_count = _estimate_inbox_count(db, user_id)
    inbox_count_estimate = max(inbox_count, 100)

    return OnboardingCompleteResponse(
        status="queued",
        task_id=task_id,
        inbox_count_estimate=inbox_count_estimate,
        longform_status="loading",
        has_completed_new_user_tutorial=_get_tutorial_flag(db, user_id),
    )


def run_discover_enrich(
    db: Session,
    user_id: int,
    profile_summary: str,
    inferred_topics: list[str] | None,
) -> int | None:
    """Run async enrich discovery and persist suggestions.

    Args:
        db: Database session.
        user_id: Current user id.
        profile_summary: Profile summary for queries.
        inferred_topics: Optional topic list.

    Returns:
        Discovery run id if created, otherwise None.
    """
    if not profile_summary:
        return None

    try:
        topics = list(inferred_topics or [])[:12]
        request = OnboardingFastDiscoverRequest(
            profile_summary=profile_summary,
            inferred_topics=topics,
        )
    except Exception:  # noqa: BLE001
        return None
    curated = _load_curated_defaults()
    queries = _build_discovery_queries(request, max_queries=ENRICH_MAX_QUERIES)
    results = _run_exa_queries(queries, num_results=ENRICH_EXA_RESULTS)
    if not results:
        return None

    try:
        prompt = _format_discovery_prompt(request, results)
        agent = get_basic_agent(FAST_DISCOVER_MODEL, _DiscoverOutput, FAST_DISCOVER_SYSTEM_PROMPT)
        result = agent.run_sync(prompt, model_settings={"timeout": ENRICH_TIMEOUT_SECONDS})
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Onboarding discover enrich failed",
            extra={
                "component": "onboarding",
                "operation": "discover_enrich",
                "item_id": str(user_id),
                "context_data": {"error": str(exc)},
            },
        )
        return None

    output = _get_agent_output(result)
    suggestions = _build_discovery_response(output, curated)
    return _persist_discovery_run(db, user_id, suggestions)


def run_audio_discovery(db: Session, run_id: int) -> None:
    """Run onboarding audio discovery lanes and persist suggestions.

    Args:
        db: Database session.
        run_id: Onboarding discovery run id.
    """
    run = db.query(OnboardingDiscoveryRun).filter(OnboardingDiscoveryRun.id == run_id).first()
    if not run:
        raise ValueError("Discovery run not found")
    if run.status == "completed":
        return

    try:
        run.status = "processing"
        db.commit()

        lanes = (
            db.query(OnboardingDiscoveryLane)
            .filter(OnboardingDiscoveryLane.run_id == run.id)
            .order_by(OnboardingDiscoveryLane.id.asc())
            .all()
        )

        results: list[ExaSearchResult] = []
        for lane in lanes:
            lane.status = "processing"
            lane.completed_queries = 0
            lane.query_count = len(lane.queries or [])
            db.commit()

            for idx, query in enumerate(lane.queries or []):
                results.extend(
                    _run_exa_queries(
                        [query],
                        num_results=FAST_DISCOVER_EXA_RESULTS,
                        include_social=(lane.target == "reddit"),
                    )
                )
                lane.completed_queries = idx + 1
                db.commit()

            lane.status = "completed"
            db.commit()

        curated = _load_curated_defaults()
        if not results:
            suggestions = _fast_discover_from_defaults(curated)
            _persist_onboarding_suggestions(db, run, suggestions)
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        request = OnboardingFastDiscoverRequest(
            profile_summary=run.topic_summary or "News interests",
            inferred_topics=list(run.inferred_topics or []),
        )
        prompt = _format_discovery_prompt(request, results)
        agent = get_basic_agent(FAST_DISCOVER_MODEL, _DiscoverOutput, FAST_DISCOVER_SYSTEM_PROMPT)
        result = agent.run_sync(prompt, model_settings={"timeout": FAST_DISCOVER_TIMEOUT_SECONDS})
        suggestions = _build_discovery_response(_get_agent_output(result), curated)
        _persist_onboarding_suggestions(db, run, suggestions)
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Onboarding audio discovery failed",
            extra={
                "component": "onboarding",
                "operation": "audio_discover",
                "item_id": str(run_id),
                "context_data": {"error": str(exc)},
            },
        )
        run.status = "failed"
        run.error_message = str(exc)
        db.query(OnboardingDiscoveryLane).filter(OnboardingDiscoveryLane.run_id == run.id).update(
            {"status": "failed"}, synchronize_session=False
        )
        db.commit()


def mark_tutorial_complete(db: Session, user_id: int) -> bool:
    """Mark the onboarding tutorial as completed for a user.

    Args:
        db: Database session.
        user_id: Current user id.

    Returns:
        Updated completion flag.
    """
    from app.models.user import User

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    user.has_completed_new_user_tutorial = True
    db.commit()
    return True


def _build_profile_queries(request: OnboardingProfileRequest) -> list[str]:
    topics = _merge_topics(request.interest_topics)
    queries: list[str] = []
    for topic in topics:
        queries.append(f"{topic} newsletter")
        queries.append(f"{topic} podcast")
        queries.append(f"{topic} substack")
        if len(queries) >= 4:
            break
    if not queries:
        queries.append(f"{request.first_name} newsletter")
    return queries[:4]


def _build_discovery_queries(
    request: OnboardingFastDiscoverRequest, max_queries: int = FAST_DISCOVER_MAX_QUERIES
) -> list[str]:
    topics = [topic.strip() for topic in request.inferred_topics if topic.strip()]
    topics = topics[:4] if topics else []

    queries: list[str] = []
    if request.profile_summary:
        queries.append(f"{request.profile_summary} newsletter")

    for topic in topics:
        queries.append(f"{topic} substack")
        queries.append(f"{topic} podcast rss")
        queries.append(f"{topic} best newsletters")
        if len(queries) >= max_queries:
            break

    return queries[:max_queries]


def _run_exa_queries(
    queries: Iterable[str],
    *,
    num_results: int,
    include_social: bool = False,
) -> list[ExaSearchResult]:
    results: list[ExaSearchResult] = []
    exclude_domains = [] if include_social else None
    for query in queries:
        results.extend(
            exa_search(
                query,
                num_results=num_results,
                max_characters=1200,
                exclude_domains=exclude_domains,
            )
        )
    return results


def _format_profile_prompt(
    request: OnboardingProfileRequest, results: list[ExaSearchResult]
) -> str:
    lines = [
        f"first_name: {request.first_name}",
        f"interest_topics: {', '.join(request.interest_topics)}",
        "",
        "web_results:",
    ]
    for idx, item in enumerate(results[:10], start=1):
        lines.append(f"{idx}. {item.title}\nurl: {item.url}\nsummary: {item.snippet or ''}")
    return "\n".join(lines)


def _format_voice_parse_prompt(transcript: str, locale: str | None) -> str:
    locale_value = locale or "unknown"
    return (
        "Extract the user's first name (if stated) and the topics of news they want to read. "
        "Return concise topic phrases (2-5 words) and avoid guessing. "
        f"locale: {locale_value}\n"
        f"transcript: {transcript}"
    )


async def _build_audio_lane_plan(transcript: str, locale: str | None) -> _AudioPlanOutput:
    try:
        prompt = _format_audio_plan_prompt(transcript, locale)
        agent = get_basic_agent(AUDIO_PLAN_MODEL, _AudioPlanOutput, AUDIO_PLAN_SYSTEM_PROMPT)
        if hasattr(agent, "run"):
            result = await agent.run(prompt, model_settings={"timeout": AUDIO_PLAN_TIMEOUT_SECONDS})
        else:
            result = agent.run_sync(prompt, model_settings={"timeout": AUDIO_PLAN_TIMEOUT_SECONDS})
        output = _get_agent_output(result)
        return _normalize_audio_lane_plan(output, transcript)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Onboarding audio lane plan failed",
            extra={
                "component": "onboarding",
                "operation": "audio_plan",
                "context_data": {"error": str(exc)},
            },
        )
        return _fallback_audio_lane_plan(transcript)


def _format_audio_plan_prompt(transcript: str, locale: str | None) -> str:
    locale_value = locale or "unknown"
    return f"locale: {locale_value}\ntranscript: {transcript}"


def _get_agent_output(result: Any) -> Any:
    if hasattr(result, "output"):
        return result.output
    if hasattr(result, "data"):
        return result.data
    raise AttributeError("Agent result missing output")


def _normalize_audio_lane_plan(plan: _AudioPlanOutput, transcript: str) -> _AudioPlanOutput:
    topic_summary = (plan.topic_summary or "").strip()
    if not topic_summary:
        topic_summary = _fallback_topic_summary(transcript)

    inferred_topics = _merge_topics(plan.inferred_topics, max_topics=6)
    lanes: list[_AudioLane] = []
    seen_names: set[str] = set()
    has_reddit = False

    for lane in plan.lanes:
        name = (lane.name or "").strip()
        if not name:
            continue
        normalized_name = name.lower()
        if normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)

        queries = _clean_queries(lane.queries)
        if len(queries) < 2:
            continue

        target = lane.target
        if target == "reddit":
            has_reddit = True

        lanes.append(
            _AudioLane(
                name=name,
                goal=(lane.goal or "").strip(),
                target=target,
                queries=queries[:4],
            )
        )
        if len(lanes) >= 5:
            break

    if not lanes:
        return _fallback_audio_lane_plan(transcript)

    if not has_reddit:
        reddit_lane = _fallback_reddit_lane(transcript, inferred_topics)
        if lanes:
            existing_names = {lane.name.lower() for lane in lanes if lane.name}
            if reddit_lane.name.lower() in existing_names:
                reddit_lane = _AudioLane(
                    name=f"{reddit_lane.name} Suggestions",
                    goal=reddit_lane.goal,
                    target=reddit_lane.target,
                    queries=reddit_lane.queries,
                )
        if len(lanes) >= 5:
            lanes[-1] = reddit_lane
        else:
            lanes.append(reddit_lane)

    if len(lanes) < 3:
        lanes.extend(_fallback_core_lanes(transcript, inferred_topics, existing=lanes))

    return _AudioPlanOutput(
        topic_summary=topic_summary,
        inferred_topics=inferred_topics,
        lanes=lanes[:5],
    )


def _fallback_audio_lane_plan(transcript: str) -> _AudioPlanOutput:
    inferred_topics = _merge_topics([_fallback_topic_summary(transcript)], max_topics=3)
    lanes = _fallback_core_lanes(transcript, inferred_topics, existing=[])
    return _AudioPlanOutput(
        topic_summary=_fallback_topic_summary(transcript),
        inferred_topics=inferred_topics,
        lanes=lanes,
    )


def _fallback_core_lanes(
    transcript: str,
    inferred_topics: list[str],
    *,
    existing: list[_AudioLane],
) -> list[_AudioLane]:
    seed = _seed_phrase(transcript, inferred_topics)
    lanes = list(existing)
    if len(lanes) < 3:
        lanes.append(
            _AudioLane(
                name="Newsletters & Feeds",
                goal="Find newsletters and RSS feeds aligned with the user's interests.",
                target="feeds",
                queries=[
                    f"{seed} newsletter",
                    f"{seed} RSS feed",
                    f"best {seed} Substack",
                ],
            )
        )
    if len(lanes) < 3:
        lanes.append(
            _AudioLane(
                name="Podcasts",
                goal="Find podcast feeds covering the user's interests.",
                target="podcasts",
                queries=[
                    f"{seed} podcast",
                    f"{seed} podcast RSS",
                    f"best {seed} podcasts",
                ],
            )
        )
    if not any(lane.target == "reddit" for lane in lanes):
        lanes.append(_fallback_reddit_lane(transcript, inferred_topics))
    return lanes


def _fallback_reddit_lane(transcript: str, inferred_topics: list[str]) -> _AudioLane:
    seed = _seed_phrase(transcript, inferred_topics)
    return _AudioLane(
        name="Reddit",
        goal="Find active subreddits for the user's interests.",
        target="reddit",
        queries=[
            f"{seed} subreddit",
            f"best subreddits for {seed}",
            f"{seed} reddit community",
        ],
    )


def _fallback_topic_summary(transcript: str) -> str:
    cleaned = transcript.strip().strip(".")
    if not cleaned:
        return "general news interests"
    words = cleaned.split()
    return " ".join(words[:10])


def _seed_phrase(transcript: str, inferred_topics: list[str]) -> str:
    if inferred_topics:
        return inferred_topics[0]
    summary = _fallback_topic_summary(transcript)
    return summary or "technology news"


def _clean_queries(queries: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for query in queries:
        if not isinstance(query, str):
            continue
        normalized = query.strip().strip(".")
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized)
        if len(cleaned) >= 4:
            break
    return cleaned


def _merge_topics(*topic_lists: Iterable[str], max_topics: int = 8) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for topics in topic_lists:
        for topic in topics:
            if not isinstance(topic, str):
                continue
            normalized = topic.strip().strip(".,;:")
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)
            if len(merged) >= max_topics:
                return merged
    return merged


def _build_profile_fallback_summary(first_name: str, topics: list[str]) -> str:
    cleaned_topics = _merge_topics(topics, max_topics=3)
    if cleaned_topics:
        return f"{first_name} interested in {', '.join(cleaned_topics)}"
    return first_name


def _format_discovery_prompt(
    request: OnboardingFastDiscoverRequest, results: list[ExaSearchResult]
) -> str:
    lines = [
        f"profile_summary: {request.profile_summary}",
        f"topics: {', '.join(request.inferred_topics)}",
        "",
        "web_results:",
    ]
    for idx, item in enumerate(results[:12], start=1):
        lines.append(f"{idx}. {item.title}\nurl: {item.url}\nsummary: {item.snippet or ''}")
    return "\n".join(lines)


def _fast_discover_from_defaults(
    curated: dict[str, list[OnboardingSuggestion]],
) -> OnboardingFastDiscoverResponse:
    feed_defaults = curated.get("substack", []) + curated.get("atom", [])
    return OnboardingFastDiscoverResponse(
        recommended_pods=curated.get("podcast_rss", []),
        recommended_substacks=feed_defaults,
        recommended_subreddits=curated.get("reddit", []),
    )


def _build_discovery_response(
    output: _DiscoverOutput,
    curated: dict[str, list[OnboardingSuggestion]],
) -> OnboardingFastDiscoverResponse:
    feed_defaults = curated.get("substack", []) + curated.get("atom", [])
    feed_limit = DEFAULT_SOURCE_LIMITS["substack"] + DEFAULT_SOURCE_LIMITS["atom"]
    substacks = _merge_suggestions(
        _normalize_suggestions(output.substacks, "substack"),
        feed_defaults,
        feed_limit,
    )
    podcasts = _merge_suggestions(
        _normalize_suggestions(output.podcasts, "podcast_rss"),
        curated.get("podcast_rss", []),
        DEFAULT_SOURCE_LIMITS["podcast_rss"],
    )
    subreddits = _merge_suggestions(
        _normalize_suggestions(output.subreddits, "reddit"),
        curated.get("reddit", []),
        DEFAULT_SOURCE_LIMITS["reddit"],
    )

    return OnboardingFastDiscoverResponse(
        recommended_pods=podcasts,
        recommended_substacks=substacks,
        recommended_subreddits=subreddits,
    )


def _normalize_suggestions(
    items: list[_DiscoverSuggestion], suggestion_type: str
) -> list[OnboardingSuggestion]:
    normalized: list[OnboardingSuggestion] = []
    for item in items:
        feed_url = (item.feed_url or "").strip()
        site_url = (item.site_url or "").strip() or None
        subreddit = (item.subreddit or "").strip() or None

        if suggestion_type == "substack" and not feed_url and site_url:
            feed_url = site_url.rstrip("/") + "/feed"
        if suggestion_type == "reddit" and not subreddit:
            subreddit = _extract_subreddit(site_url)

        if suggestion_type == "reddit":
            if not subreddit:
                continue
            normalized.append(
                OnboardingSuggestion(
                    suggestion_type="reddit",
                    title=item.title or subreddit,
                    site_url=site_url,
                    subreddit=subreddit,
                    rationale=item.rationale,
                    score=item.score,
                    is_default=False,
                )
            )
            continue

        if not feed_url:
            continue

        normalized.append(
            OnboardingSuggestion(
                suggestion_type=suggestion_type,
                title=item.title,
                site_url=site_url,
                feed_url=feed_url,
                rationale=item.rationale,
                score=item.score,
                is_default=False,
            )
        )
    return normalized


def _merge_suggestions(
    primary: list[OnboardingSuggestion],
    defaults: list[OnboardingSuggestion],
    limit: int,
) -> list[OnboardingSuggestion]:
    merged: list[OnboardingSuggestion] = []
    seen: set[str] = set()

    for item in list(primary) + list(defaults):
        key = _suggestion_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged


def _suggestion_key(item: OnboardingSuggestion) -> str | None:
    if item.suggestion_type == "reddit":
        return item.subreddit
    return item.feed_url


def _extract_subreddit(site_url: str | None) -> str | None:
    if not site_url:
        return None
    lowered = site_url.lower()
    if "reddit.com/r/" not in lowered:
        return None
    try:
        parts = lowered.split("reddit.com/r/")
        if len(parts) < 2:
            return None
        name = parts[1].split("/")[0]
        return name.strip()
    except Exception:
        return None


def _load_curated_defaults() -> dict[str, list[OnboardingSuggestion]]:
    defaults: dict[str, list[OnboardingSuggestion]] = {
        "substack": _load_substack_defaults(),
        "podcast_rss": _load_podcast_defaults(),
        "atom": _load_atom_defaults(),
        "reddit": _load_reddit_defaults(),
    }
    return defaults


def _load_substack_defaults() -> list[OnboardingSuggestion]:
    feeds = load_substack_feeds()
    suggestions = []
    for feed in feeds:
        feed_url = (feed.get("url") or "").strip()
        if not feed_url:
            continue
        suggestions.append(
            OnboardingSuggestion(
                suggestion_type="substack",
                title=feed.get("name"),
                feed_url=feed_url,
                site_url=feed_url,
                is_default=True,
            )
        )
    return suggestions


def _load_atom_defaults() -> list[OnboardingSuggestion]:
    feeds = load_atom_feeds()
    suggestions = []
    for feed in feeds:
        feed_url = (feed.get("url") or "").strip()
        if not feed_url:
            continue
        suggestions.append(
            OnboardingSuggestion(
                suggestion_type="atom",
                title=feed.get("name"),
                feed_url=feed_url,
                site_url=feed_url,
                is_default=True,
            )
        )
    return suggestions


def _load_podcast_defaults() -> list[OnboardingSuggestion]:
    path = resolve_config_path("PODCAST_CONFIG_PATH", "podcasts.yml")
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
    except Exception:
        logger.warning("Failed to load podcast defaults", exc_info=True)
        return []

    feeds = payload.get("feeds") or []
    suggestions: list[OnboardingSuggestion] = []
    for feed in feeds:
        if not isinstance(feed, dict):
            continue
        feed_url = (feed.get("url") or "").strip()
        if not feed_url:
            continue
        suggestions.append(
            OnboardingSuggestion(
                suggestion_type="podcast_rss",
                title=feed.get("name"),
                feed_url=feed_url,
                site_url=feed_url,
                is_default=True,
            )
        )
    return suggestions


def _load_reddit_defaults() -> list[OnboardingSuggestion]:
    path = resolve_config_path("REDDIT_CONFIG_PATH", "reddit.yml")
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
    except Exception:
        logger.warning("Failed to load reddit defaults", exc_info=True)
        return []

    subreddits = payload.get("subreddits") or []
    suggestions: list[OnboardingSuggestion] = []
    for sub in subreddits:
        if not isinstance(sub, dict):
            continue
        name = (sub.get("name") or "").strip()
        if not name:
            continue
        suggestions.append(
            OnboardingSuggestion(
                suggestion_type="reddit",
                title=name,
                site_url=f"https://www.reddit.com/r/{name}/",
                subreddit=name,
                is_default=True,
            )
        )
    return suggestions


def _defaults_to_selected_sources(
    curated: dict[str, list[OnboardingSuggestion]],
) -> list[OnboardingSelectedSource]:
    selections: list[OnboardingSelectedSource] = []
    for suggestion_type in ("substack", "podcast_rss", "atom"):
        defaults = curated.get(suggestion_type, [])
        limit = DEFAULT_SOURCE_LIMITS[suggestion_type]
        for suggestion in defaults[:limit]:
            selections.append(
                OnboardingSelectedSource(
                    suggestion_type=suggestion.suggestion_type,
                    title=suggestion.title,
                    feed_url=suggestion.feed_url or "",
                    config={"feed_url": suggestion.feed_url or ""},
                )
            )
    return selections


def _create_reddit_configs(db: Session, user_id: int, subreddits: list[str]) -> None:
    for subreddit in subreddits:
        cleaned = subreddit.strip().lstrip("r/").strip("/")
        if not cleaned:
            continue
        try:
            create_user_scraper_config(
                db,
                user_id=user_id,
                data=CreateUserScraperConfig(
                    scraper_type="reddit",
                    display_name=cleaned,
                    config={"subreddit": cleaned, "limit": DEFAULT_NEW_FEED_LIMIT},
                ),
            )
        except ValueError as exc:
            if "already exists" not in str(exc):
                logger.error(
                    "Failed to create subreddit config",
                    extra={
                        "component": "onboarding",
                        "operation": "create_subreddit",
                        "item_id": str(user_id),
                        "context_data": {"error": str(exc), "subreddit": cleaned},
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Unexpected error creating subreddit config",
                extra={
                    "component": "onboarding",
                    "operation": "create_subreddit",
                    "item_id": str(user_id),
                    "context_data": {"error": str(exc), "subreddit": cleaned},
                },
            )
    return None


def _resolve_scraper_sources(types: set[str]) -> list[str]:
    sources = [
        SCRAPER_SOURCE_BY_TYPE[type_name]
        for type_name in types
        if type_name in SCRAPER_SOURCE_BY_TYPE
    ]
    return sorted(set(sources))


def _estimate_inbox_count(db: Session, user_id: int) -> int:
    context = build_visibility_context(user_id)
    count_query = db.query(func.count(Content.id))
    count_query = apply_visibility_filters(count_query, context)
    count_query = count_query.filter(~context.is_read)
    return count_query.scalar() or 0


def _get_tutorial_flag(db: Session, user_id: int) -> bool:
    from app.models.user import User

    user = db.query(User).filter(User.id == user_id).first()
    return bool(user and user.has_completed_new_user_tutorial)


def _serialize_lane_status(lane: OnboardingDiscoveryLane) -> OnboardingDiscoveryLaneStatus:
    return OnboardingDiscoveryLaneStatus(
        name=lane.lane_name,
        status=lane.status,
        completed_queries=lane.completed_queries or 0,
        query_count=lane.query_count or 0,
    )


def _persist_onboarding_suggestions(
    db: Session,
    run: OnboardingDiscoveryRun,
    suggestions: OnboardingFastDiscoverResponse,
) -> None:
    db.query(OnboardingDiscoverySuggestion).filter(
        OnboardingDiscoverySuggestion.run_id == run.id
    ).delete(synchronize_session=False)

    seen: set[str] = set()
    candidates = (
        suggestions.recommended_substacks
        + suggestions.recommended_pods
        + suggestions.recommended_subreddits
    )
    for item in candidates:
        key = _suggestion_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        if item.suggestion_type == "reddit" and not item.subreddit:
            continue
        if item.suggestion_type != "reddit" and not item.feed_url:
            continue
        if not item.rationale or not item.rationale.strip():
            item.rationale = _default_rationale(item)
        db.add(
            OnboardingDiscoverySuggestion(
                run_id=run.id,
                user_id=run.user_id,
                suggestion_type=item.suggestion_type,
                site_url=item.site_url,
                feed_url=item.feed_url,
                subreddit=item.subreddit,
                title=item.title,
                rationale=item.rationale,
                score=item.score,
                status="new",
            )
        )
    db.commit()


def _default_rationale(item: OnboardingSuggestion) -> str:
    if item.suggestion_type == "podcast_rss":
        label = item.title or "podcast"
        return f"Podcast recommendation aligned with your interests ({label})."
    if item.suggestion_type == "reddit":
        label = item.subreddit or item.title or "subreddit"
        return f"Active community discussing {label}."
    label = item.title or "newsletter"
    return f"Suggested source aligned with your interests ({label})."


def _load_onboarding_suggestions(db: Session, run_id: int) -> OnboardingFastDiscoverResponse:
    suggestions = (
        db.query(OnboardingDiscoverySuggestion)
        .filter(
            OnboardingDiscoverySuggestion.run_id == run_id,
            OnboardingDiscoverySuggestion.status == "new",
        )
        .order_by(func.coalesce(OnboardingDiscoverySuggestion.score, 0).desc())
        .all()
    )

    feeds: list[OnboardingSuggestion] = []
    podcasts: list[OnboardingSuggestion] = []
    subreddits: list[OnboardingSuggestion] = []

    for suggestion in suggestions:
        item = OnboardingSuggestion(
            suggestion_type=suggestion.suggestion_type,
            title=suggestion.title,
            site_url=suggestion.site_url,
            feed_url=suggestion.feed_url,
            subreddit=suggestion.subreddit,
            rationale=suggestion.rationale,
            score=suggestion.score,
            is_default=False,
        )
        if suggestion.suggestion_type == "podcast_rss":
            podcasts.append(item)
        elif suggestion.suggestion_type == "reddit":
            subreddits.append(item)
        else:
            feeds.append(item)

    return OnboardingFastDiscoverResponse(
        recommended_pods=podcasts,
        recommended_substacks=feeds,
        recommended_subreddits=subreddits,
    )


def _persist_discovery_run(
    db: Session, user_id: int, suggestions: OnboardingFastDiscoverResponse
) -> int | None:
    run = FeedDiscoveryRun(
        user_id=user_id,
        status="completed",
        direction_summary="onboarding_enrich",
        seed_content_ids=[],
    )
    db.add(run)
    db.flush()

    persisted = 0
    candidate_feed_urls = [
        suggestion.feed_url
        for suggestion in suggestions.recommended_substacks + suggestions.recommended_pods
        if suggestion.feed_url
    ]
    existing_feed_urls: set[str] = set()
    if candidate_feed_urls:
        existing_feed_urls = {
            row[0]
            for row in db.query(FeedDiscoverySuggestion.feed_url)
            .filter(
                FeedDiscoverySuggestion.user_id == user_id,
                FeedDiscoverySuggestion.feed_url.in_(candidate_feed_urls),
            )
            .all()
        }
    for suggestion in suggestions.recommended_substacks + suggestions.recommended_pods:
        if not suggestion.feed_url:
            continue
        if suggestion.feed_url in existing_feed_urls:
            continue
        db.add(
            FeedDiscoverySuggestion(
                run_id=run.id,
                user_id=user_id,
                suggestion_type=suggestion.suggestion_type,
                site_url=suggestion.site_url,
                feed_url=suggestion.feed_url,
                title=suggestion.title,
                rationale=suggestion.rationale,
                score=suggestion.score,
                status="new",
                config={"feed_url": suggestion.feed_url},
            )
        )
        persisted += 1

    if not persisted:
        db.rollback()
        return None

    db.commit()
    return run.id
