"""Shared per-user prompt helpers for news list curation."""

from __future__ import annotations

from app.models.user import User

DEFAULT_NEWS_LIST_PREFERENCE_PROMPT = (
    "Curate a high-signal news list across all sources using these principles: "
    "prefer original reporting over commentary; prioritize concrete developments, "
    "technical insight, firsthand company or product updates, meaningful data, and "
    "strong analysis; reward pieces that add context, synthesis, or clear implications; "
    "avoid memes, engagement bait, vague reactions, spammy vendor copy, repetitive "
    "hype, and low-context chatter unless they contain genuinely new information."
)


def normalize_news_list_preference_prompt(prompt: str | None) -> str | None:
    """Normalize a stored user news-list preference prompt."""
    if prompt is None:
        return None
    cleaned = prompt.strip()
    return cleaned or None


def resolve_user_news_list_preference_prompt(user: User) -> str:
    """Resolve the active shared news-list preference prompt for a user."""
    stored_prompt = normalize_news_list_preference_prompt(user.news_list_preference_prompt)
    if stored_prompt:
        return stored_prompt
    return DEFAULT_NEWS_LIST_PREFERENCE_PROMPT
