"""Helpers for deterministic image URLs."""


def build_content_image_url(content_id: int) -> str:
    """Build the URL for a generated content image."""
    return f"/static/images/content/{content_id}.png"


def build_news_thumbnail_url(content_id: int) -> str:
    """Build the URL for a generated news thumbnail image."""
    return f"/static/images/news_thumbnails/{content_id}.png"


def build_thumbnail_url(content_id: int) -> str:
    """Build the URL for a 200px thumbnail image."""
    return f"/static/images/thumbnails/{content_id}.png"
