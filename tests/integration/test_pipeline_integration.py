"""Integration tests for the complete processing pipeline."""

import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from app.pipeline.sequential_task_processor import SequentialTaskProcessor
from app.services.queue import TaskType, QueueService
from app.models.schema import Content, ProcessingTask
from app.models.metadata import ContentStatus, ContentType
from app.core.db import get_db


@pytest.fixture
def setup_test_db():
    """Setup test database with sample content."""
    with get_db() as db:
        # Clear existing test data
        db.query(ProcessingTask).delete()
        db.query(Content).delete()
        db.commit()
        
        # Add test content
        test_contents = [
            Content(
                id=1,
                url="https://example.com/article1",
                title="Test Article 1",
                content_type=ContentType.ARTICLE.value,
                status=ContentStatus.NEW.value,
                source_feed="test",
                created_at=datetime.utcnow(),
                metadata={},
            ),
            Content(
                id=2,
                url="https://example.com/podcast1.mp3",
                title="Test Podcast 1",
                content_type=ContentType.PODCAST.value,
                status=ContentStatus.NEW.value,
                source_feed="test",
                created_at=datetime.utcnow(),
                metadata={"audio_url": "https://example.com/podcast1.mp3"},
            ),
            Content(
                id=3,
                url="https://failing-site.com/article",
                title="Failing Article",
                content_type=ContentType.ARTICLE.value,
                status=ContentStatus.NEW.value,
                source_feed="test",
                created_at=datetime.utcnow(),
                metadata={},
            ),
        ]
        
        for content in test_contents:
            db.add(content)
        db.commit()
        
        yield db
        
        # Cleanup
        db.query(ProcessingTask).delete()
        db.query(Content).delete()
        db.commit()


class TestPipelineIntegration:
    """Integration tests for the complete pipeline."""
    
    @pytest.mark.integration
    def test_full_article_processing_pipeline(self, setup_test_db):
        """Test complete article processing from task creation to completion."""
        # Create processing task
        queue_service = QueueService()
        task_id = queue_service.enqueue(
            task_type=TaskType.PROCESS_CONTENT,
            content_id=1
        )
        
        assert task_id is not None
        
        # Mock external services
        with patch("app.pipeline.worker.get_http_service") as mock_http_service, \
             patch("app.pipeline.worker.get_llm_service") as mock_llm_service, \
             patch("app.pipeline.worker.get_strategy_registry") as mock_registry:
            
            # Setup mocks
            mock_http = Mock()
            mock_http.fetch_content_sync.return_value = (
                "<html><body>Test article content</body></html>",
                {"content-type": "text/html"}
            )
            mock_http_service.return_value = mock_http
            
            mock_llm = Mock()
            mock_summary = Mock()
            mock_summary.model_dump.return_value = {"summary": "Test summary"}
            mock_llm.summarize_content_sync.return_value = mock_summary
            mock_llm_service.return_value = mock_llm
            
            mock_strategy = Mock()
            mock_strategy.preprocess_url.return_value = "https://example.com/article1"
            mock_strategy.extract_data.return_value = {
                "title": "Test Article 1",
                "text_content": "Test article content",
                "author": None,
                "publication_date": None,
                "content_type": "html",
                "final_url_after_redirects": "https://example.com/article1",
            }
            mock_strategy.prepare_for_llm.return_value = {
                "content_to_summarize": "Test article content"
            }
            mock_strategy.extract_internal_urls.return_value = []
            
            mock_registry_instance = Mock()
            mock_registry_instance.get_strategy.return_value = mock_strategy
            mock_registry.return_value = mock_registry_instance
            
            # Process with sequential processor
            processor = SequentialTaskProcessor()
            
            # Process single task
            task = queue_service.dequeue(worker_id="test-worker")
            if task:
                processor.process_task(task)
                queue_service.complete_task(task["id"], success=True)
            
            # Verify content was processed
            with setup_test_db as db:
                content = db.query(Content).filter(Content.id == 1).first()
                assert content.status == ContentStatus.COMPLETED.value
                assert content.processed_at is not None
                assert content.metadata.get("summary") == {"summary": "Test summary"}
                assert content.metadata.get("content") == "Test article content"
    
    @pytest.mark.integration
    def test_failed_task_retry_mechanism(self, setup_test_db):
        """Test task retry mechanism for failed tasks."""
        queue_service = QueueService()
        
        # Create task for content that will fail
        task_id = queue_service.enqueue(
            task_type=TaskType.PROCESS_CONTENT,
            content_id=3  # Failing article
        )
        
        with patch("app.pipeline.worker.get_http_service") as mock_http_service, \
             patch("app.pipeline.worker.get_strategy_registry") as mock_registry:
            
            # Setup to fail
            mock_http = Mock()
            mock_http.fetch_content_sync.side_effect = Exception("Network error")
            mock_http_service.return_value = mock_http
            
            mock_strategy = Mock()
            mock_strategy.preprocess_url.return_value = "https://failing-site.com/article"
            
            mock_registry_instance = Mock()
            mock_registry_instance.get_strategy.return_value = mock_strategy
            mock_registry.return_value = mock_registry_instance
            
            processor = SequentialTaskProcessor()
            
            # Process the failing task
            task = queue_service.dequeue(worker_id="test-worker")
            assert task is not None
            
            result = processor.process_task(task)
            assert result is False
            
            # Check task was marked for retry
            queue_service.complete_task(task["id"], success=False)
            
            # Should be able to retry
            queue_service.retry_task(task["id"], delay_seconds=0)
            
            # Check retry count increased
            with setup_test_db as db:
                updated_task = db.query(ProcessingTask).filter(
                    ProcessingTask.id == task["id"]
                ).first()
                assert updated_task.retry_count == 1
                assert updated_task.status == "pending"
    
    @pytest.mark.integration
    def test_concurrent_processing(self, setup_test_db):
        """Test concurrent processing with multiple workers."""
        queue_service = QueueService()
        
        # Create multiple tasks
        task_ids = []
        for content_id in [1, 2]:
            task_id = queue_service.enqueue(
                task_type=TaskType.PROCESS_CONTENT,
                content_id=content_id
            )
            task_ids.append(task_id)
        
        processed_contents = []
        
        # Mock services
        with patch("app.pipeline.worker.get_http_service") as mock_http_service, \
             patch("app.pipeline.worker.get_llm_service") as mock_llm_service, \
             patch("app.pipeline.worker.get_strategy_registry") as mock_registry, \
             patch("app.pipeline.worker.PodcastDownloadWorker") as mock_download, \
             patch("app.pipeline.worker.PodcastTranscribeWorker") as mock_transcribe:
            
            # Setup mocks for both content types
            mock_http = Mock()
            mock_http.fetch_content_sync.return_value = (
                "<html><body>Content</body></html>",
                {"content-type": "text/html"}
            )
            mock_http_service.return_value = mock_http
            
            mock_llm = Mock()
            mock_summary = Mock()
            mock_summary.model_dump.return_value = {"summary": "Summary"}
            mock_llm.summarize_content_sync.return_value = mock_summary
            mock_llm_service.return_value = mock_llm
            
            # Article strategy
            mock_strategy = Mock()
            mock_strategy.preprocess_url.return_value = "https://example.com/article1"
            mock_strategy.extract_data.return_value = {
                "title": "Article",
                "text_content": "Content",
                "author": None,
                "publication_date": None,
                "content_type": "html",
                "final_url_after_redirects": "https://example.com/article1",
            }
            mock_strategy.prepare_for_llm.return_value = {
                "content_to_summarize": "Content"
            }
            mock_strategy.extract_internal_urls.return_value = []
            
            mock_registry_instance = Mock()
            mock_registry_instance.get_strategy.return_value = mock_strategy
            mock_registry.return_value = mock_registry_instance
            
            # Podcast workers
            mock_download_worker = Mock()
            mock_download_worker.process_download_task_sync.return_value = True
            mock_download.return_value = mock_download_worker
            
            mock_transcribe_worker = Mock()
            mock_transcribe_worker.process_transcribe_task_sync.return_value = True
            mock_transcribe.return_value = mock_transcribe_worker
            
            # Track processed content
            def track_processing(content_id, worker_id):
                processed_contents.append((content_id, worker_id))
                return True
            
            # Process tasks with multiple workers
            processor = SequentialTaskProcessor()
            
            # Simulate two workers processing in parallel
            worker1_task = queue_service.dequeue(worker_id="worker-1")
            worker2_task = queue_service.dequeue(worker_id="worker-2")
            
            if worker1_task:
                processor.process_task(worker1_task)
                queue_service.complete_task(worker1_task["id"], success=True)
            
            if worker2_task:
                processor.process_task(worker2_task)
                queue_service.complete_task(worker2_task["id"], success=True)
            
            # Verify both tasks were processed
            with setup_test_db as db:
                completed_tasks = db.query(ProcessingTask).filter(
                    ProcessingTask.status == "completed"
                ).all()
                assert len(completed_tasks) == 2
    
    @pytest.mark.integration
    def test_pipeline_error_recovery(self, setup_test_db):
        """Test pipeline recovery from various error conditions."""
        queue_service = QueueService()
        
        # Test handling of invalid content ID
        invalid_task_id = queue_service.enqueue(
            task_type=TaskType.PROCESS_CONTENT,
            content_id=9999  # Non-existent
        )
        
        processor = SequentialTaskProcessor()
        task = queue_service.dequeue(worker_id="test-worker")
        
        result = processor.process_task(task)
        assert result is False
        
        # Test handling of invalid task type
        with setup_test_db as db:
            invalid_task = ProcessingTask(
                task_type="INVALID_TYPE",
                payload={"content_id": 1},
                status="pending",
                created_at=datetime.utcnow(),
                retry_count=0,
            )
            db.add(invalid_task)
            db.commit()
            
            task_data = {
                "id": invalid_task.id,
                "task_type": "INVALID_TYPE",
                "payload": invalid_task.payload,
                "retry_count": 0,
            }
            
            result = processor.process_task(task_data)
            assert result is False
    
    @pytest.mark.integration
    def test_end_to_end_scraping_and_processing(self, setup_test_db):
        """Test complete flow from scraping to processing."""
        queue_service = QueueService()
        
        # Create scrape task
        scrape_task_id = queue_service.enqueue(
            task_type=TaskType.SCRAPE,
            payload={"sources": ["test"]}
        )
        
        with patch("app.pipeline.sequential_task_processor.ScraperRunner") as mock_runner:
            # Mock scraper to create new content
            def mock_scrape(source):
                with get_db() as db:
                    new_content = Content(
                        url=f"https://scraped.com/{source}/article",
                        title=f"Scraped from {source}",
                        content_type=ContentType.ARTICLE.value,
                        status=ContentStatus.NEW.value,
                        source_feed=source,
                        created_at=datetime.utcnow(),
                        metadata={},
                    )
                    db.add(new_content)
                    db.commit()
                    
                    # Create processing task for new content
                    queue_service.enqueue(
                        task_type=TaskType.PROCESS_CONTENT,
                        content_id=new_content.id
                    )
                return 1
            
            mock_runner_instance = Mock()
            mock_runner_instance.run_scraper_sync.side_effect = mock_scrape
            mock_runner.return_value = mock_runner_instance
            
            processor = SequentialTaskProcessor()
            
            # Process scrape task
            scrape_task = queue_service.dequeue(worker_id="scraper")
            result = processor.process_task(scrape_task)
            assert result is True
            
            # Verify new content was created and task queued
            with setup_test_db as db:
                new_content = db.query(Content).filter(
                    Content.url.like("%scraped.com%")
                ).first()
                assert new_content is not None
                
                # Check processing task was created
                process_task = db.query(ProcessingTask).filter(
                    ProcessingTask.task_type == TaskType.PROCESS_CONTENT.value,
                    ProcessingTask.payload["content_id"].astext == str(new_content.id)
                ).first()
                assert process_task is not None