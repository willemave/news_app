"""Test to reproduce and fix the task processing bug."""
import asyncio
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from app.pipeline.task_processor import TaskProcessor, TaskProcessorPool
from app.services.queue import TaskType, TaskStatus


def test_task_processor_async_sync_issue():
    """Test that reproduces the async/sync issue in task processing."""
    
    # Mock the dependencies
    with patch('app.pipeline.task_processor.get_queue_service') as mock_queue_service, \
         patch('app.pipeline.task_processor.get_llm_service') as mock_llm_service, \
         patch('app.pipeline.task_processor.ScraperRunner') as mock_scraper_runner, \
         patch('app.pipeline.task_processor.ContentWorker') as mock_content_worker, \
         patch('app.pipeline.task_processor.get_db') as mock_get_db:
        
        # Setup mock queue service
        mock_queue = Mock()
        mock_queue_service.return_value = mock_queue
        
        # Create a mock task
        task_data = {
            'id': 1,
            'task_type': TaskType.PROCESS_CONTENT.value,
            'content_id': 123,
            'payload': {},
            'retry_count': 0,
            'status': TaskStatus.PROCESSING.value,
            'created_at': datetime.now(timezone.utc),
            'started_at': datetime.now(timezone.utc)
        }
        
        # Setup queue to return the task once then None
        mock_queue.dequeue.side_effect = [task_data, None]
        mock_queue.complete_task = Mock()
        
        # Setup content worker to succeed
        mock_worker_instance = Mock()
        async def mock_process_content(*args):
            return True
        mock_worker_instance.process_content = mock_process_content
        mock_content_worker.return_value = mock_worker_instance
        
        # Create processor
        processor = TaskProcessor()
        
        # Run the worker in a thread to simulate the real usage
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(processor.run_worker, "test-worker", 1)
            future.result()
        
        # Verify the task was processed
        assert mock_queue.dequeue.call_count >= 1  # At least one dequeue call
        mock_queue.complete_task.assert_called_once_with(1, success=True)


def test_task_processor_pool_threading_issue():
    """Test the threading issue in TaskProcessorPool."""
    
    with patch('app.pipeline.task_processor.get_queue_service') as mock_queue_service, \
         patch('app.pipeline.task_processor.TaskProcessor') as mock_task_processor:
        
        # Setup mock queue with stats
        mock_queue = Mock()
        mock_queue.get_queue_stats.return_value = {
            'by_status': {TaskStatus.PENDING.value: 5}
        }
        mock_queue_service.return_value = mock_queue
        
        # Setup mock processor
        mock_processor_instance = Mock()
        mock_processor_instance.run_worker = Mock()
        mock_task_processor.return_value = mock_processor_instance
        
        # Create pool and run
        pool = TaskProcessorPool(max_workers=2)
        pool.run_pool(max_tasks_per_worker=1)
        
        # Verify workers were started
        assert mock_processor_instance.run_worker.call_count == 2


@pytest.mark.asyncio 
async def test_asyncio_run_in_thread_issue():
    """Test that demonstrates the asyncio.run() issue when called from threads."""
    
    import threading
    from concurrent.futures import ThreadPoolExecutor
    
    results = []
    errors = []
    
    async def async_task():
        await asyncio.sleep(0.1)
        return "success"
    
    def thread_worker():
        try:
            # This is what the current code does - asyncio.run() in a thread
            result = asyncio.run(async_task())
            results.append(result)
        except Exception as e:
            errors.append(str(e))
    
    # Run multiple workers in threads
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i in range(3):
            future = executor.submit(thread_worker)
            futures.append(future)
        
        # Wait for all to complete
        for future in futures:
            future.result()
    
    # This should work but might have issues with event loop
    assert len(results) == 3
    assert all(r == "success" for r in results)
    assert len(errors) == 0