"""Shared per-user prompt helpers for news digest curation."""

from __future__ import annotations

from app.models.user import User

DEFAULT_NEWS_DIGEST_PREFERENCE_PROMPT = (
    "Curate a high-signal technology and business news digest across all sources. "
    "Prefer original reporting, firsthand product or company updates, technical insight, "
    "important market structure changes, meaningful data points, strong analysis, and clear "
    "synthesis. Exclude memes, vague reactions, engagement bait, low-context social chatter, "
    "blocked galleries, spammy vendor copy, repetitive hype, and thin anecdotal posts unless "
    "they add concrete new information."
)


def normalize_news_digest_preference_prompt(prompt: str | None) -> str | None:
    """Normalize a stored user digest preference prompt."""
    if prompt is None:
        return None
    cleaned = prompt.strip()
    return cleaned or None


def resolve_user_news_digest_preference_prompt(user: User) -> str:
    """Resolve the active shared digest preference prompt for a user."""
    stored_prompt = normalize_news_digest_preference_prompt(user.news_digest_preference_prompt)
    if stored_prompt:
        return stored_prompt
    return DEFAULT_NEWS_DIGEST_PREFERENCE_PROMPT
