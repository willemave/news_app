import asyncio
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.core.settings import get_settings
from app.core.logging import get_logger
from app.core.db import get_db
from app.models.schema import Content, ProcessingTask
from app.services.queue import get_queue_service, TaskType, TaskStatus
from app.services.llm import get_llm_service
from app.pipeline.podcast_workers import PodcastDownloadWorker, PodcastTranscribeWorker
from app.domain.converters import content_to_domain
from app.scraping.runner import ScraperRunner
from app.pipeline.worker import ContentWorker
from app.utils.error_logger import create_error_logger

logger = get_logger(__name__)
settings = get_settings()


class TaskProcessor:
    """Processes tasks from the queue."""
    
    def __init__(self):
        self.queue_service = get_queue_service()
        self.llm_service = get_llm_service()
        self.podcast_download_worker = PodcastDownloadWorker()
        self.podcast_transcribe_worker = PodcastTranscribeWorker()
        self.scraper_runner = ScraperRunner()
        self.content_worker = ContentWorker()
        self.error_logger = create_error_logger("task_processor")
    
    async def process_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Process a single task based on its type.
        
        Args:
            task_data: Dictionary containing task information
        
        Returns:
            True if successful, False otherwise
        """
        task_id = task_data['id']
        task_type = task_data['task_type']
        content_id = task_data.get('content_id')
        payload = task_data.get('payload', {})
        
        logger.info(f"Processing task {task_id} of type {task_type}")
        
        try:
            if task_type == TaskType.SCRAPE.value:
                return await self._process_scrape_task(payload)
            
            elif task_type == TaskType.PROCESS_CONTENT.value:
                return await self._process_content_task(content_id)
            
            elif task_type == TaskType.DOWNLOAD_AUDIO.value:
                return await self.podcast_download_worker.process_download_task(content_id)
            
            elif task_type == TaskType.TRANSCRIBE.value:
                return await self.podcast_transcribe_worker.process_transcribe_task(content_id)
            
            elif task_type == TaskType.SUMMARIZE.value:
                return await self._process_summarize_task(content_id)
            
            else:
                logger.error(f"Unknown task type: {task_type}")
                return False
                
        except Exception as e:
            self.error_logger.log_processing_error(
                item_id=task_id,
                error=e,
                operation="task_processing",
                context={
                    "task_type": task_type,
                    "content_id": content_id,
                    "payload": payload
                }
            )
            logger.error(f"Error processing task {task_id}: {e}")
            return False
    
    async def _process_summarize_task(self, content_id: int) -> bool:
        """
        Summarize content (works for both articles and podcasts).
        
        Args:
            content_id: ID of the content to summarize
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Processing summarize task for content {content_id}")
        
        try:
            with get_db() as db:
                # Get content
                db_content = db.query(Content).filter(
                    Content.id == content_id
                ).first()
                
                if not db_content:
                    logger.error(f"Content {content_id} not found")
                    return False
                
                content = content_to_domain(db_content)
                
                # Get content to summarize
                content_to_summarize = None
                
                if content.content_type == "article":
                    # For articles, get the text content
                    content_to_summarize = content.metadata.get('content', '')
                elif content.content_type == "podcast":
                    # For podcasts, get the transcript
                    content_to_summarize = content.metadata.get('transcript', '')
                
                if not content_to_summarize:
                    logger.error(f"No content to summarize for {content_id}")
                    db_content.status = "failed"
                    db_content.error_message = "No content to summarize"
                    db.commit()
                    return False
                
                # Use LLM to generate summary
                summary = await self.llm_service.summarize_content(content_to_summarize)
                
                if summary:
                    # Re-fetch the content object to ensure it's attached to the session
                    db_content_to_update = db.query(Content).filter(
                        Content.id == content_id
                    ).first()
                    
                    if not db_content_to_update.content_metadata:
                        db_content_to_update.content_metadata = {}
                    
                    # Create a mutable copy to update
                    new_metadata = dict(db_content_to_update.content_metadata)
                    new_metadata['summary'] = summary
                    new_metadata['summarization_date'] = datetime.now(timezone.utc).isoformat()
                    
                    db_content_to_update.content_metadata = new_metadata
                    db_content_to_update.status = "completed"
                    db_content_to_update.processed_at = datetime.now(timezone.utc)
                    db.commit()
                    
                    logger.info(f"Successfully summarized content {content_id}")
                    return True
                else:
                    logger.error(f"Failed to generate summary for content {content_id}")
                    db_content.status = "failed"
                    db_content.error_message = "Failed to generate summary"
                    db.commit()
                    return False
                    
        except Exception as e:
            self.error_logger.log_processing_error(
                item_id=content_id,
                error=e,
                operation="content_summarization",
                context={"content_id": content_id}
            )
            logger.error(f"Error summarizing content {content_id}: {e}")
            
            # Update content with error
            try:
                with get_db() as db:
                    db_content = db.query(Content).filter(
                        Content.id == content_id
                    ).first()
                    if db_content:
                        db_content.status = "failed"
                        db_content.error_message = str(e)
                        db_content.retry_count += 1
                        db.commit()
            except:
                pass
            
            return False
    
    async def _process_scrape_task(self, payload: dict) -> bool:
        """
        Process a scrape task by running the specified scraper.
        
        Args:
            payload: Task payload containing scraper_name
            
        Returns:
            True if successful, False otherwise
        """
        scraper_name = payload.get('scraper_name')
        if not scraper_name:
            logger.error("No scraper_name in payload")
            return False
        
        logger.info(f"Processing scrape task for {scraper_name}")
        
        try:
            # Run the scraper
            count = await self.scraper_runner.run_scraper(scraper_name)
            
            if count is not None and count >= 0:
                logger.info(f"Scraper {scraper_name} found {count} new items")
                # Items are already saved and PROCESS_CONTENT tasks are queued by the scraper
                return True
            else:
                logger.error(f"Scraper {scraper_name} failed")
                return False
                
        except Exception as e:
            self.error_logger.log_processing_error(
                item_id=scraper_name,
                error=e,
                operation="scraper_execution",
                context={"scraper_name": scraper_name}
            )
            logger.error(f"Error running scraper {scraper_name}: {e}")
            return False
    
    async def _process_content_task(self, content_id: int) -> bool:
        """
        Process content using the ContentWorker.
        
        Args:
            content_id: ID of the content to process
            
        Returns:
            True if successful, False otherwise
        """
        if not content_id:
            logger.error("No content_id provided for PROCESS_CONTENT task")
            return False
        
        logger.info(f"Processing content task for content {content_id}")
        
        try:
            # Use ContentWorker to process the content
            success = await self.content_worker.process_content(
                content_id,
                f"task-processor-{content_id}"
            )
            return success
            
        except Exception as e:
            self.error_logger.log_processing_error(
                item_id=content_id,
                error=e,
                operation="content_processing",
                context={"content_id": content_id}
            )
            logger.error(f"Error processing content {content_id}: {e}")
            return False
    
    def run_worker(self, worker_id: str, max_tasks: Optional[int] = None):
        """
        Run a worker that processes tasks from the queue.
        
        Args:
            worker_id: Unique identifier for this worker
            max_tasks: Maximum number of tasks to process (None for unlimited)
        """
        logger.info(f"Starting task worker {worker_id}")
        
        processed_count = 0
        
        while True:
            # Check if we've hit the limit
            if max_tasks and processed_count >= max_tasks:
                logger.info(f"Worker {worker_id} reached max tasks limit ({max_tasks})")
                break
            
            # Get next task from queue
            task_data = self.queue_service.dequeue(worker_id=worker_id)
            
            if not task_data:
                logger.debug(f"No tasks available for worker {worker_id}")
                break
            
            task_id = task_data['id']
            retry_count = task_data['retry_count']
            
            try:
                # Process the task - asyncio.run() is safe here because
                # each thread in the ThreadPoolExecutor gets its own event loop
                success = asyncio.run(self.process_task(task_data))
                
                # Update task status
                self.queue_service.complete_task(task_id, success=success)
                
                if success:
                    processed_count += 1
                    logger.info(f"Worker {worker_id} successfully processed task {task_id}")
                else:
                    # Retry logic with exponential backoff
                    max_retries = getattr(settings, 'max_retries', 3)
                    if retry_count < max_retries:
                        # Use exponential backoff: 2^retry_count * 60 seconds
                        delay_seconds = min(60 * (2 ** retry_count), 3600)  # Cap at 1 hour
                        self.queue_service.retry_task(task_id, delay_seconds=delay_seconds)
                        logger.info(f"Task {task_id} scheduled for retry {retry_count + 1}/{max_retries} in {delay_seconds}s")
                    else:
                        logger.error(f"Task {task_id} exceeded max retries ({max_retries})")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Worker {worker_id} error processing task {task_id}: {error_msg}", exc_info=True)
                
                # Check if it's a network/DNS error that should be retried
                is_network_error = any(term in error_msg.lower() for term in [
                    'nodename nor servname provided',
                    'name or service not known',
                    'temporary failure in name resolution',
                    'connection error',
                    'timeout',
                    'dns'
                ])
                
                if is_network_error:
                    max_retries = getattr(settings, 'max_retries', 3)
                    if retry_count < max_retries:
                        delay_seconds = min(120 * (2 ** retry_count), 7200)  # Longer delays for network issues
                        self.queue_service.retry_task(task_id, delay_seconds=delay_seconds)
                        logger.info(f"Network error for task {task_id}, scheduling retry {retry_count + 1}/{max_retries} in {delay_seconds}s")
                    else:
                        logger.error(f"Task {task_id} exceeded max retries due to persistent network issues")
                        self.queue_service.complete_task(task_id, success=False, error_message=error_msg[:500])
                else:
                    # Non-network errors don't get retried automatically
                    self.queue_service.complete_task(task_id, success=False, error_message=error_msg[:500])
        
        logger.info(f"Worker {worker_id} finished. Processed {processed_count} tasks")
        
        # Cleanup models if needed
        if hasattr(self.podcast_transcribe_worker, 'cleanup_model'):
            self.podcast_transcribe_worker.cleanup_model()


class TaskProcessorPool:
    """Manages a pool of task processors."""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or settings.max_workers
    
    def run_pool(self, max_tasks_per_worker: Optional[int] = None):
        """
        Run a pool of workers to process tasks.
        
        Args:
            max_tasks_per_worker: Maximum tasks each worker should process
        """
        logger.info(f"Starting task processor pool with {self.max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            for i in range(self.max_workers):
                worker_id = f"task-worker-{i}"
                processor = TaskProcessor()
                
                future = executor.submit(
                    processor.run_worker,
                    worker_id,
                    max_tasks_per_worker
                )
                futures.append(future)
            
            # Wait for all workers to complete
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Worker pool error: {e}")
        
        logger.info("Task processor pool finished")
    
    def run_continuous(self, check_interval_seconds: int = 30):
        """
        Run workers continuously, checking for new tasks at intervals.
        
        Args:
            check_interval_seconds: How often to check for new tasks
        """
        logger.info("Starting continuous task processing")
        
        while True:
            # Check if there are pending tasks
            stats = get_queue_service().get_queue_stats()
            pending_count = stats.get('by_status', {}).get(TaskStatus.PENDING.value, 0)
            
            if pending_count > 0:
                logger.info(f"Found {pending_count} pending tasks, starting workers")
                self.run_pool()
            else:
                logger.debug("No pending tasks")
            
            # Wait before checking again
            logger.debug(f"Sleeping for {check_interval_seconds} seconds")
            asyncio.run(asyncio.sleep(check_interval_seconds))