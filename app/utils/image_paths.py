"""Helpers for image storage paths."""

from pathlib import Path

from app.core.settings import get_settings


def get_images_base_dir() -> Path:
    """Return the base directory for generated images."""
    return get_settings().images_base_dir.resolve()


def get_content_images_dir() -> Path:
    """Return the directory for article/podcast infographic images."""
    return (get_images_base_dir() / "content").resolve()


def get_news_thumbnails_dir() -> Path:
    """Return the directory for news thumbnails."""
    return (get_images_base_dir() / "news_thumbnails").resolve()


def get_thumbnails_dir() -> Path:
    """Return the directory for 200px thumbnails."""
    return (get_images_base_dir() / "thumbnails").resolve()
