import asyncio
from typing import Optional, List, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from datetime import datetime

from app.core.settings import get_settings
from app.core.logging import get_logger
from app.core.db import get_db
from app.domain.content import ContentType, ContentData, ContentStatus
from app.domain.converters import content_to_domain, domain_to_content
from app.pipeline.checkout import get_checkout_manager
from app.services.http import get_http_service, NonRetryableError
from app.services.llm import get_llm_service
from app.services.queue import get_queue_service, TaskType, TaskStatus
from app.processing_strategies.registry import get_strategy_registry
from app.models.schema import Content, ProcessingTask
from app.pipeline.podcast_workers import PodcastDownloadWorker, PodcastTranscribeWorker
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
    
    async def process_content(self, content_id: int, worker_id: str) -> bool:
        """
        Process a single content item.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Worker {worker_id} processing content {content_id}")
        
        try:
            # Get content from database
            with get_db() as db:
                db_content = db.query(Content).filter(
                    Content.id == content_id
                ).first()
                
                if not db_content:
                    logger.error(f"Content {content_id} not found")
                    return False
                
                content = content_to_domain(db_content)
            
            # Process based on type
            if content.content_type == ContentType.ARTICLE:
                success = await self._process_article(content)
            elif content.content_type == ContentType.PODCAST:
                success = await self._process_podcast(content)
            else:
                logger.error(f"Unknown content type: {content.content_type}")
                success = False
            
            # Update database
            with get_db() as db:
                db_content = db.query(Content).filter(
                    Content.id == content_id
                ).first()
                
                if success:
                    db_content.status = ContentStatus.COMPLETED.value
                    db_content.processed_at = datetime.utcnow()
                else:
                    db_content.status = ContentStatus.FAILED.value
                    db_content.retry_count += 1
                
                db.commit()
            
            return success
            
        except Exception as e:
            self.error_logger.log_processing_error(
                item_id=content_id,
                error=e,
                operation="content_processing",
                context={"content_id": content_id, "worker_id": worker_id}
            )
            logger.error(f"Error processing content {content_id}: {e}")
            return False
    
    async def _process_article(self, content: ContentData) -> bool:
        """Process article content."""
        try:
            # Get processing strategy first (before downloading)
            strategy = self.strategy_registry.get_strategy(str(content.url))
            if not strategy:
                logger.error(f"No strategy for URL: {content.url}")
                return False
            
            # Preprocess URL if needed
            processed_url = strategy.preprocess_url(str(content.url))
            
            # Download content using HttpService
            try:
                raw_content, _ = await self.http_service.fetch_content(processed_url)
            except NonRetryableError as e:
                logger.warning(f"Non-retryable error for {processed_url}: {e}")
                # Mark as failed but don't retry
                with get_db() as db:
                    db_content = db.query(Content).filter(Content.id == content.id).first()
                    if db_content:
                        db_content.status = ContentStatus.FAILED.value
                        # Handle metadata properly
                        metadata = db_content.metadata.copy() if db_content.metadata else {}
                        metadata['error'] = str(e)
                        metadata['error_type'] = 'non_retryable'
                        db_content.metadata = metadata
                        db.commit()
                return False
            
            # Extract data using strategy
            extracted_data = strategy.extract_data(raw_content, processed_url)
            
            # Prepare for LLM processing
            llm_data = strategy.prepare_for_llm(extracted_data)
            
            # Update content with extracted data
            content.title = extracted_data.get('title') or content.title
            content.metadata.update({
                'content': extracted_data.get('text_content', ''),
                'author': extracted_data.get('author'),
                'publication_date': extracted_data.get('publication_date'),
                'content_type': extracted_data.get('content_type', 'html'),
                'final_url_after_redirects': extracted_data.get('final_url_after_redirects'),
                'word_count': len(extracted_data.get('text_content', '').split()) if extracted_data.get('text_content') else 0
            })
            
            # Summarize if we have content
            if llm_data.get('content_to_summarize'):
                summary = await self.llm_service.summarize_content(
                    llm_data['content_to_summarize']
                )
                if summary:
                    content.metadata['summary'] = summary
            
            # Save to database
            with get_db() as db:
                db_content = db.query(Content).filter(
                    Content.id == content.id
                ).first()
                
                domain_to_content(content, db_content)
                db.commit()
            
            # Extract and queue internal links for processing
            try:
                internal_links = strategy.extract_internal_urls(raw_content, processed_url)
                for link in internal_links:
                    self.queue_service.enqueue(
                        TaskType.PROCESS_CONTENT,
                        payload={'url': link, 'content_type': 'article'}
                    )
            except Exception as e:
                logger.warning(f"Failed to extract internal links: {e}")
            
            return True
            
        except NonRetryableError as e:
            logger.warning(f"Non-retryable error processing article {content.url}: {e}")
            # Mark as failed without incrementing retry count
            with get_db() as db:
                db_content = db.query(Content).filter(Content.id == content.id).first()
                if db_content:
                    db_content.status = ContentStatus.FAILED.value
                    # Handle metadata properly
                    metadata = db_content.metadata.copy() if db_content.metadata else {}
                    metadata['error'] = str(e)
                    metadata['error_type'] = 'non_retryable'
                    db_content.metadata = metadata
                    db.commit()
            return False
        except Exception as e:
            self.error_logger.log_processing_error(
                item_id=content.url,
                error=e,
                operation="article_processing",
                context={"url": str(content.url), "content_id": content.id}
            )
            logger.error(f"Error processing article {content.url}: {e}")
            return False
    
    async def _process_podcast(self, content: ContentData) -> bool:
        """Process podcast content."""
        try:
            # For podcasts, we need to:
            # 1. Download audio file
            # 2. Transcribe
            # 3. Summarize
            
            logger.info(f"Processing podcast: {content.url}")
            
            # Queue download task if not already done
            if not content.metadata.get('file_path'):
                self.queue_service.enqueue(
                    TaskType.DOWNLOAD_AUDIO,
                    content_id=content.id
                )
            elif not content.metadata.get('transcript'):
                # If already downloaded but not transcribed, queue transcribe
                self.queue_service.enqueue(
                    TaskType.TRANSCRIBE,
                    content_id=content.id
                )
            elif content.metadata.get('transcript'):
                # If already transcribed, queue summarize
                self.queue_service.enqueue(
                    TaskType.SUMMARIZE,
                    content_id=content.id
                )
            
            return True
            
        except Exception as e:
            self.error_logger.log_processing_error(
                item_id=content.url,
                error=e,
                operation="podcast_processing",
                context={"url": str(content.url), "content_id": content.id}
            )
            logger.error(f"Error processing podcast {content.url}: {e}")
            return False

class WorkerPool:
    """Manages a pool of content workers."""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or settings.max_workers
        self.checkout_manager = get_checkout_manager()
        self.worker = ContentWorker()
    
    def run_workers(
        self,
        content_type: Optional[ContentType] = None,
        max_items: Optional[int] = None
    ):
        """
        Run worker pool to process content.
        
        Args:
            content_type: Filter by content type
            max_items: Maximum items to process
        """
        logger.info(
            f"Starting worker pool with {self.max_workers} workers "
            f"for {content_type.value if content_type else 'all'} content"
        )
        
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while True:
                # Check if we've hit the limit
                if max_items and processed_count >= max_items:
                    logger.info(f"Reached max items limit ({max_items})")
                    break
                
                # Get available work
                batch_size = min(
                    self.max_workers * 2,  # Process 2x workers at a time
                    max_items - processed_count if max_items else self.max_workers * 2
                )
                
                with self.checkout_manager.checkout_content(
                    worker_id="pool",
                    content_type=content_type,
                    batch_size=batch_size
                ) as content_ids:
                    
                    if not content_ids:
                        logger.info("No more content to process")
                        break
                    
                    # Submit tasks to executor
                    futures = []
                    for i, content_id in enumerate(content_ids):
                        worker_id = f"worker-{i % self.max_workers}"
                        future = executor.submit(
                            asyncio.run,
                            self.worker.process_content(content_id, worker_id)
                        )
                        futures.append((future, content_id))
                    
                    # Wait for completion
                    for future, content_id in futures:
                        try:
                            success = future.result(timeout=settings.worker_timeout_seconds)
                            if success:
                                processed_count += 1
                                logger.info(f"Successfully processed content {content_id}")
                            else:
                                logger.error(f"Failed to process content {content_id}")
                        except Exception as e:
                            logger.error(f"Worker error for content {content_id}: {e}")
        
        logger.info(f"Worker pool finished. Processed {processed_count} items")
    
    def run_maintenance(self):
        """Run maintenance tasks."""
        logger.info("Running maintenance tasks")
        
        # Release stale checkouts
        released = self.checkout_manager.release_stale_checkouts()
        logger.info(f"Released {released} stale checkouts")
        
        # Clean up old tasks
        queue_service = get_queue_service()
        queue_service.cleanup_old_tasks(days=7)
        
        # Log statistics
        checkout_stats = self.checkout_manager.get_checkout_stats()
        queue_stats = queue_service.get_queue_stats()
        
        logger.info(f"Checkout stats: {checkout_stats}")
        logger.info(f"Queue stats: {queue_stats}")
    
    async def process_batch(self, limit: int = 10) -> int:
        """Process a batch of content items."""
        logger.info(f"Processing batch of up to {limit} items")
        
        processed_count = 0
        
        with self.checkout_manager.checkout_content(
            worker_id="api-batch",
            batch_size=limit
        ) as content_ids:
            
            if not content_ids:
                logger.info("No content to process")
                return 0
            
            # Process each item
            for content_id in content_ids:
                try:
                    success = await self.worker.process_content(content_id, "api-worker")
                    if success:
                        processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing content {content_id}: {e}")
        
        logger.info(f"Batch processing completed. Processed {processed_count} items")
        return processed_count

def get_worker() -> WorkerPool:
    """Get worker pool instance."""
    return WorkerPool()