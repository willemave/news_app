from datetime import datetime

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
from app.services.llm import get_llm_service
from app.services.queue import TaskType, get_queue_service
from app.utils.error_logger import create_error_logger

logger = get_logger(__name__)
settings = get_settings()


class ContentWorker:
    """Unified worker for processing all content types."""

    def __init__(self):
        self.checkout_manager = get_checkout_manager()
        self.http_service = get_http_service()
        self.llm_service = get_llm_service()
        self.queue_service = get_queue_service()
        self.strategy_registry = get_strategy_registry()
        self.podcast_download_worker = PodcastDownloadWorker()
        self.podcast_transcribe_worker = PodcastTranscribeWorker()
        self.error_logger = create_error_logger("content_worker")

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
            extracted_data = strategy.extract_data(raw_content, processed_url)

            # Check if this is a delegation case (e.g., from PubMed)
            if extracted_data.get("next_url_to_process"):
                logger.info(f"Delegation detected. Processing next URL: {extracted_data['next_url_to_process']}")
                # Update the URL and process recursively
                content.url = extracted_data["next_url_to_process"]
                return self._process_article(content)

            # Prepare for LLM processing
            llm_data = strategy.prepare_for_llm(extracted_data)

            # Update content with extracted data
            content.title = extracted_data.get("title") or content.title
            content.metadata.update(
                {
                    "content": extracted_data.get("text_content", ""),
                    "author": extracted_data.get("author"),
                    "publication_date": extracted_data.get("publication_date"),
                    "content_type": extracted_data.get("content_type", "html"),
                    "source": extracted_data.get("source"),
                    "final_url": extracted_data.get("final_url_after_redirects", str(content.url)),
                }
            )

            # Generate structured summary using LLM service
            if llm_data.get("content_to_summarize"):
                summary = self.llm_service.summarize_content_sync(
                    content=llm_data["content_to_summarize"]
                )
                if summary:
                    content.metadata["summary"] = summary.model_dump()
                    logger.info(f"Generated summary for content {content.id}")
                else:
                    logger.warning(f"Failed to generate summary for content {content.id}")

            # Extract internal URLs for potential future crawling
            internal_urls = strategy.extract_internal_urls(
                extracted_data.get("links", []), str(content.url)
            )
            if internal_urls:
                content.metadata["internal_urls"] = internal_urls

            # Update status
            content.status = ContentStatus.COMPLETED
            content.processed_at = datetime.utcnow()

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

    def _process_podcast(self, content: ContentData) -> bool:
        """Process podcast content."""
        try:
            # Update content metadata
            if not content.metadata:
                content.metadata = {}

            # Mark as in progress
            content.status = ContentStatus.PROCESSING
            content.processed_at = datetime.utcnow()

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
