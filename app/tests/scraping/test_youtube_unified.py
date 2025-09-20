from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:  # Python 3.11+
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[assignment]
from pathlib import Path

import pytest

from app.scraping.youtube_unified import (
    YouTubeChannelConfig,
    YouTubeUnifiedScraper,
    load_youtube_channels,
)


def write_config(tmp_path: Path, content: str) -> Path:
    config_path = tmp_path / "youtube.yml"
    config_path.write_text(content, encoding="utf-8")
    return config_path


def test_load_youtube_channels(tmp_path: Path) -> None:
    config = """
channels:
  - name: "Example"
    channel_id: "UC123"
    limit: 5
    max_age_days: 10
    language: "en"
"""

    config_path = write_config(tmp_path, config)

    channels = load_youtube_channels(config_path)

    assert len(channels) == 1
    channel = channels[0]
    assert channel.name == "Example"
    assert channel.channel_id == "UC123"
    assert channel.limit == 5
    assert channel.max_age_days == 10
    assert channel.language == "en"
    assert channel.target_url == "https://www.youtube.com/channel/UC123"


def test_scrape_returns_items(mocker, tmp_path: Path) -> None:
    channel = YouTubeChannelConfig(
        name="Example",
        channel_id="UC123",
        limit=2,
        max_age_days=30,
        language="en",
    )

    mocker.patch.object(
        YouTubeUnifiedScraper,
        "_extract_channel_entries",
        return_value=[{"id": "abc"}],
    )

    mocker.patch.object(
        YouTubeUnifiedScraper,
        "_extract_video_info",
        return_value={
            "id": "abc",
            "title": "Video Title",
            "upload_date": datetime.now(tz=UTC).strftime("%Y%m%d"),
            "duration": 1234,
            "thumbnail": "https://example.com/thumb.jpg",
            "view_count": 100,
            "like_count": 10,
            "description": "A sample description",
            "channel_id": "UC123",
        },
    )

    scraper = YouTubeUnifiedScraper(channels=[channel])

    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    assert item["content_type"].value == "podcast"
    assert item["metadata"]["platform"] == "youtube"
    assert item["metadata"]["source"] == "youtube:Example"
    assert item["metadata"]["has_transcript"] is False
    assert item["metadata"]["video_id"] == "abc"


def test_scrape_respects_max_age(mocker) -> None:
    recent_video = {
        "id": "recent",
        "title": "Recent",
        "upload_date": datetime.now(tz=UTC).strftime("%Y%m%d"),
    }
    old_video = {
        "id": "old",
        "title": "Old",
        "upload_date": (datetime.now(tz=UTC) - timedelta(days=400)).strftime("%Y%m%d"),
    }

    mocker.patch.object(
        YouTubeUnifiedScraper,
        "_extract_channel_entries",
        return_value=[{"id": "recent"}, {"id": "old"}],
    )

    mocker.patch.object(
        YouTubeUnifiedScraper,
        "_extract_video_info",
        side_effect=[recent_video, old_video],
    )

    channel = YouTubeChannelConfig(
        name="Example",
        channel_id="UC123",
        limit=5,
        max_age_days=30,
    )

    scraper = YouTubeUnifiedScraper(channels=[channel])
    items = scraper.scrape()

    assert len(items) == 1
    assert items[0]["metadata"]["video_id"] == "recent"


def test_missing_config_returns_empty(tmp_path: Path) -> None:
    config_path = tmp_path / "does-not-exist.yml"
    channels = load_youtube_channels(config_path)
    assert channels == []
