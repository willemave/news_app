"""Unified YouTube channel scraper aligned with podcast ingestion flow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator

from app.core.logging import get_logger
from app.models.metadata import ContentType
from app.scraping.base import BaseScraper
from app.utils.error_logger import create_error_logger

try:  # pragma: no cover - import guard for optional dependency in tests
    import yt_dlp  # type: ignore
except ImportError:  # pragma: no cover
    yt_dlp = None  # type: ignore

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

logger = get_logger(__name__)


class YouTubeChannelConfig(BaseModel):
    """Configuration for a single YouTube channel or playlist."""

    name: str = Field(..., min_length=1, max_length=200)
    url: HttpUrl | str | None = None
    channel_id: str | None = Field(None, min_length=5)
    playlist_id: str | None = Field(None, min_length=5)
    limit: int = Field(default=10, ge=1, le=50)
    max_age_days: int | None = Field(default=30, ge=0, le=365)
    language: str | None = Field(default=None, min_length=2, max_length=8)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: HttpUrl | str | None) -> str | None:
        if value is None:
            return None
        return str(value)

    @field_validator("playlist_id")
    @classmethod
    def normalize_playlist(cls, value: str | None) -> str | None:
        if value:
            return value.strip()
        return value

    @field_validator("channel_id")
    @classmethod
    def normalize_channel(cls, value: str | None) -> str | None:
        if value:
            return value.strip()
        return value

    @field_validator("url")
    @classmethod
    def ensure_path_components(cls, value: str | None, values: dict[str, Any]) -> str | None:
        if not value and not values.get("channel_id") and not values.get("playlist_id"):
            raise ValueError("Provide either url, channel_id, or playlist_id")
        return value

    @property
    def target_url(self) -> str:
        """Resolve to a concrete URL that yt-dlp understands."""

        if self.playlist_id:
            return f"https://www.youtube.com/playlist?list={self.playlist_id}"
        if self.channel_id:
            return f"https://www.youtube.com/channel/{self.channel_id}"
        return str(self.url)


class YouTubeUnifiedScraper(BaseScraper):
    """Scraper that ingests recent videos from configured YouTube channels."""

    _LISTING_OPTS: Final[dict[str, Any]] = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "socket_timeout": 15,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    }

    _VIDEO_OPTS: Final[dict[str, Any]] = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "skip_download": True,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "socket_timeout": 15,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    }

    def __init__(
        self,
        config_path: str | Path = "config/youtube.yml",
        channels: list[YouTubeChannelConfig] | None = None,
    ):
        super().__init__("YouTube")
        self.config_path = self._resolve_config_path(config_path)
        self.channels = channels or self._load_channels(self.config_path)
        self.error_logger = create_error_logger("youtube_scraper")

    def scrape(self) -> list[dict[str, Any]]:
        if not self.channels:
            logger.warning("No YouTube channels configured")
            return []

        results: list[dict[str, Any]] = []

        for channel in self.channels:
            channel_results = self._scrape_channel(channel)
            results.extend(channel_results)

        logger.info(
            "YouTube scraper gathered %s items across %s channels",
            len(results),
            len(self.channels),
        )
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scrape_channel(self, channel: YouTubeChannelConfig) -> list[dict[str, Any]]:
        logger.info("Scraping YouTube channel %s", channel.name)

        try:
            entries = self._extract_channel_entries(channel)
        except Exception as exc:  # pragma: no cover - safety net
            self.error_logger.log_error(
                error=exc,
                operation="channel_listing",
                context={"channel": channel.name, "target_url": channel.target_url},
            )
            return []

        if not entries:
            logger.info("No entries returned for channel %s", channel.name)
            return []

        items: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for entry in entries:
            if len(items) >= channel.limit:
                break

            video_url = self._resolve_video_url(entry)
            if not video_url or video_url in seen_urls:
                continue

            video_info = entry if self._entry_has_core_details(entry) else None

            if video_info is None:
                try:
                    video_info = self._extract_video_info(video_url)
                except Exception as exc:  # pragma: no cover - yt-dlp errors hard to replicate
                    self.error_logger.log_error(
                        error=exc,
                        operation="video_metadata",
                        context={"channel": channel.name, "video_url": video_url},
                    )
                    continue

            if not self._passes_filters(video_info, channel.max_age_days):
                continue

            item = self._build_scraped_item(channel, video_url, video_info)
            if item:
                items.append(item)
                seen_urls.add(video_url)

        logger.info(
            "Prepared %s videos for channel %s (limit %s)",
            len(items),
            channel.name,
            channel.limit,
        )
        return items

    def _extract_channel_entries(self, channel: YouTubeChannelConfig) -> list[dict[str, Any]]:
        logger.debug("Fetching channel listing for %s", channel.target_url)
        if yt_dlp is None:  # pragma: no cover - runtime safeguard when dependency missing
            raise RuntimeError("yt-dlp is required to run the YouTube scraper")
        listing_opts = {**self._LISTING_OPTS, "playlistend": channel.limit}
        with yt_dlp.YoutubeDL(listing_opts) as ydl:
            info = ydl.extract_info(channel.target_url, download=False)

        entries = info.get("entries", []) if isinstance(info, dict) else []
        flattened: list[dict[str, Any]] = []

        for entry in entries:
            if isinstance(entry, dict):
                flattened.append(entry)
            elif hasattr(entry, "__dict__"):
                flattened.append(dict(entry.__dict__))

        return flattened

    def _extract_video_info(self, video_url: str) -> dict[str, Any]:
        if yt_dlp is None:  # pragma: no cover - runtime safeguard when dependency missing
            raise RuntimeError("yt-dlp is required to run the YouTube scraper")
        with yt_dlp.YoutubeDL(self._VIDEO_OPTS) as ydl:
            return ydl.extract_info(video_url, download=False)

    def _passes_filters(
        self, video_info: dict[str, Any], max_age_days: int | None
    ) -> bool:
        if max_age_days in (None, 0):
            return True

        publication_date = self._extract_publication_datetime(video_info)
        if not publication_date:
            return True

        cutoff = datetime.now(tz=self._utc()) - timedelta(days=max_age_days)
        return publication_date >= cutoff

    def _build_scraped_item(
        self,
        channel: YouTubeChannelConfig,
        video_url: str,
        video_info: dict[str, Any],
    ) -> dict[str, Any] | None:
        title = video_info.get("title") or channel.name
        publication_date = self._extract_publication_datetime(video_info)

        metadata = {
            "platform": "youtube",
            "source": f"youtube:{channel.name}",
            "channel_name": channel.name,
            "channel_id": video_info.get("channel_id"),
            "channel_url": channel.target_url,
            "video_id": video_info.get("id"),
            "video_url": video_url,
            "audio_url": video_url,
            "thumbnail_url": video_info.get("thumbnail"),
            "duration_seconds": video_info.get("duration"),
            "view_count": video_info.get("view_count"),
            "like_count": video_info.get("like_count"),
            "language": channel.language,
            "youtube_video": True,
            "has_transcript": bool(video_info.get("subtitles") or video_info.get("automatic_captions")),
            "publication_date": publication_date.isoformat() if publication_date else None,
        }

        description = video_info.get("description")
        if description:
            metadata["description"] = description[:2000]

        return {
            "url": self._normalize_url(video_url),
            "title": title,
            "content_type": ContentType.PODCAST,
            "metadata": metadata,
        }

    @staticmethod
    def _resolve_video_url(entry: dict[str, Any]) -> str | None:
        if "webpage_url" in entry:
            return entry["webpage_url"]
        if "url" in entry and entry.get("url").startswith("http"):
            return entry["url"]
        if entry.get("id"):
            return f"https://www.youtube.com/watch?v={entry['id']}"
        return None

    @staticmethod
    def _entry_has_core_details(entry: dict[str, Any]) -> bool:
        return any(
            key in entry and entry[key] is not None
            for key in ("duration", "timestamp", "upload_date")
        )

    @staticmethod
    def _extract_publication_datetime(video_info: dict[str, Any]) -> datetime | None:
        utc = YouTubeUnifiedScraper._utc()

        if "upload_date" in video_info and video_info["upload_date"]:
            try:
                return datetime.strptime(video_info["upload_date"], "%Y%m%d").replace(tzinfo=utc)
            except ValueError:
                pass

        if "timestamp" in video_info and video_info["timestamp"]:
            try:
                return datetime.fromtimestamp(int(video_info["timestamp"]), tz=utc)
            except (ValueError, TypeError, OverflowError):
                return None

        if "release_timestamp" in video_info and video_info["release_timestamp"]:
            try:
                return datetime.fromtimestamp(int(video_info["release_timestamp"]), tz=utc)
            except (ValueError, TypeError, OverflowError):
                return None

        return None

    @staticmethod
    def _resolve_config_path(config_path: str | Path) -> Path:
        provided = Path(config_path)
        if provided.is_absolute():
            return provided
        return PROJECT_ROOT / provided

    @classmethod
    def _load_channels(cls, config_path: Path) -> list[YouTubeChannelConfig]:
        if not config_path.exists():
            logger.warning("YouTube config file not found at %s", config_path)
            return []

        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                raw_config = yaml.safe_load(fh) or {}
        except Exception as exc:
            logger.error("Failed to read YouTube config %s: %s", config_path, exc)
            return []

        channel_entries = raw_config.get("channels", [])
        channels: list[YouTubeChannelConfig] = []

        for entry in channel_entries:
            try:
                channel = YouTubeChannelConfig.model_validate(entry)
                channels.append(channel)
            except ValidationError as exc:
                logger.error("Invalid YouTube channel config %s: %s", entry, exc)

        return channels

    @staticmethod
    def _utc():
        try:  # pragma: no branch - executed on import
            from datetime import UTC as stdlib_utc

            return stdlib_utc
        except ImportError:  # pragma: no cover - python <3.11
            return timezone.utc


def load_youtube_channels(config_path: str | Path = "config/youtube.yml") -> list[YouTubeChannelConfig]:
    """Public helper to load channel configuration for testing or scripts."""

    resolved = YouTubeUnifiedScraper._resolve_config_path(config_path)
    return YouTubeUnifiedScraper._load_channels(resolved)
