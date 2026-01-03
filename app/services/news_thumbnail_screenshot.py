"""Screenshot-based thumbnail generation for news content."""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, Field

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.metadata import ContentType
from app.models.schema import Content
from app.services.image_generation import get_image_generation_service
from app.utils.image_paths import get_news_thumbnails_dir

logger = get_logger(__name__)

NEWS_SCREENSHOT_VIEWPORT = (1024, 1024)
NEWS_SCREENSHOT_TIMEOUT_MS = 15000
NEWS_SCREENSHOT_NETWORK_IDLE_MS = 5000
NEWS_SCREENSHOT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
NEWS_SCREENSHOT_LAUNCH_ARGS = ["--no-sandbox"]
PLACEHOLDER_DIR = Path("static/images/placeholders")
PLACEHOLDER_PATH = PLACEHOLDER_DIR / "news_thumbnail.png"


class NewsThumbnailJob(BaseModel):
    """Input for a queued news thumbnail job."""

    content_id: int = Field(..., ge=1)


class NewsThumbnailRequest(BaseModel):
    """Input for screenshot capture."""

    content_id: int = Field(..., ge=1)
    url: str = Field(..., min_length=4)
    viewport_width: int = Field(default=NEWS_SCREENSHOT_VIEWPORT[0], ge=256, le=4096)
    viewport_height: int = Field(default=NEWS_SCREENSHOT_VIEWPORT[1], ge=256, le=4096)
    timeout_ms: int = Field(default=NEWS_SCREENSHOT_TIMEOUT_MS, ge=1000, le=60000)
    network_idle_timeout_ms: int = Field(default=NEWS_SCREENSHOT_NETWORK_IDLE_MS, ge=1000, le=30000)


class NewsThumbnailResult(BaseModel):
    """Result for screenshot thumbnail generation."""

    content_id: int
    success: bool
    image_path: str | None = None
    thumbnail_path: str | None = None
    error_message: str | None = None
    used_placeholder: bool = False


class NewsContentSnapshot(BaseModel):
    """Snapshot of content fields needed for screenshot generation."""

    content_type: str
    url: str
    metadata: dict[str, object]


def generate_news_thumbnail(job: NewsThumbnailJob) -> NewsThumbnailResult:
    """Generate a screenshot-based thumbnail for news content.

    Args:
        job: Job metadata for the thumbnail generation.

    Returns:
        Result of screenshot generation (placeholder on failure).
    """
    content = _load_news_snapshot(job.content_id)
    if content is None:
        return NewsThumbnailResult(
            content_id=job.content_id,
            success=False,
            error_message="Content not found",
        )

    if content.content_type != ContentType.NEWS.value:
        return NewsThumbnailResult(
            content_id=job.content_id,
            success=True,
            error_message="Skipped non-news content",
        )

    url = _select_normalized_url(content)
    if not url:
        return _generate_placeholder(job.content_id, "Missing normalized URL")

    if _is_pdf_content(content, url):
        logger.info(
            "Skipping screenshot for PDF content %s",
            job.content_id,
            extra={
                "component": "thumbnail_generation",
                "operation": "screenshot_skip",
                "item_id": job.content_id,
                "context_data": {"url": url, "reason": "pdf"},
            },
        )
        placeholder_result = _generate_placeholder(job.content_id, "PDF screenshots not supported")
        if placeholder_result.success:
            placeholder_result.used_placeholder = True
        return placeholder_result

    request = NewsThumbnailRequest(content_id=job.content_id, url=url)
    result = _capture_screenshot(request)
    if result.success:
        return result

    logger.error(
        "Screenshot failed for content %s: %s",
        job.content_id,
        result.error_message,
        extra={
            "component": "thumbnail_generation",
            "operation": "screenshot",
            "item_id": job.content_id,
            "context_data": {"url": url},
        },
    )
    placeholder_result = _generate_placeholder(job.content_id, result.error_message or "")
    if placeholder_result.success:
        placeholder_result.used_placeholder = True
    return placeholder_result


def _capture_screenshot(request: NewsThumbnailRequest) -> NewsThumbnailResult:
    """Capture a Playwright screenshot for a news URL.

    Args:
        request: Screenshot request parameters.

    Returns:
        Screenshot result with paths populated on success.
    """
    news_thumbnails_dir = get_news_thumbnails_dir()
    news_thumbnails_dir.mkdir(parents=True, exist_ok=True)

    image_path = news_thumbnails_dir / f"{request.content_id}.png"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=NEWS_SCREENSHOT_LAUNCH_ARGS,
            )
            context = browser.new_context(user_agent=NEWS_SCREENSHOT_USER_AGENT)
            page = context.new_page()
            page.set_viewport_size(
                {"width": request.viewport_width, "height": request.viewport_height}
            )

            page.goto(request.url, wait_until="domcontentloaded", timeout=request.timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=request.network_idle_timeout_ms)
            except PlaywrightTimeoutError:
                logger.info(
                    "Network idle timeout for %s; proceeding with screenshot",
                    request.url,
                )
            page.wait_for_timeout(1000)

            page.screenshot(path=str(image_path), full_page=False, type="png")

            context.close()
            browser.close()

        thumbnail_path = _generate_thumbnail(image_path, request.content_id)

        return NewsThumbnailResult(
            content_id=request.content_id,
            success=True,
            image_path=str(image_path),
            thumbnail_path=str(thumbnail_path) if thumbnail_path else None,
        )

    except PlaywrightTimeoutError as e:
        return NewsThumbnailResult(
            content_id=request.content_id,
            success=False,
            error_message=f"Timeout while loading page: {e}",
        )
    except Exception as e:
        return NewsThumbnailResult(
            content_id=request.content_id,
            success=False,
            error_message=str(e),
        )


def _generate_placeholder(content_id: int, reason: str) -> NewsThumbnailResult:
    """Copy the default placeholder image into the news thumbnail location.

    Args:
        content_id: Content ID to name the placeholder image.
        reason: Reason for fallback.

    Returns:
        Result of placeholder copy + thumbnail generation.
    """
    PLACEHOLDER_DIR.mkdir(parents=True, exist_ok=True)
    news_thumbnails_dir = get_news_thumbnails_dir()
    news_thumbnails_dir.mkdir(parents=True, exist_ok=True)

    target_path = news_thumbnails_dir / f"{content_id}.png"

    if not PLACEHOLDER_PATH.exists():
        _create_placeholder_image()
        if not PLACEHOLDER_PATH.exists():
            logger.error(
                "Missing placeholder image at %s",
                PLACEHOLDER_PATH,
                extra={
                    "component": "thumbnail_generation",
                    "operation": "placeholder",
                    "item_id": content_id,
                },
            )
            return NewsThumbnailResult(
                content_id=content_id,
                success=False,
                error_message="Placeholder image missing",
            )

    shutil.copyfile(PLACEHOLDER_PATH, target_path)
    thumbnail_path = _generate_thumbnail(target_path, content_id)

    return NewsThumbnailResult(
        content_id=content_id,
        success=True,
        image_path=str(target_path),
        thumbnail_path=str(thumbnail_path) if thumbnail_path else None,
        error_message=reason or None,
        used_placeholder=True,
    )


def _generate_thumbnail(source_path: Path, content_id: int) -> Path | None:
    """Generate a 200px thumbnail using the shared image service."""
    image_service = get_image_generation_service()
    return image_service.generate_thumbnail(source_path, content_id)


def _load_news_snapshot(content_id: int) -> NewsContentSnapshot | None:
    """Load content fields required for screenshot generation."""
    with get_db() as db:
        content = db.query(Content).filter(Content.id == content_id).first()
        if not content:
            return None
        return NewsContentSnapshot(
            content_type=content.content_type,
            url=str(content.url),
            metadata=dict(content.content_metadata or {}),
        )


def _select_normalized_url(content: NewsContentSnapshot) -> str | None:
    """Select the best normalized URL for a news item."""
    metadata = content.metadata or {}
    if isinstance(metadata, dict):
        article_section = metadata.get("article")
        if isinstance(article_section, dict):
            article_url = article_section.get("url")
            if isinstance(article_url, str) and article_url.strip():
                return article_url.strip()

        summary_section = metadata.get("summary")
        if isinstance(summary_section, dict):
            final_url = summary_section.get("final_url_after_redirects")
            if isinstance(final_url, str) and final_url.strip():
                return final_url.strip()

    if isinstance(content.url, str) and content.url.strip():
        return content.url.strip()

    return None


def _is_pdf_url(url: str | None) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    parsed = urlparse(url.strip())
    return parsed.path.lower().endswith(".pdf")


def _is_pdf_content(content: NewsContentSnapshot, url: str | None) -> bool:
    metadata = content.metadata or {}
    if isinstance(metadata, dict):
        content_type = metadata.get("content_type")
        if isinstance(content_type, str) and content_type.lower() == "pdf":
            return True
        if metadata.get("is_pdf") is True:
            return True
        article_section = metadata.get("article")
        if isinstance(article_section, dict) and _is_pdf_url(article_section.get("url")):
            return True
    return _is_pdf_url(url)


def _create_placeholder_image() -> None:
    """Create a neutral placeholder image if one does not exist."""
    PLACEHOLDER_DIR.mkdir(parents=True, exist_ok=True)

    size = 512
    image = Image.new("RGB", (size, size), color=(235, 235, 235))
    draw = ImageDraw.Draw(image)
    draw.rectangle([8, 8, size - 9, size - 9], outline=(210, 210, 210), width=2)
    image.save(PLACEHOLDER_PATH, "PNG", optimize=True)
