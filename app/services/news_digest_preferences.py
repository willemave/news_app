"""Backward-compatible wrappers for news-list preference prompts."""

from __future__ import annotations

from app.models.user import User
from app.services.news_list_preferences import (
    DEFAULT_NEWS_LIST_PREFERENCE_PROMPT,
    normalize_news_list_preference_prompt,
    resolve_user_news_list_preference_prompt,
)

DEFAULT_NEWS_DIGEST_PREFERENCE_PROMPT = DEFAULT_NEWS_LIST_PREFERENCE_PROMPT


def normalize_news_digest_preference_prompt(prompt: str | None) -> str | None:
    """Normalize a stored preference prompt via the news-list implementation."""
    return normalize_news_list_preference_prompt(prompt)


def resolve_user_news_digest_preference_prompt(user: User) -> str:
    """Resolve the active shared preference prompt for a user."""
    return resolve_user_news_list_preference_prompt(user)
