"""Sequential task processor for robust, simple task processing."""

import signal
import sys
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.constants import SELF_SUBMISSION_SOURCE
from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.core.settings import get_settings
from app.models.metadata import ContentClassification, ContentStatus, ContentType, NewsSummary
from app.models.schema import Content, ProcessingTask
from app.pipeline.podcast_workers import PodcastDownloadWorker, PodcastTranscribeWorker
from app.pipeline.worker import ContentWorker, get_llm_service
from app.scraping.runner import ScraperRunner
from app.services.content_analyzer import AnalysisError, get_content_analyzer
from app.services.content_submission import normalize_url
from app.services.feed_detection import detect_feeds_from_html
from app.services.feed_discovery import run_feed_discovery
from app.services.feed_subscription import subscribe_to_detected_feed
from app.services.http import get_http_service
from app.services.instruction_links import create_contents_from_instruction_links
from app.services.queue import QueueService, TaskType
from app.services.scraper_configs import ensure_inbox_status
from app.services.twitter_share import (
    TweetFetchParams,
    canonical_tweet_url,
    extract_tweet_id,
    fetch_tweet_detail,
    resolve_twitter_credentials,
)

logger = get_logger(__name__)


def _build_analysis_instruction(
    instruction: str | None,
    crawl_links: bool,
) -> str | None:
    """Build the instruction string to send to the content analyzer.

    Args:
        instruction: Raw instruction provided by the client/share sheet.
        crawl_links: Whether link crawling was explicitly requested.

    Returns:
        Cleaned instruction string or a default crawl prompt when enabled.
    """
    cleaned = instruction.strip() if instruction else None
    if cleaned:
        return cleaned
    if not crawl_links:
        return None
    return "Extract relevant links from the submitted page."


def _build_thread_text(tweet_texts: list[str]) -> str:
    """Join tweet/thread text into a single body."""
    cleaned = [text.strip() for text in tweet_texts if isinstance(text, str) and text.strip()]
    return "\n\n".join(cleaned)


class SequentialTaskProcessor:
    """Sequential task processor - processes tasks one at a time."""

    def __init__(self):
        logger.debug("Initializing SequentialTaskProcessor...")
        self.queue_service = QueueService()
        logger.debug("QueueService initialized")
        self.llm_service = get_llm_service()
        logger.debug("Shared summarization service initialized")
        self.settings = get_settings()
        logger.debug("Settings loaded")
        self.running = True
        self.worker_id = "sequential-processor"
        logger.debug(f"SequentialTaskProcessor initialized with worker_id: {self.worker_id}")

    def process_task(self, task_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Process a single task."""
        task_id = task_data.get("id", "unknown")
        start_time = time.time()
        task_error: str | None = None

        try:
            task_type = TaskType(task_data["task_type"])
            logger.info(f"Processing task {task_id} of type {task_type}")
            logger.debug(f"Task {task_id} data: {task_data}")

            result = False
            if task_type == TaskType.SCRAPE:
                result = self._process_scrape_task(task_data)
            elif task_type == TaskType.ANALYZE_URL:
                result = self._process_analyze_url_task(task_data)
            elif task_type == TaskType.PROCESS_CONTENT:
                result = self._process_content_task(task_data)
            elif task_type == TaskType.DOWNLOAD_AUDIO:
                result = self._process_download_task(task_data)
            elif task_type == TaskType.TRANSCRIBE:
                result = self._process_transcribe_task(task_data)
            elif task_type == TaskType.SUMMARIZE:
                result = self._process_summarize_task(task_data)
            elif task_type == TaskType.GENERATE_IMAGE:
                result = self._process_generate_image_task(task_data)
            elif task_type == TaskType.GENERATE_THUMBNAIL:
                result = self._process_generate_thumbnail_task(task_data)
            elif task_type == TaskType.DISCOVER_FEEDS:
                result = self._process_discover_feeds_task(task_data)
            else:
                logger.error(f"Unknown task type: {task_type}")
                result = False

            if not result:
                task_error = task_data.get("error_message") or f"{task_type.value} returned False"

            elapsed = time.time() - start_time
            logger.info(f"Task {task_id} completed in {elapsed:.2f}s with result: {result}")
            return result, task_error

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Error processing task {task_id} after {elapsed:.2f}s: {e}", exc_info=True
            )
            return False, str(e)

    def _process_scrape_task(self, task_data: dict[str, Any]) -> bool:
        """Process a scrape task."""
        try:
            payload = task_data.get("payload", {})
            sources = payload.get("sources", ["all"])
            runner = ScraperRunner()

            # Run scrapers
            if sources == ["all"]:
                runner.run_all()
            else:
                for source in sources:
                    runner.run_scraper(source)
            return True
        except Exception as e:
            logger.error(f"Scraper error: {e}", exc_info=True)
            return False

    def _process_analyze_url_task(self, task_data: dict[str, Any]) -> bool:
        """Analyze URL to determine content type, then enqueue PROCESS_CONTENT.

        Uses pattern matching for known platforms (fast) or LLM web search
        for unknown URLs to determine content type and extract metadata.
        """
        from app.models.metadata import ContentType
        from app.services.url_detection import (
            infer_content_type_and_platform,
            should_use_llm_analysis,
        )

        try:
            content_id = task_data.get("content_id") or task_data.get("payload", {}).get(
                "content_id"
            )
            if not content_id:
                logger.error("No content_id provided for analyze_url task")
                return False

            content_id = int(content_id)
            logger.info(f"Analyzing URL for content {content_id}")

            with get_db() as db:
                content = db.query(Content).filter(Content.id == content_id).first()
                if not content:
                    logger.error(f"Content {content_id} not found for URL analysis")
                    return False

                url = content.url
                metadata = dict(content.content_metadata or {})

                payload = task_data.get("payload", {}) or {}
                instruction = payload.get("instruction")
                crawl_links = bool(payload.get("crawl_links"))
                subscribe_to_feed = bool(payload.get("subscribe_to_feed"))
                task_id = task_data.get("id")
                analysis_result = None
                analysis_instruction = _build_analysis_instruction(instruction, crawl_links)
                tweet_handled = False

                if subscribe_to_feed:
                    html_content: str | None = None
                    fetch_status = "no_feed_found"
                    try:
                        http_service = get_http_service()
                        body, _headers = http_service.fetch_content(url)
                        if isinstance(body, str):
                            html_content = body
                    except Exception as exc:  # noqa: BLE001
                        fetch_status = "fetch_failed"
                        logger.error(
                            "Failed to fetch URL for feed detection: %s",
                            exc,
                            extra={
                                "component": "sequential_task_processor",
                                "operation": "feed_detect_fetch",
                                "item_id": content_id,
                                "context_data": {"url": url, "error": str(exc)},
                            },
                        )

                    detected_feed = None
                    all_detected_feeds = None
                    if html_content:
                        feed_data = detect_feeds_from_html(
                            html_content,
                            str(url),
                            page_title=content.title,
                            source=SELF_SUBMISSION_SOURCE,
                            content_type=content.content_type,
                        )
                        if feed_data:
                            detected_feed = feed_data.get("detected_feed")
                            all_detected_feeds = feed_data.get("all_detected_feeds")

                    metadata["subscribe_to_feed"] = True
                    if detected_feed:
                        metadata["detected_feed"] = detected_feed
                        if all_detected_feeds:
                            metadata["all_detected_feeds"] = all_detected_feeds

                        created, fetch_status = subscribe_to_detected_feed(
                            db,
                            metadata.get("submitted_by_user_id"),
                            detected_feed,
                            display_name=detected_feed.get("title"),
                        )
                        metadata["feed_subscription"] = {
                            "status": fetch_status,
                            "feed_url": detected_feed.get("url"),
                            "feed_type": detected_feed.get("type"),
                            "created": created,
                        }
                    else:
                        metadata["feed_subscription"] = {"status": fetch_status}

                    content.content_metadata = metadata
                    content.status = ContentStatus.SKIPPED.value
                    content.processed_at = datetime.now(UTC)
                    db.commit()

                    logger.info(
                        "Feed subscription flow completed for content %s (status=%s)",
                        content_id,
                        metadata.get("feed_subscription", {}).get("status"),
                    )
                    return True

                tweet_id = extract_tweet_id(str(url))
                is_self_submission = content.source == SELF_SUBMISSION_SOURCE or bool(
                    metadata.get("submitted_by_user_id")
                )
                if tweet_id and is_self_submission:
                    tweet_handled = True
                    credentials_result = resolve_twitter_credentials()
                    if not credentials_result.success or not credentials_result.credentials:
                        error_message = (
                            credentials_result.error or "Twitter credentials unavailable"
                        )
                        logger.error(
                            "Twitter share fetch failed: %s",
                            error_message,
                            extra={
                                "component": "twitter_share",
                                "operation": "resolve_credentials",
                                "item_id": content_id,
                            },
                        )
                        content.status = ContentStatus.FAILED.value
                        content.error_message = error_message
                        db.commit()
                        return False

                    tweet_url = canonical_tweet_url(tweet_id)
                    fetch_result = fetch_tweet_detail(
                        TweetFetchParams(
                            tweet_id=tweet_id,
                            credentials=credentials_result.credentials,
                            include_thread=True,
                        )
                    )
                    if not fetch_result.success or not fetch_result.tweet:
                        error_message = fetch_result.error or "TweetDetail request failed"
                        logger.error(
                            "Twitter share fetch failed: %s",
                            error_message,
                            extra={
                                "component": "twitter_share",
                                "operation": "fetch_tweet",
                                "item_id": content_id,
                            },
                        )
                        content.status = ContentStatus.FAILED.value
                        content.error_message = error_message
                        db.commit()
                        return False

                    thread_tweets = fetch_result.thread or [fetch_result.tweet]
                    thread_text = _build_thread_text([tweet.text for tweet in thread_tweets])
                    external_urls: list[str] = []
                    for raw_url in fetch_result.external_urls:
                        try:
                            external_urls.append(normalize_url(raw_url))
                        except Exception:
                            logger.warning(
                                "Skipping invalid tweet external URL: %s",
                                raw_url,
                                extra={
                                    "component": "twitter_share",
                                    "operation": "normalize_external_url",
                                    "item_id": content_id,
                                },
                            )

                    metadata.update(
                        {
                            "platform": "twitter",
                            "discussion_url": tweet_url,
                            "tweet_id": tweet_id,
                            "tweet_url": tweet_url,
                            "tweet_author": fetch_result.tweet.author_name,
                            "tweet_author_username": fetch_result.tweet.author_username,
                            "tweet_created_at": fetch_result.tweet.created_at,
                            "tweet_like_count": fetch_result.tweet.like_count,
                            "tweet_retweet_count": fetch_result.tweet.retweet_count,
                            "tweet_reply_count": fetch_result.tweet.reply_count,
                            "tweet_text": fetch_result.tweet.text,
                            "tweet_thread_text": thread_text,
                            "tweet_external_urls": external_urls,
                        }
                    )

                    content.content_type = ContentType.ARTICLE.value
                    content.platform = "twitter"
                    if not content.source_url:
                        content.source_url = tweet_url

                    fanout_urls: list[str] = []
                    if external_urls:
                        content.url = external_urls[0]
                        fanout_urls = external_urls[1:]
                    else:
                        content.url = tweet_url
                        metadata["tweet_only"] = True

                    content.content_metadata = metadata
                    db.commit()

                    submitter_id = metadata.get("submitted_by_user_id")
                    submitted_via = metadata.get("submitted_via") or "share_sheet"
                    for normalized_url in fanout_urls:
                        existing = (
                            db.query(Content)
                            .filter(
                                Content.url == normalized_url,
                                Content.content_type == ContentType.ARTICLE.value,
                            )
                            .first()
                        )
                        if existing:
                            if submitter_id:
                                ensure_inbox_status(
                                    db,
                                    submitter_id,
                                    existing.id,
                                    content_type=existing.content_type,
                                )
                                db.commit()
                            continue

                        fanout_metadata = dict(metadata)
                        fanout_metadata["source"] = SELF_SUBMISSION_SOURCE
                        if submitter_id:
                            fanout_metadata["submitted_by_user_id"] = submitter_id
                        fanout_metadata["submitted_via"] = f"{submitted_via}_tweet_fanout"

                        new_content = Content(
                            url=normalized_url,
                            source_url=tweet_url,
                            content_type=ContentType.ARTICLE.value,
                            title=None,
                            source=SELF_SUBMISSION_SOURCE,
                            platform="twitter",
                            is_aggregate=False,
                            status=ContentStatus.NEW.value,
                            classification=ContentClassification.TO_READ.value,
                            content_metadata=fanout_metadata,
                        )
                        db.add(new_content)
                        try:
                            db.commit()
                        except IntegrityError:
                            db.rollback()
                            continue
                        db.refresh(new_content)

                        if submitter_id:
                            ensure_inbox_status(
                                db,
                                submitter_id,
                                new_content.id,
                                content_type=new_content.content_type,
                            )
                            db.commit()

                        self.queue_service.enqueue(TaskType.ANALYZE_URL, content_id=new_content.id)

                    logger.info(
                        "Twitter share processed for content %s (external_urls=%s)",
                        content_id,
                        len(external_urls),
                        extra={
                            "component": "twitter_share",
                            "operation": "analyze_url",
                            "item_id": content_id,
                        },
                    )

                    # Skip standard LLM analysis for tweets.
                    analysis_result = None
                if not tweet_handled:
                    # Check if this is a known platform (fast path)
                    use_llm = should_use_llm_analysis(url) or bool(analysis_instruction)
                    if not use_llm:
                        # Use pattern-based detection
                        detected_type, platform = infer_content_type_and_platform(
                            url,
                            None,
                            None,
                        )
                        logger.info(
                            "Pattern-based detection for %s: type=%s, platform=%s",
                            content_id,
                            detected_type.value,
                            platform,
                        )

                        content.content_type = detected_type.value
                        if platform:
                            content.platform = platform
                            metadata["platform"] = platform

                        content.content_metadata = metadata
                        db.commit()

                    else:
                        # Use LLM analysis with web search
                        analyzer = get_content_analyzer()
                        result = analyzer.analyze_url(url, instruction=analysis_instruction)

                        if isinstance(result, AnalysisError):
                            # Fall back to pattern detection on error
                            logger.warning(
                                "LLM analysis failed for %s, using pattern detection: %s",
                                content_id,
                                result.message,
                            )
                            detected_type, platform = infer_content_type_and_platform(
                                url,
                                None,
                                None,
                            )
                            content.content_type = detected_type.value
                            if platform:
                                content.platform = platform
                                metadata["platform"] = platform
                        else:
                            analysis = result.analysis
                            # Map LLM result to ContentType
                            if analysis.content_type == "article":
                                content.content_type = ContentType.ARTICLE.value
                            elif analysis.content_type in ("podcast", "video"):
                                content.content_type = ContentType.PODCAST.value
                            else:
                                content.content_type = ContentType.ARTICLE.value

                            # Store extracted metadata
                            if analysis.platform:
                                content.platform = analysis.platform
                                metadata["platform"] = analysis.platform
                            if analysis.media_url:
                                metadata["audio_url"] = analysis.media_url
                            if analysis.media_format:
                                metadata["media_format"] = analysis.media_format
                            if analysis.title:
                                metadata["extracted_title"] = analysis.title
                                if not content.title:
                                    content.title = analysis.title
                            if analysis.description:
                                metadata["extracted_description"] = analysis.description
                            if analysis.duration_seconds:
                                metadata["duration"] = analysis.duration_seconds
                            if analysis.content_type == "video":
                                metadata["is_video"] = True
                                metadata["video_url"] = url

                            logger.info(
                                f"LLM analysis complete for {content_id}: "
                                f"type={content.content_type}, platform={content.platform}"
                            )
                            analysis_result = result

                        content.content_metadata = metadata
                        db.commit()

                if crawl_links and analysis_result and analysis_result.instruction:
                    created_ids = create_contents_from_instruction_links(
                        db,
                        content,
                        analysis_result.instruction.links,
                    )
                    if created_ids:
                        logger.info(
                            "Created %d content records from instruction links for %s",
                            len(created_ids),
                            content_id,
                        )

                if instruction and task_id:
                    task = (
                        db.query(ProcessingTask).filter(ProcessingTask.id == int(task_id)).first()
                    )
                    if task and isinstance(task.payload, dict) and "instruction" in task.payload:
                        updated_payload = dict(task.payload)
                        updated_payload.pop("instruction", None)
                        task.payload = updated_payload
                        db.commit()

            # Enqueue PROCESS_CONTENT task
            self.queue_service.enqueue(TaskType.PROCESS_CONTENT, content_id=content_id)
            logger.info(f"Enqueued PROCESS_CONTENT for content {content_id}")

            return True

        except Exception as e:
            logger.exception(
                f"URL analysis error for content_id {content_id}: {e}",
                extra={
                    "component": "sequential_task_processor",
                    "operation": "analyze_url",
                    "item_id": content_id,
                    "context_data": {"error": str(e)},
                },
            )
            return False

    def _process_content_task(self, task_data: dict[str, Any]) -> bool:
        """Process content with strategies."""
        try:
            # Try to get content_id from top level first, then from payload
            content_id = task_data.get("content_id")
            if content_id is None:
                content_id = task_data.get("payload", {}).get("content_id")

            if content_id is None:
                logger.error(f"No content_id found in task data: {task_data}")
                return False

            content_id = int(content_id)
            logger.info(f"Processing content {content_id}")

            worker = ContentWorker()
            success = worker.process_content(content_id, self.worker_id)

            if success:
                logger.info(f"Content {content_id} processed successfully")
                return True
            else:
                logger.error(f"Content {content_id} processing failed")
                return False
        except Exception as e:
            logger.error(
                f"Content processing error for content_id {content_id}: {e}", exc_info=True
            )
            logger.error(f"Full task data: {task_data}")
            return False

    def _process_download_task(self, task_data: dict[str, Any]) -> bool:
        """Download audio files."""
        try:
            content_id = task_data.get("content_id") or task_data.get("payload", {}).get(
                "content_id"
            )
            if not content_id:
                logger.error("No content_id provided for download task")
                return False

            worker = PodcastDownloadWorker()
            return worker.process_download_task(content_id)
        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            return False

    def _process_transcribe_task(self, task_data: dict[str, Any]) -> bool:
        """Transcribe audio files."""
        try:
            content_id = task_data.get("content_id") or task_data.get("payload", {}).get(
                "content_id"
            )
            if not content_id:
                logger.error("No content_id provided for transcribe task")
                return False

            worker = PodcastTranscribeWorker()
            return worker.process_transcribe_task(content_id)
        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            return False

    def _process_summarize_task(self, task_data: dict[str, Any]) -> bool:
        """Generate content summaries."""
        try:
            content_id = task_data.get("content_id") or task_data.get("payload", {}).get(
                "content_id"
            )

            if not content_id:
                logger.error(
                    "SUMMARIZE_TASK_ERROR: No content_id provided. Task data: %s",
                    task_data,
                )
                return False

            logger.info("Processing summarize task for content %s", content_id)

            # Get content from database
            with get_db() as db:
                content = db.query(Content).filter(Content.id == content_id).first()
                if not content:
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: Content %s not found in database",
                        content_id,
                    )
                    return False

                # Log content details for debugging
                title_preview = "No title"
                if content.title and isinstance(content.title, str):
                    title_preview = content.title[:50]
                logger.info(
                    "Summarizing content %s: type=%s, title=%s, url=%s, status=%s",
                    content_id,
                    content.content_type,
                    title_preview,
                    content.url,
                    content.status,
                )

                def _persist_failure(reason: str) -> None:
                    metadata = dict(content.content_metadata or {})
                    metadata.pop("summary", None)
                    existing_errors = metadata.get("processing_errors")
                    processing_errors = (
                        existing_errors.copy() if isinstance(existing_errors, list) else []
                    )
                    processing_errors.append(
                        {
                            "stage": "summarization",
                            "reason": reason,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                    metadata["processing_errors"] = processing_errors

                    content.content_metadata = metadata
                    content.status = ContentStatus.FAILED.value
                    content.error_message = reason[:500]
                    content.processed_at = datetime.utcnow()
                    db.commit()

                # Get content to summarize
                metadata = content.content_metadata or {}
                if content.content_type == "article":
                    text_to_summarize = metadata.get("content", "")
                elif content.content_type == "news":
                    text_to_summarize = metadata.get("content", "")
                    # Build aggregator context for news items
                    aggregator_context = self._build_news_context(metadata)
                    if aggregator_context and text_to_summarize:
                        text_to_summarize = (
                            f"Context:\n{aggregator_context}\n\n"
                            f"Article Content:\n{text_to_summarize}"
                        )
                elif content.content_type == "podcast":
                    text_to_summarize = metadata.get("transcript", "")
                else:
                    reason = f"Unknown content type for summarization: {content.content_type}"
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: %s. Content %s, URL: %s",
                        reason,
                        content_id,
                        content.url,
                        extra={
                            "component": "summarization",
                            "operation": "summarize_task",
                            "item_id": content_id,
                            "context_data": {
                                "content_type": content.content_type,
                                "url": str(content.url),
                                "title": content.title,
                            },
                        },
                    )
                    _persist_failure(reason)
                    return False

                if not text_to_summarize:
                    # Determine what field was expected
                    expected_field = (
                        "transcript" if content.content_type == "podcast" else "content"
                    )
                    reason = f"No text to summarize for content {content_id}"
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: %s. Type: %s, expected field: %s, "
                        "metadata keys: %s, URL: %s",
                        reason,
                        content.content_type,
                        expected_field,
                        list(metadata.keys()),
                        content.url,
                        extra={
                            "component": "summarization",
                            "operation": "summarize_task",
                            "item_id": content_id,
                            "context_data": {
                                "content_type": content.content_type,
                                "expected_field": expected_field,
                                "metadata_keys": list(metadata.keys()),
                                "url": str(content.url),
                                "title": content.title,
                            },
                        },
                    )
                    _persist_failure(reason)
                    return False

                # Log text length for monitoring
                logger.debug(
                    "Content %s has %d characters to summarize",
                    content_id,
                    len(text_to_summarize),
                )

                # Determine summarization parameters based on content type
                summarization_type = content.content_type
                provider_override = None
                max_bullet_points = 6
                max_quotes = 8

                if content.content_type == "news":
                    summarization_type = "news_digest"
                    provider_override = "openai"
                    max_bullet_points = 4
                    max_quotes = 0
                elif content.content_type in ("article", "podcast"):
                    # Use interleaved format for articles and podcasts
                    summarization_type = "interleaved"

                logger.info(
                    "Calling LLM for content %s: provider=%s, type=%s, "
                    "text_length=%d, max_bullets=%d",
                    content_id,
                    provider_override or "default",
                    summarization_type,
                    len(text_to_summarize),
                    max_bullet_points,
                )

                try:
                    summary = self.llm_service.summarize_content(
                        text_to_summarize,
                        content_type=summarization_type,
                        content_id=content.id,
                        max_bullet_points=max_bullet_points,
                        max_quotes=max_quotes,
                        provider_override=provider_override,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "SUMMARIZE_TASK_ERROR: LLM call failed for content %s (%s). "
                        "Error: %s, URL: %s, text_length: %d",
                        content_id,
                        content.content_type,
                        str(e),
                        content.url,
                        len(text_to_summarize),
                        extra={
                            "component": "summarization",
                            "operation": "llm_summarization",
                            "item_id": content_id,
                            "context_data": {
                                "content_type": content.content_type,
                                "summarization_type": summarization_type,
                                "provider": provider_override or "default",
                                "text_length": len(text_to_summarize),
                                "url": str(content.url),
                                "title": content.title,
                            },
                        },
                    )
                    _persist_failure(f"Summarization error: {e}")
                    return False

                if summary is not None:
                    # Update content with summary
                    # Create a new dictionary to ensure SQLAlchemy detects the change
                    metadata = dict(content.content_metadata or {})
                    summary_dict = (
                        summary.model_dump(mode="json", by_alias=True)
                        if hasattr(summary, "model_dump")
                        else summary
                    )

                    # Handle NewsSummary specially to update article metadata
                    if isinstance(summary, NewsSummary):
                        summary_dict.setdefault("classification", summary.classification)
                        metadata["summary"] = summary_dict

                        # Update article section
                        article_section = metadata.get("article", {})
                        article_section.setdefault(
                            "url",
                            summary_dict.get("final_url_after_redirects")
                            or summary_dict.get("article", {}).get("url"),
                        )
                        if summary.title and not article_section.get("title"):
                            article_section["title"] = summary.title
                        metadata["article"] = article_section

                        # Update content title
                        if summary.title:
                            content.title = summary.title

                        logger.info("Generated news digest summary for content %s", content_id)
                    else:
                        metadata["summary"] = summary_dict
                        # Update title if provided
                        if summary_dict.get("title") and not content.title:
                            content.title = summary_dict["title"]
                        logger.info("Generated summary for content %s", content_id)

                    metadata["summarization_date"] = datetime.utcnow().isoformat()

                    # Assign new dictionary to trigger SQLAlchemy change detection
                    content.content_metadata = metadata
                    content.status = ContentStatus.COMPLETED.value
                    content.processed_at = datetime.utcnow()
                    db.commit()

                    if content.content_type == ContentType.NEWS.value:
                        self.queue_service.enqueue(
                            task_type=TaskType.GENERATE_THUMBNAIL,
                            content_id=content_id,
                        )
                        logger.info(
                            "Enqueued thumbnail generation for news content %s",
                            content_id,
                        )
                    else:
                        self.queue_service.enqueue(
                            task_type=TaskType.GENERATE_IMAGE,
                            content_id=content_id,
                        )
                        logger.info("Enqueued image generation for content %s", content_id)

                    return True

                reason = "LLM summarization returned None"
                logger.error(
                    "MISSING_SUMMARY: Content %s (%s) - %s. Title: %s, Text length: %s, URL: %s",
                    content_id,
                    content.content_type,
                    reason,
                    content.title,
                    len(text_to_summarize) if text_to_summarize else 0,
                    content.url,
                    extra={
                        "component": "summarization",
                        "operation": "llm_summarization",
                        "item_id": content_id,
                        "context_data": {
                            "content_type": content.content_type,
                            "summarization_type": summarization_type,
                            "provider": provider_override or "default",
                            "text_length": len(text_to_summarize) if text_to_summarize else 0,
                            "url": str(content.url),
                            "title": content.title,
                        },
                    },
                )
                _persist_failure(reason)
                return False

        except Exception as e:
            logger.error(f"Summarization error: {e}", exc_info=True)
            return False

    def _build_news_context(self, metadata: dict[str, Any]) -> str:
        """Build aggregator context string for news items."""
        article = metadata.get("article", {})
        aggregator = metadata.get("aggregator", {})
        lines: list[str] = []

        article_title = article.get("title") or ""
        article_url = article.get("url") or ""

        if article_title:
            lines.append(f"Article Title: {article_title}")
        if article_url:
            lines.append(f"Article URL: {article_url}")

        if aggregator:
            name = aggregator.get("name") or metadata.get("platform")
            agg_title = aggregator.get("title")
            agg_url = metadata.get("discussion_url") or aggregator.get("url")
            author = aggregator.get("author")

            context_bits = []
            if name:
                context_bits.append(name)
            if author:
                context_bits.append(f"by {author}")
            if agg_title and agg_title != article_title:
                lines.append(f"Aggregator Headline: {agg_title}")
            if context_bits:
                lines.append("Aggregator Context: " + ", ".join(context_bits))
            if agg_url:
                lines.append(f"Discussion URL: {agg_url}")

            extra = aggregator.get("metadata") or {}
            highlights = []
            for field in ["score", "comments_count", "likes", "retweets", "replies"]:
                value = extra.get(field)
                if value is not None:
                    highlights.append(f"{field}={value}")
            if highlights:
                lines.append("Signals: " + ", ".join(highlights))

        summary_payload = metadata.get("summary") if isinstance(metadata, dict) else {}
        excerpt = metadata.get("excerpt")
        if not excerpt and isinstance(summary_payload, dict):
            excerpt = (
                summary_payload.get("overview")
                or summary_payload.get("summary")
                or summary_payload.get("hook")
                or summary_payload.get("takeaway")
            )
        if excerpt:
            lines.append(f"Aggregator Summary: {excerpt}")

        return "\n".join(lines)

    def _process_generate_image_task(self, task_data: dict[str, Any]) -> bool:
        """Generate an AI image for content."""
        try:
            content_id = task_data.get("content_id") or task_data.get("payload", {}).get(
                "content_id"
            )
            if not content_id:
                logger.error("No content_id provided for image generation task")
                return False

            content_id = int(content_id)
            logger.info("Generating image for content %s", content_id)

            # Get content from database
            with get_db() as db:
                content = db.query(Content).filter(Content.id == content_id).first()
                if not content:
                    logger.error("Content %s not found for image generation", content_id)
                    return False
                if content.content_type == ContentType.NEWS.value:
                    logger.info(
                        "Skipping AI image generation for news content %s",
                        content_id,
                    )
                    return True

                # Convert to domain model
                from app.domain.converters import content_to_domain

                domain_content = content_to_domain(content)

                # Generate image
                from app.services.image_generation import get_image_generation_service
                from app.utils.image_urls import build_content_image_url, build_thumbnail_url

                image_service = get_image_generation_service()
                result = image_service.generate_image(domain_content)

                if result.success:
                    # Update metadata to record generation
                    metadata = dict(content.content_metadata or {})
                    metadata["image_generated_at"] = datetime.now(UTC).isoformat()
                    metadata["image_url"] = build_content_image_url(content_id)
                    if result.thumbnail_path:
                        metadata["thumbnail_url"] = build_thumbnail_url(content_id)
                    content.content_metadata = metadata
                    db.commit()

                    logger.info(
                        "Successfully generated image for content %s at %s",
                        content_id,
                        result.image_path,
                    )
                    return True
                else:
                    if result.error_message and "Skipped" in result.error_message:
                        # Not an error, just skipped (e.g., YouTube podcast)
                        logger.info(
                            "Image generation skipped for %s: %s",
                            content_id,
                            result.error_message,
                        )
                        return True
                    logger.error(
                        "Image generation failed for %s: %s",
                        content_id,
                        result.error_message,
                        extra={
                            "component": "image_generation",
                            "operation": "generate_image",
                            "item_id": content_id,
                        },
                    )
                    return False

        except Exception as e:
            logger.exception(
                "Image generation error for content %s: %s",
                content_id,
                e,
                extra={
                    "component": "image_generation",
                    "operation": "generate_image_task",
                    "item_id": content_id,
                },
            )
            return False

    def _process_generate_thumbnail_task(self, task_data: dict[str, Any]) -> bool:
        """Generate a screenshot-based thumbnail for news content."""
        try:
            content_id = task_data.get("content_id") or task_data.get("payload", {}).get(
                "content_id"
            )
            if not content_id:
                logger.error("No content_id provided for thumbnail generation task")
                return False

            content_id = int(content_id)
            logger.info("Generating thumbnail for content %s", content_id)

            from app.services.news_thumbnail_screenshot import (
                NewsThumbnailJob,
                generate_news_thumbnail,
            )

            result = generate_news_thumbnail(NewsThumbnailJob(content_id=content_id))

            if result.success:
                if result.error_message and "Skipped" in result.error_message:
                    logger.info(
                        "Thumbnail generation skipped for %s: %s",
                        content_id,
                        result.error_message,
                    )
                    return True
                with get_db() as db:
                    content = db.query(Content).filter(Content.id == content_id).first()
                    if not content:
                        logger.error(
                            "Content %s not found for thumbnail metadata update",
                            content_id,
                        )
                        return False
                    from app.utils.image_urls import (
                        build_news_thumbnail_url,
                        build_thumbnail_url,
                    )

                    metadata = dict(content.content_metadata or {})
                    metadata["image_generated_at"] = datetime.now(UTC).isoformat()
                    metadata["image_url"] = build_news_thumbnail_url(content_id)
                    if result.thumbnail_path:
                        metadata["thumbnail_url"] = build_thumbnail_url(content_id)
                    content.content_metadata = metadata
                    db.commit()

                logger.info(
                    "Successfully generated thumbnail for content %s at %s",
                    content_id,
                    result.image_path,
                )
                return True

            logger.error(
                "Thumbnail generation failed for %s: %s",
                content_id,
                result.error_message,
                extra={
                    "component": "thumbnail_generation",
                    "operation": "generate_thumbnail",
                    "item_id": content_id,
                },
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Thumbnail generation task failed",
                extra={
                    "component": "thumbnail_generation",
                    "operation": "generate_thumbnail_task",
                    "item_id": str(
                        task_data.get("content_id")
                        or task_data.get("payload", {}).get("content_id")
                        or "unknown"
                    ),
                    "context_data": {"error": str(exc)},
                },
            )
            return False

    def _process_discover_feeds_task(self, task_data: dict[str, Any]) -> bool:
        """Run feed/podcast/YouTube discovery for a user."""
        payload = task_data.get("payload") or {}
        user_id = payload.get("user_id")
        if not isinstance(user_id, int):
            logger.error(
                "Missing user_id in discover_feeds task",
                extra={
                    "component": "feed_discovery",
                    "operation": "task_payload",
                    "context_data": {"payload": payload},
                },
            )
            return False

        try:
            run_feed_discovery(user_id=user_id, trigger=payload.get("trigger", "cron"))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Feed discovery task failed",
                extra={
                    "component": "feed_discovery",
                    "operation": "task_run",
                    "item_id": str(user_id),
                    "context_data": {"error": str(exc)},
                },
            )
            return False

    def run(self, max_tasks: int | None = None):
        """
        Run the task processor.

        Args:
            max_tasks: Maximum number of tasks to process. None for unlimited.
        """
        logger.debug(f"Entering run method with max_tasks={max_tasks}")
        # Logging is already set up by the main script
        logger.info(f"Starting sequential task processor (worker_id: {self.worker_id})")

        # Set up signal handlers
        self._shutdown_requested = False

        def signal_handler(signum, frame):
            if not self._shutdown_requested:
                logger.info("\n🛑 Received shutdown signal (Ctrl+C) - stopping gracefully...")
                self._shutdown_requested = True
                self.running = False
            else:
                logger.warning("\n⚠️  Force shutdown requested - exiting immediately")
                sys.exit(1)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        processed_count = 0
        consecutive_empty_polls = 0
        max_empty_polls = 5  # Number of empty polls before backing off
        startup_polls = 0  # Track polls during startup phase
        startup_phase_polls = 10  # Number of aggressive polls on startup

        logger.info(
            f"Entering startup phase with {startup_phase_polls} aggressive polls (100ms intervals)"
        )

        logger.debug(f"About to enter main loop, self.running={self.running}")
        while self.running:
            try:
                # Get next task from queue
                logger.debug(f"Attempting to dequeue task (poll #{startup_polls + 1})")
                task_data = self.queue_service.dequeue(worker_id=self.worker_id)
                logger.debug(f"Dequeue result: {task_data is not None}")

                if not task_data:
                    consecutive_empty_polls += 1
                    startup_polls += 1

                    # During startup phase, poll more aggressively
                    if startup_polls <= startup_phase_polls:
                        logger.debug(
                            f"Startup phase: quick poll {startup_polls}/{startup_phase_polls}"
                        )
                        # Check for shutdown more frequently
                        for _ in range(10):  # 10 x 10ms = 100ms total
                            if not self.running:
                                break
                            time.sleep(0.01)
                    elif consecutive_empty_polls >= max_empty_polls:
                        # Back off when queue is consistently empty
                        logger.debug("Queue empty, backing off...")
                        # Check for shutdown every 100ms during long waits
                        for _ in range(50):  # 50 x 100ms = 5s total
                            if not self.running:
                                break
                            time.sleep(0.1)
                    else:
                        # Check for shutdown every 100ms
                        for _ in range(10):  # 10 x 100ms = 1s total
                            if not self.running:
                                break
                            time.sleep(0.1)
                    continue

                # Reset empty poll counter
                consecutive_empty_polls = 0

                # Mark end of startup phase on first task
                if startup_polls > 0 and startup_polls <= startup_phase_polls:
                    logger.info("Exiting startup phase - found first task")

                logger.info(f"Processing task {task_data['id']} (type: {task_data['task_type']})")

                task_id = task_data["id"]
                retry_count = task_data["retry_count"]

                # Process the task
                success, error_message = self.process_task(task_data)

                # Update task status
                self.queue_service.complete_task(
                    task_id, success=success, error_message=error_message
                )

                if success:
                    processed_count += 1
                    logger.info(
                        f"Successfully completed task {task_id} "
                        f"(total processed: {processed_count})"
                    )
                else:
                    # Retry logic
                    max_retries = getattr(self.settings, "max_retries", 3)
                    if retry_count < max_retries:
                        delay_seconds = min(60 * (2**retry_count), 3600)
                        self.queue_service.retry_task(task_id, delay_seconds=delay_seconds)
                        logger.info(
                            f"Task {task_id} scheduled for retry "
                            f"{retry_count + 1}/{max_retries} in {delay_seconds}s"
                        )
                    else:
                        logger.error(f"Task {task_id} exceeded max retries ({max_retries})")

                # Check if we've hit max tasks
                if max_tasks and processed_count >= max_tasks:
                    logger.info(f"Reached max tasks limit ({max_tasks}), stopping")
                    break

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(5)  # Wait before retrying

        logger.info(f"Processor shutting down (processed {processed_count} tasks)")

    def run_single_task(self, task_data: dict[str, Any]) -> bool:
        """
        Process a single task without the main loop.
        Useful for testing or one-off processing.
        """
        setup_logging()
        logger.info(f"Processing single task: {task_data.get('id', 'unknown')}")

        success, error_message = self.process_task(task_data)

        # Handle completion and retry logic
        task_id = task_data["id"]
        self.queue_service.complete_task(task_id, success=success, error_message=error_message)

        if not success and task_data.get("retry_count", 0) < getattr(
            self.settings, "max_retries", 3
        ):
            retry_count = task_data.get("retry_count", 0)
            delay_seconds = min(60 * (2**retry_count), 3600)
            self.queue_service.retry_task(task_id, delay_seconds=delay_seconds)
            logger.info(f"Task {task_id} scheduled for retry")

        return success


if __name__ == "__main__":
    processor = SequentialTaskProcessor()

    # Check for max tasks argument
    max_tasks = None
    if len(sys.argv) > 1:
        try:
            max_tasks = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid max_tasks argument: {sys.argv[1]}")
            sys.exit(1)

    processor.run(max_tasks=max_tasks)
