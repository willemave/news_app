import json
import logging
import re
from datetime import datetime
from typing import Any

import httpx
import yt_dlp

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.base_strategy import UrlProcessorStrategy

logger = logging.getLogger(__name__)


class YouTubeProcessorStrategy(UrlProcessorStrategy):
    """Processing strategy for YouTube videos using yt-dlp."""

    def __init__(self, http_client: RobustHttpClient):
        super().__init__(http_client)
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "ignoreerrors": True,
            "no_check_certificate": True,
            # Subtitle options
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "skip_download": True,  # Don't download video
        }

    def can_handle_url(self, url: str, response_headers: httpx.Headers | None = None) -> bool:
        """Check if this strategy can handle the given URL."""
        patterns = [
            r"youtube\.com/watch\?v=",
            r"youtu\.be/",
            r"youtube\.com/embed/",
            r"m\.youtube\.com/watch\?v=",
            r"youtube\.com/v/",
            r"youtube\.com/shorts/",
        ]
        return any(re.search(pattern, url) for pattern in patterns)

    async def download_content(self, url: str) -> bytes:
        """Download content from YouTube (returns empty bytes as we only need metadata)."""
        # We don't actually download the video, just return empty bytes
        # The actual content comes from the transcript
        return b""

    async def extract_data(self, content: bytes, url: str) -> dict[str, Any]:
        """Extract metadata and transcript from YouTube video."""
        logger.info(f"Extracting YouTube data from: {url}")

        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            try:
                # Extract video info
                info = ydl.extract_info(url, download=False)

                # Extract basic metadata
                video_id = info.get("id")
                title = info.get("title", "Untitled")
                uploader = info.get("uploader", "Unknown")
                description = info.get("description", "")
                duration = info.get("duration", 0)
                upload_date = info.get("upload_date")
                view_count = info.get("view_count", 0)
                like_count = info.get("like_count", 0)
                thumbnail = info.get("thumbnail")

                # Get transcript
                transcript = await self._extract_transcript(info)

                # Parse upload date
                if upload_date:
                    publication_date = datetime.strptime(upload_date, "%Y%m%d")
                else:
                    publication_date = datetime.now()

                return {
                    "title": title,
                    # Use transcript if available, else description
                    "text": transcript or description,
                    "metadata": {
                        "platform": "youtube",  # Platform identifier
                        "source": f"youtube:{uploader}",  # Standardized format: platform:channel
                        "video_id": video_id,
                        "channel": uploader,
                        "duration": duration,
                        "description": description[:1000] if description else None,
                        "thumbnail_url": thumbnail,
                        "view_count": view_count,
                        "like_count": like_count,
                        "publication_date": publication_date.isoformat(),
                        "has_transcript": bool(transcript),
                        "transcript": transcript,
                        "audio_url": url,  # Store YouTube URL as audio_url for consistency
                        "video_url": url,  # Also store as video_url
                    },
                }

            except Exception as e:
                logger.error(f"Error extracting YouTube data: {e}")
                raise

    async def _extract_transcript(self, video_info: dict[str, Any]) -> str | None:
        """Extract transcript from video info."""
        try:
            # Check for subtitles
            subtitles = video_info.get("subtitles", {})
            automatic_captions = video_info.get("automatic_captions", {})

            # Prefer manual subtitles over automatic
            subtitle_tracks = subtitles.get("en", []) or automatic_captions.get("en", [])

            if not subtitle_tracks:
                logger.warning(f"No English subtitles found for video {video_info.get('id')}")
                return None

            # Get the first available format (usually vtt or srv3)
            for track in subtitle_tracks:
                if track.get("ext") in ["vtt", "srv3", "json3"]:
                    # yt-dlp can fetch the subtitle content
                    subtitle_url = track.get("url")
                    if subtitle_url:
                        transcript = await self._download_subtitle(subtitle_url, track.get("ext"))
                        if transcript:
                            return transcript

            # If we have subtitle data directly in the info
            requested_subtitles = video_info.get("requested_subtitles", {})
            if "en" in requested_subtitles and requested_subtitles["en"].get("data"):
                return self._parse_subtitle_data(requested_subtitles["en"]["data"])

            return None

        except Exception as e:
            logger.error(f"Error extracting transcript: {e}")
            return None

    async def _download_subtitle(self, url: str, ext: str) -> str | None:
        """Download and parse subtitle file."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()

                content = response.text

                # Parse based on format
                if ext == "vtt":
                    return self._parse_vtt(content)
                elif ext in ["srv3", "json3"]:
                    return self._parse_json_subtitle(content)
                else:
                    return content

        except Exception as e:
            logger.error(f"Error downloading subtitle: {e}")
            return None

    def _parse_vtt(self, vtt_content: str) -> str:
        """Parse VTT subtitle format to plain text."""
        lines = vtt_content.split("\n")
        transcript_lines = []

        # Skip header
        i = 0
        while i < len(lines) and not lines[i].strip().startswith("00:"):
            i += 1

        # Extract text
        while i < len(lines):
            line = lines[i].strip()
            # Skip timecodes and empty lines
            if "-->" in line or not line or line.startswith("00:"):
                i += 1
                continue
            # Skip tags
            line = re.sub(r"<[^>]+>", "", line)
            if line:
                transcript_lines.append(line)
            i += 1

        return " ".join(transcript_lines)

    def _parse_json_subtitle(self, json_content: str) -> str:
        """Parse JSON subtitle format to plain text."""
        try:
            data = json.loads(json_content)

            # Handle different JSON subtitle formats
            if isinstance(data, dict) and "events" in data:
                # srv3 format
                events = data.get("events", [])
                transcript_parts = []

                for event in events:
                    if "segs" in event:
                        for seg in event["segs"]:
                            text = seg.get("utf8", "")
                            if text and text.strip():
                                transcript_parts.append(text.strip())

                return " ".join(transcript_parts)

            elif isinstance(data, list):
                # Simple JSON array format
                return " ".join(item.get("text", "") for item in data if "text" in item)

            return json_content

        except json.JSONDecodeError:
            logger.error("Failed to parse JSON subtitle")
            return json_content

    def _parse_subtitle_data(self, data: str) -> str:
        """Parse subtitle data that's already been fetched."""
        # Try to detect format
        if data.startswith("WEBVTT"):
            return self._parse_vtt(data)
        elif data.startswith("{") or data.startswith("["):
            return self._parse_json_subtitle(data)
        else:
            # Return as-is if format unknown
            return data

    async def prepare_for_llm(self, extracted_data: dict[str, Any]) -> dict[str, Any]:
        """Prepare the extracted data for LLM processing."""
        metadata = extracted_data.get("metadata", {})
        title = extracted_data.get("title", "Untitled")
        channel = metadata.get("channel", "Unknown")
        description = metadata.get("description", "")
        transcript = metadata.get("transcript", "")

        # Format duration
        duration = metadata.get("duration", 0)
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        # Build content for LLM
        parts = [
            f"YouTube Video: {title}",
            f"Channel: {channel}",
            f"Duration: {duration_str}",
            f"Views: {metadata.get('view_count', 0):,}",
            "",
        ]

        if description:
            parts.extend(["Description:", description, ""])

        if transcript:
            parts.extend(["Transcript:", transcript])
        else:
            parts.append(
                "Note: No transcript available. Summary based on title and description only."
            )

        content_text = "\n".join(parts)

        return {
            "content_to_filter": content_text,
            "content_to_summarize": content_text,
            "is_pdf": False,
        }
