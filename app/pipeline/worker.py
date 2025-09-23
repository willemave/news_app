import asyncio
from datetime import datetime, timezone
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
from app.services.openai_llm import get_openai_summarization_service
from app.services.http import NonRetryableError, get_http_service
from app.services.queue import TaskType, get_queue_service
from app.services.news_formatter import render_news_markdown
from app.utils.error_logger import create_error_logger

logger = get_logger(__name__)
settings = get_settings()


class ContentWorker:
    """Unified worker for processing all content types."""

    def __init__(self):
        self.checkout_manager = get_checkout_manager()
        self.http_service = get_http_service()
        self.llm_service = get_openai_summarization_service()
        self.queue_service = get_queue_service()
        self.strategy_registry = get_strategy_registry()
        self.podcast_download_worker = PodcastDownloadWorker()
        self.podcast_transcribe_worker = PodcastTranscribeWorker()
        self.error_logger = create_error_logger("content_worker")

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
            {
                key: value
                for key, value in failure_metadata.items()
                if value not in (None, "", {})
            }
        )

        content.status = ContentStatus.FAILED
        content.error_message = reason
        content.processed_at = datetime.now(timezone.utc)

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
            if content.content_type == ContentType.ARTICLE:
                success = self._process_article(content)
            elif content.content_type == ContentType.PODCAST:
                success = self._process_podcast(content)
            elif content.content_type == ContentType.NEWS:
                success = self._process_news(content)
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
            self.error_logger.log_processing_error(
                item_id=str(content_id),
                error=e,
                operation="process_content",
                context={
                    "worker_id": worker_id,
                    "content_id": content_id,
                },
            )
            logger.error(f"Error processing content {content_id}: {e}")
            return False

    def _process_article(self, content: ContentData) -> bool:
        """Process article content."""
        try:
            # Get processing strategy first (before downloading)
            strategy = self.strategy_registry.get_strategy(str(content.url))
            if not strategy:
                logger.error(f"No strategy for URL: {content.url}")
                return False

            logger.info(f"Using {strategy.__class__.__name__} for {content.url}")

            # Preprocess URL if needed
            processed_url = strategy.preprocess_url(str(content.url))

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
            if extracted_data.get("next_url_to_process"):
                logger.info(
                    f"Delegation detected. Processing next URL: {extracted_data['next_url_to_process']}"
                )
                # Update the URL and process recursively
                content.url = extracted_data["next_url_to_process"]
                return self._process_article(content)

            # Prepare for LLM processing
            # Handle async methods from strategies like YouTubeStrategy
            if asyncio.iscoroutinefunction(strategy.prepare_for_llm):
                llm_data = asyncio.run(strategy.prepare_for_llm(extracted_data)) or {}
            else:
                llm_data = strategy.prepare_for_llm(extracted_data) or {}

            # Update content with extracted data
            content.title = extracted_data.get("title") or content.title

            # Build metadata update dict
            metadata_update = {
                "content": extracted_data.get("text_content", ""),
                "author": extracted_data.get("author"),
                "publication_date": extracted_data.get("publication_date"),
                "content_type": extracted_data.get("content_type", "html"),
                "source": extracted_data.get("source"),
                "final_url": extracted_data.get("final_url_after_redirects", str(content.url)),
            }

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

            # Generate structured summary using LLM service
            if llm_data.get("content_to_summarize"):
                # Determine content type for summarization
                summarization_content_type = llm_data.get("content_type", "article")

                summary = self.llm_service.summarize_content(
                    content=llm_data["content_to_summarize"],
                    content_type=summarization_content_type,
                )
                if summary:
                    # Convert StructuredSummary to dict and store
                    summary_dict = summary.model_dump()
                    # Keep full_markdown inside the summary where it belongs
                    content.metadata["summary"] = summary_dict
                    logger.info(
                        f"Generated summary and formatted markdown for content {content.id}"
                    )
                else:
                    logger.warning(f"Failed to generate summary for content {content.id}")

            # Extract internal URLs for potential future crawling
            internal_urls = strategy.extract_internal_urls(
                extracted_data.get("links", []), str(content.url)
            )
            if internal_urls:
                content.metadata["internal_urls"] = internal_urls

            # Update publication_date from metadata
            pub_date = extracted_data.get("publication_date")
            if pub_date:
                if isinstance(pub_date, str):
                    try:
                        from dateutil import parser

                        content.publication_date = parser.parse(pub_date)
                    except Exception:
                        logger.warning(f"Could not parse publication date: {pub_date}")
                        content.publication_date = content.created_at
                elif isinstance(pub_date, datetime):
                    content.publication_date = pub_date
                else:
                    content.publication_date = content.created_at
            else:
                # Fallback to created_at if no publication date
                content.publication_date = content.created_at

            # Update status
            content.status = ContentStatus.COMPLETED
            content.processed_at = datetime.now(timezone.utc)

            logger.info(
                f"Successfully processed article {content.id} [{strategy.__class__.__name__}] "
                f"Title: {content.title[:50] if content.title else 'No title'}..."
            )

            return True

        except Exception as e:
            self.error_logger.log_processing_error(
                item_id=str(content.id),
                error=e,
                operation="process_article",
                context={
                    "url": str(content.url),
                    "content_type": content.content_type.value,
                },
            )
            logger.error(f"Error processing article {content.url}: {e}")
            return False

    def _process_news(self, content: ContentData) -> bool:
        """Process news content, generating markdown lists for aggregates."""
        try:
            news_metadata = content.to_news_metadata()
        except Exception as exc:
            logger.error(f"Invalid news metadata for content {content.id}: {exc}")
            return False

        items = news_metadata.items
        if not items:
            logger.warning(f"No news items available for content {content.id}")
            content.status = ContentStatus.SKIPPED
            content.error_message = "news content missing items"
            return False

        # Render markdown list regardless of aggregate flag for consistent display
        item_dicts = [item.model_dump(mode="json", exclude_none=True) for item in items]
        rendered_markdown = render_news_markdown(
            item_dicts,
            heading=content.title,
        )

        # Prepare excerpt for list view if missing
        excerpt = news_metadata.excerpt
        if not excerpt:
            first_item = items[0]
            if content.is_aggregate:
                excerpt = f"{len(items)} updates curated from {content.source or 'aggregate source'}"
            else:
                excerpt = first_item.summary or first_item.title

        # Update metadata dict for persistence
        metadata_dict = news_metadata.model_dump(mode="json", exclude_none=True)
        metadata_dict["items"] = item_dicts
        metadata_dict["rendered_markdown"] = rendered_markdown
        metadata_dict.setdefault("excerpt", excerpt)

        content.metadata = metadata_dict
        content.status = ContentStatus.COMPLETED
        content.processed_at = datetime.utcnow()
        return True

    def _process_podcast(self, content: ContentData) -> bool:
        """Process podcast content."""
        try:
            # Update content metadata
            if not content.metadata:
                content.metadata = {}

            # Mark as in progress
            content.status = ContentStatus.PROCESSING
            content.processed_at = datetime.now(timezone.utc)

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
            self.error_logger.log_processing_error(
                item_id=str(content.id),
                error=e,
                operation="process_podcast",
                context={
                    "url": str(content.url),
                    "content_type": content.content_type.value,
                },
            )
            logger.error(f"Error processing podcast {content.url}: {e}")
            return False
