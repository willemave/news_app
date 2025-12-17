import asyncio
from datetime import UTC, datetime
from typing import Any

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.domain.converters import content_to_domain, domain_to_content
from app.models.metadata import ContentData, ContentStatus, ContentType
from app.models.schema import Content
from app.pipeline.checkout import get_checkout_manager
from app.pipeline.podcast_workers import PodcastDownloadWorker, PodcastTranscribeWorker
from app.processing_strategies.registry import get_strategy_registry
from app.services.http import NonRetryableError, get_http_service
from app.services.llm_summarization import ContentSummarizer, get_content_summarizer
from app.services.queue import TaskType, get_queue_service
from app.utils.dates import parse_date_with_tz

logger = get_logger(__name__)
settings = get_settings()


def get_llm_service() -> ContentSummarizer:
    """Return the shared summarization service."""
    return get_content_summarizer()


class ContentWorker:
    """Unified worker for processing all content types."""

    def __init__(self):
        self.checkout_manager = get_checkout_manager()
        self.http_service = get_http_service()
        self.queue_service = get_queue_service()
        self.strategy_registry = get_strategy_registry()
        self.podcast_download_worker = PodcastDownloadWorker()
        self.podcast_transcribe_worker = PodcastTranscribeWorker()

    def _mark_article_extraction_failure(
        self,
        content: ContentData,
        extracted_data: dict[str, Any],
        reason: str,
        fallback_text: str | None,
    ) -> None:
        """Update content metadata and status when extraction fails."""
        logger.warning(
            "Marking content %s as failed due to extraction error: %s",
            content.id,
            reason,
        )

        failure_metadata = {
            "extraction_failed": True,
            "extraction_error": reason,
            "extraction_failure_details": fallback_text.strip() if fallback_text else None,
            "content_type": extracted_data.get("content_type", "html"),
            "source": extracted_data.get("source"),
            "final_url_after_redirects": extracted_data.get(
                "final_url_after_redirects", str(content.url)
            ),
            "author": extracted_data.get("author"),
            "publication_date": extracted_data.get("publication_date"),
        }

        # Remove summary/content snapshots so the UI does not render a success state.
        content.metadata.pop("summary", None)
        if "content" in content.metadata:
            content.metadata["content"] = None

        # Merge metadata while omitting empty values.
        content.metadata.update(
            {key: value for key, value in failure_metadata.items() if value not in (None, "", {})}
        )

        content.status = ContentStatus.FAILED
        content.error_message = reason
        content.processed_at = datetime.now(UTC)

    def process_content(self, content_id: int, worker_id: str) -> bool:
        """
        Process a single content item.

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Worker {worker_id} processing content {content_id}")

        try:
            # Get content from database
            with get_db() as db:
                db_content = db.query(Content).filter(Content.id == content_id).first()

                if not db_content:
                    logger.error(f"Content {content_id} not found")
                    return False

                content = content_to_domain(db_content)

            # Process based on type
            if content.content_type in {ContentType.ARTICLE, ContentType.NEWS}:
                success = self._process_article(content)
            elif content.content_type == ContentType.PODCAST:
                success = self._process_podcast(content)
            else:
                logger.error(f"Unknown content type: {content.content_type}")
                success = False

            # Update database
            if success:
                with get_db() as db:
                    db_content = db.query(Content).filter(Content.id == content_id).first()
                    if db_content:
                        domain_to_content(content, db_content)
                        db.commit()

            return success

        except Exception as e:
            logger.exception(
                "Error processing content %s: %s",
                content_id,
                e,
                extra={
                    "component": "content_worker",
                    "operation": "process_content",
                    "item_id": str(content_id),
                    "context_data": {"worker_id": worker_id, "content_id": content_id},
                },
            )
            return False

    def _process_article(self, content: ContentData) -> bool:
        """Process article content."""
        try:
            target_url = self._resolve_article_url(content)

            # Get processing strategy first (before downloading)
            strategy = self.strategy_registry.get_strategy(target_url)
            if not strategy:
                logger.error(f"No strategy for URL: {target_url}")
                return False

            logger.info(f"Using {strategy.__class__.__name__} for {target_url}")

            # Preprocess URL if needed
            processed_url = strategy.preprocess_url(target_url)

            # Download content using strategy (HTML strategy uses crawl4ai)
            try:
                # Handle async methods from YouTubeStrategy
                if asyncio.iscoroutinefunction(strategy.download_content):
                    raw_content = asyncio.run(strategy.download_content(processed_url))
                else:
                    raw_content = strategy.download_content(processed_url)
            except NonRetryableError as e:
                logger.warning(f"Non-retryable error for {processed_url}: {e}")
                # Mark as failed but don't retry
                with get_db() as db:
                    db_content = db.query(Content).filter(Content.id == content.id).first()
                    if db_content:
                        db_content.status = ContentStatus.FAILED.value
                        # Handle metadata properly
                        metadata = (
                            dict(db_content.content_metadata) if db_content.content_metadata else {}
                        )
                        metadata["error"] = str(e)
                        metadata["error_type"] = "non_retryable"
                        db_content.metadata = metadata
                        db.commit()
                return False

            # Extract data using strategy
            # Handle async methods from YouTubeStrategy
            if asyncio.iscoroutinefunction(strategy.extract_data):
                extracted_data = asyncio.run(strategy.extract_data(raw_content, processed_url))
            else:
                extracted_data = strategy.extract_data(raw_content, processed_url)

            # Check if this is a delegation case (e.g., from PubMed)
            delegated_url = extracted_data.get("next_url_to_process")
            if delegated_url:
                logger.info("Delegation detected. Processing next URL: %s", delegated_url)
                # Update the URL and process recursively
                content.url = delegated_url
                return self._process_article(content)

            # Prepare for LLM processing
            # Handle async methods from strategies like YouTubeStrategy
            if asyncio.iscoroutinefunction(strategy.prepare_for_llm):
                llm_data = asyncio.run(strategy.prepare_for_llm(extracted_data)) or {}
            else:
                llm_data = strategy.prepare_for_llm(extracted_data) or {}

            # Check if strategy marked this content to be skipped (e.g., images, YouTube auth)
            if extracted_data.get("skip_processing") or llm_data.get("skip_processing"):
                skip_reason = (
                    extracted_data.get("skip_reason")
                    or llm_data.get("skip_reason")
                    or "marked by strategy"
                )
                logger.info(
                    f"Skipping processing for content {content.id}: {skip_reason} "
                    f"({strategy.__class__.__name__})"
                )
                content.status = ContentStatus.SKIPPED
                content.processed_at = datetime.now(UTC)
                # Store minimal metadata
                content.metadata["content_type"] = extracted_data.get("content_type", "unknown")
                content.metadata["image_url"] = extracted_data.get("image_url")
                content.metadata["final_url"] = extracted_data.get("final_url_after_redirects")
                if extracted_data.get("title"):
                    content.title = extracted_data.get("title")
                return True

            # Update content with extracted data
            content.title = extracted_data.get("title") or content.title

            # Build metadata update dict
            final_url = extracted_data.get("final_url_after_redirects") or processed_url
            final_url = str(final_url)

            existing_metadata = content.metadata or {}

            metadata_update = {
                "content": extracted_data.get("text_content", ""),
                "author": extracted_data.get("author"),
                "publication_date": extracted_data.get("publication_date"),
                "content_type": extracted_data.get("content_type", "html"),
                "source": existing_metadata.get("source"),  # Never overwrite source from scraper
                "final_url": final_url,
            }

            original_url = str(content.url)
            if content.content_type == ContentType.NEWS and original_url != final_url:
                metadata_update.setdefault("news_original_url", original_url)

            if content.content_type == ContentType.NEWS:
                article_info = existing_metadata.get("article", {}).copy()
                article_info.setdefault("url", final_url)
                if extracted_data.get("title"):
                    article_info["title"] = extracted_data.get("title")
                if metadata_update.get("source"):
                    article_info["source_domain"] = metadata_update.get("source")
                metadata_update["article"] = article_info

            # Do not override platform here; platform should reflect the scraper.

            # Add HackerNews-specific metadata if present
            hn_fields = [
                "hn_score",
                "hn_comments_count",
                "hn_submitter",
                "hn_discussion_url",
                "hn_item_type",
                "hn_linked_url",
                "is_hn_text_post",
            ]
            for field in hn_fields:
                if field in extracted_data:
                    metadata_update[field] = extracted_data[field]

            content.metadata.update(metadata_update)

            extraction_error = extracted_data.get("extraction_error")
            llm_content = llm_data.get("content_to_summarize")
            llm_content_text = llm_content.strip() if isinstance(llm_content, str) else ""
            text_content = (extracted_data.get("text_content") or "").strip()

            failure_reason: str | None = None
            if extraction_error:
                failure_reason = extraction_error
            elif not llm_content_text:
                failure_reason = "extracted article contained no content to summarize"
            elif llm_content_text.lower().startswith("failed to extract content"):
                failure_reason = llm_content_text
            elif text_content.lower().startswith("failed to extract content"):
                failure_reason = text_content

            if failure_reason:
                self._mark_article_extraction_failure(
                    content,
                    extracted_data,
                    failure_reason,
                    llm_content_text or text_content,
                )
                return True

            # Store content_to_summarize in metadata for the SUMMARIZE task
            if llm_data.get("content_to_summarize"):
                # Content is already stored in metadata["content"] from extraction
                # Enqueue SUMMARIZE task to handle summarization asynchronously
                self.queue_service.enqueue(TaskType.SUMMARIZE, content_id=content.id)
                logger.info(
                    "Enqueued SUMMARIZE task for content %s (%s)",
                    content.id,
                    content.content_type.value,
                )
            else:
                logger.error(
                    "No LLM payload generated for content %s; keys=%s",
                    content.id,
                    sorted(llm_data.keys()),
                )

            # Extract internal URLs for potential future crawling
            internal_urls = strategy.extract_internal_urls(
                extracted_data.get("links", []), final_url
            )
            if internal_urls:
                content.metadata["internal_urls"] = internal_urls

            # Update publication_date from metadata
            pub_date = extracted_data.get("publication_date")
            if pub_date:
                parsed_pub_date = parse_date_with_tz(pub_date)
                if parsed_pub_date:
                    content.publication_date = parsed_pub_date
                else:
                    logger.warning("Could not parse publication date: %s", pub_date)
                    content.publication_date = content.created_at
            else:
                # Fallback to created_at if no publication date
                content.publication_date = content.created_at

            # Update status - keep as PROCESSING, SUMMARIZE task will set COMPLETED
            content.status = ContentStatus.PROCESSING
            content.processed_at = datetime.now(UTC)

            logger.info(
                "Extracted article %s [%s], awaiting summarization. Title: %s...",
                content.id,
                strategy.__class__.__name__,
                content.title[:50] if content.title else "No title",
            )

            return True

        except Exception as e:
            logger.exception(
                "Error processing article %s: %s",
                content.url,
                e,
                extra={
                    "component": "content_worker",
                    "operation": "process_article",
                    "item_id": str(content.id),
                    "context_data": {
                        "url": str(content.url),
                        "content_type": content.content_type.value,
                    },
                },
            )
            return False

    def _resolve_article_url(self, content: ContentData) -> str:
        """Select the best URL to fetch when processing an article/news item."""

        base_url = str(content.url)

        if content.content_type != ContentType.NEWS:
            return base_url

        metadata = content.metadata or {}
        platform = (metadata.get("platform") or content.platform or "").lower()

        candidate_urls: list[str | None] = []

        article_info = metadata.get("article", {})
        candidate_urls.append(article_info.get("url"))

        if platform == "hackernews":
            aggregator_meta = metadata.get("aggregator", {})
            candidate_urls.append(aggregator_meta.get("metadata", {}).get("hn_linked_url"))

        candidate_urls.extend(
            [
                metadata.get("primary_article_url"),
                metadata.get("primary_url"),
                metadata.get("url"),
            ]
        )

        for candidate in candidate_urls:
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                return self._normalize_target_url(candidate)

        return base_url

    @staticmethod
    def _normalize_target_url(url: str) -> str:
        normalized = url.strip()
        if normalized.startswith("http://"):
            normalized = "https://" + normalized[len("http://") :]
        return normalized

    def _process_podcast(self, content: ContentData) -> bool:
        """Process podcast content."""
        try:
            # Update content metadata
            if not content.metadata:
                content.metadata = {}

            # Mark as in progress
            content.status = ContentStatus.PROCESSING
            content.processed_at = datetime.now(UTC)

            # Save initial state to DB
            with get_db() as db:
                db_content = db.query(Content).filter(Content.id == content.id).first()
                if db_content:
                    domain_to_content(content, db_content)
                    db.commit()

            # Queue download task
            self.queue_service.enqueue(TaskType.DOWNLOAD_AUDIO, content_id=content.id)

            logger.info(f"Queued download task for podcast {content.url}")

            return True

        except Exception as e:
            logger.exception(
                "Error processing podcast %s: %s",
                content.url,
                e,
                extra={
                    "component": "content_worker",
                    "operation": "process_podcast",
                    "item_id": str(content.id),
                    "context_data": {
                        "url": str(content.url),
                        "content_type": content.content_type.value,
                    },
                },
            )
            return False

    def _process_podcast_sync(self, content: ContentData) -> bool:
        """Compatibility shim used by legacy tests."""

        return self._process_podcast(content)
