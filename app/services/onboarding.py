"""Service helpers for agentic onboarding."""

from __future__ import annotations

from collections.abc import Iterable

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants import DEFAULT_NEW_FEED_LIMIT
from app.core.logging import get_logger
from app.models.schema import Content, FeedDiscoveryRun, FeedDiscoverySuggestion
from app.repositories.content_repository import apply_visibility_filters, build_visibility_context
from app.routers.api.models import (
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
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

PROFILE_TIMEOUT_SECONDS = 8
FAST_DISCOVER_TIMEOUT_SECONDS = 12
VOICE_PARSE_TIMEOUT_SECONDS = 6
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
        output = result.data
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
        output = result.data
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
        output = result.data
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

    output = result.data
    suggestions = _build_discovery_response(output, curated)
    return _persist_discovery_run(db, user_id, suggestions)


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
    for suggestion in suggestions.recommended_substacks + suggestions.recommended_pods:
        if not suggestion.feed_url:
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
