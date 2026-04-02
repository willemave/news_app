"""Shared per-user prompt helpers for news list curation."""

from __future__ import annotations

from app.models.user import User

DEFAULT_NEWS_LIST_PREFERENCE_PROMPT = (
    "Curate a high-signal technology and business news list across all sources. "
    "Prefer original reporting, firsthand product or company updates, technical insight, "
    "important market structure changes, meaningful data points, strong analysis, and clear "
    "synthesis. Exclude memes, vague reactions, engagement bait, low-context social chatter, "
    "blocked galleries, spammy vendor copy, repetitive hype, and thin anecdotal posts unless "
    "they add concrete new information."
)


def normalize_news_list_preference_prompt(prompt: str | None) -> str | None:
    """Normalize a stored user news-list preference prompt."""
    if prompt is None:
        return None
    cleaned = prompt.strip()
    return cleaned or None


def resolve_user_news_list_preference_prompt(user: User) -> str:
    """Resolve the active shared news-list preference prompt for a user."""
    stored_prompt = normalize_news_list_preference_prompt(
        getattr(user, "news_digest_preference_prompt", None)
        or user.news_list_preference_prompt
    )
    if stored_prompt:
        return stored_prompt
    return DEFAULT_NEWS_LIST_PREFERENCE_PROMPT
