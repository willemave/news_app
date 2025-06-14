import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from app.models.schema import Content, ContentStatus, ProcessingTask
from app.services.queue import TaskType, TaskStatus
from app.pipeline.task_processor import TaskProcessor, TaskProcessorPool
from app.domain.content import ContentData, ContentType


@pytest.fixture
def mock_podcast_content():
    """Create a mock podcast content in database."""
    content = Content()
    content.id = 100
    content.content_type = "podcast"
    content.url = "https://example.com/podcast/episode1"
    content.title = "Test Podcast Episode 1"
    content.status = ContentStatus.NEW.value
    content.content_metadata = {
        "audio_url": "https://example.com/audio/episode1.mp3",
        "podcast_feed_name": "Test Podcast Show",
        "episode_number": 1,
        "duration": 1800  # 30 minutes
    }
    content.created_at = datetime.utcnow()
    return content


@pytest.fixture
def mock_download_task():
    """Create a mock download task."""
    task = ProcessingTask()
    task.id = 1
    task.task_type = TaskType.DOWNLOAD_AUDIO.value
    task.content_id = 100
    task.status = TaskStatus.PENDING.value
    task.created_at = datetime.utcnow()
    return task


@pytest.fixture
def mock_transcribe_task():
    """Create a mock transcribe task."""
    task = ProcessingTask()
    task.id = 2
    task.task_type = TaskType.TRANSCRIBE.value
    task.content_id = 100
    task.status = TaskStatus.PENDING.value
    task.created_at = datetime.utcnow()
    return task


@pytest.fixture
def mock_summarize_task():
    """Create a mock summarize task."""
    task = ProcessingTask()
    task.id = 3
    task.task_type = TaskType.SUMMARIZE.value
    task.content_id = 100
    task.status = TaskStatus.PENDING.value
    task.created_at = datetime.utcnow()
    return task


class TestPodcastPipelineIntegration:
    """Test the complete podcast processing pipeline."""
    
    @pytest.mark.asyncio
    @patch('app.pipeline.task_processor.get_db')
    @patch('app.pipeline.podcast_workers.get_db')
    @patch('app.pipeline.podcast_workers.httpx.Client')
    @patch('app.pipeline.podcast_workers.os.path.exists')
    @patch('app.pipeline.podcast_workers.os.path.getsize')
    @patch('builtins.open', create=True)
    async def test_complete_podcast_pipeline(
        self,
        mock_open,
        mock_getsize,
        mock_exists,
        mock_httpx,
        mock_podcast_db,
        mock_task_db,
        mock_podcast_content,
        mock_download_task
    ):
        """Test the complete flow from download to summarization."""
        # Setup database mocks
        mock_podcast_db.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_podcast_content
        mock_podcast_db.return_value.__enter__.return_value.commit = Mock()
        
        mock_task_db.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_podcast_content
        mock_task_db.return_value.__enter__.return_value.commit = Mock()
        
        # Setup file system mocks
        mock_exists.return_value = False  # File doesn't exist initially
        mock_getsize.return_value = 5000000  # 5MB file
        
        # Mock HTTP download
        mock_response = Mock()
        mock_response.iter_bytes.return_value = [b"audio data chunk " * 1000]
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.stream.return_value.__enter__.return_value = mock_response
        mock_httpx.return_value.__enter__.return_value = mock_client
        
        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock queue service
        with patch('app.pipeline.podcast_workers.get_queue_service') as mock_queue:
            mock_queue_service = Mock()
            mock_queue.return_value = mock_queue_service
            
            # Create task processor
            processor = TaskProcessor()
            
            # Process download task
            result = await processor.process_task(mock_download_task)
            assert result is True
            
            # Verify transcribe task was queued
            mock_queue_service.enqueue.assert_called_once()
            assert mock_queue_service.enqueue.call_args[0][0] == TaskType.TRANSCRIBE
            
            # Verify content metadata was updated
            assert 'file_path' in mock_podcast_content.content_metadata
            assert 'download_date' in mock_podcast_content.content_metadata
            assert 'file_size' in mock_podcast_content.content_metadata
    
    @pytest.mark.asyncio
    @patch('app.pipeline.task_processor.get_db')
    @patch('app.pipeline.podcast_workers.get_db')
    @patch('app.pipeline.podcast_workers.os.path.exists')
    @patch('app.pipeline.podcast_workers.WhisperModel')
    @patch('builtins.open', create=True)
    async def test_transcribe_and_summarize_flow(
        self,
        mock_open,
        mock_whisper,
        mock_exists,
        mock_podcast_db,
        mock_task_db,
        mock_podcast_content,
        mock_transcribe_task
    ):
        """Test transcription followed by summarization."""
        # Update content to have downloaded file
        mock_podcast_content.content_metadata['file_path'] = "/data/podcasts/test/episode1.mp3"
        
        # Setup database mocks
        mock_podcast_db.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_podcast_content
        mock_podcast_db.return_value.__enter__.return_value.commit = Mock()
        
        mock_task_db.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_podcast_content
        mock_task_db.return_value.__enter__.return_value.commit = Mock()
        
        # Mock file exists
        mock_exists.return_value = True
        
        # Mock Whisper transcription
        mock_model = Mock()
        mock_info = Mock()
        mock_info.language = "en"
        mock_info.language_probability = 0.98
        
        # Create mock transcript segments
        mock_segments = []
        transcript_text = "This is a test podcast episode about artificial intelligence and machine learning."
        for word in transcript_text.split():
            segment = Mock()
            segment.text = f" {word}"
            mock_segments.append(segment)
        
        mock_model.transcribe.return_value = (mock_segments, mock_info)
        mock_whisper.return_value = mock_model
        
        # Mock file write
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock queue service
        with patch('app.pipeline.podcast_workers.get_queue_service') as mock_queue:
            mock_queue_service = Mock()
            mock_queue.return_value = mock_queue_service
            
            # Mock LLM service for summarization
            with patch('app.pipeline.task_processor.get_llm_service') as mock_llm:
                mock_llm_service = Mock()
                mock_llm_service.summarize_content = AsyncMock(
                    return_value="This podcast discusses AI and ML concepts."
                )
                mock_llm.return_value = mock_llm_service
                
                # Create task processor
                processor = TaskProcessor()
                
                # Process transcribe task
                result = await processor.process_task(mock_transcribe_task)
                assert result is True
                
                # Verify summarize task was queued
                mock_queue_service.enqueue.assert_called_once()
                assert mock_queue_service.enqueue.call_args[0][0] == TaskType.SUMMARIZE
                
                # Verify transcript was saved
                assert 'transcript' in mock_podcast_content.content_metadata
                assert 'transcript_path' in mock_podcast_content.content_metadata
                assert 'detected_language' in mock_podcast_content.content_metadata
                
                # Now process the summarize task
                mock_summarize_task = Mock()
                mock_summarize_task.id = 3
                mock_summarize_task.task_type = TaskType.SUMMARIZE.value
                mock_summarize_task.content_id = 100
                
                result = await processor.process_task(mock_summarize_task)
                assert result is True
                
                # Verify summary was generated
                assert mock_llm_service.summarize_content.called
                assert mock_podcast_content.content_metadata.get('summary') is not None
                assert mock_podcast_content.status == "completed"
    
    @pytest.mark.asyncio
    @patch('app.pipeline.task_processor.get_queue_service')
    @patch('app.pipeline.task_processor.TaskProcessor')
    async def test_task_processor_pool(self, mock_processor_class, mock_queue_service):
        """Test the task processor pool."""
        # Mock queue service
        queue_service = Mock()
        mock_queue_service.return_value = queue_service
        
        # Create mock tasks
        tasks = []
        for i in range(5):
            task = Mock()
            task.id = i + 1
            task.task_type = TaskType.DOWNLOAD_AUDIO.value
            task.content_id = 100 + i
            task.retry_count = 0
            tasks.append(task)
        
        # Queue returns tasks then None
        queue_service.dequeue.side_effect = tasks + [None] * 3  # None for each worker
        queue_service.complete_task = Mock()
        
        # Mock processor
        mock_processor = Mock()
        mock_processor.process_task = AsyncMock(return_value=True)
        mock_processor.run_worker = Mock()
        mock_processor_class.return_value = mock_processor
        
        # Create and run pool
        pool = TaskProcessorPool(max_workers=3)
        
        # Mock the actual worker execution
        def mock_run_worker(worker_id, max_tasks):
            # Simulate processing some tasks
            for _ in range(2):  # Each worker processes 2 tasks
                task = queue_service.dequeue(worker_id=worker_id)
                if task:
                    asyncio.run(mock_processor.process_task(task))
                    queue_service.complete_task(task.id, success=True)
        
        mock_processor.run_worker.side_effect = mock_run_worker
        
        # Run the pool
        pool.run_pool(max_tasks_per_worker=5)
        
        # Verify workers were created
        assert mock_processor_class.call_count == 3  # 3 workers
        assert mock_processor.run_worker.call_count == 3


class TestErrorHandling:
    """Test error handling in the podcast pipeline."""
    
    @pytest.mark.asyncio
    @patch('app.pipeline.podcast_workers.get_db')
    @patch('app.pipeline.podcast_workers.httpx.Client')
    async def test_download_failure_retry(self, mock_httpx, mock_db, mock_podcast_content):
        """Test download failure and retry mechanism."""
        # Setup database mock
        mock_db.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_podcast_content
        mock_db.return_value.__enter__.return_value.commit = Mock()
        
        # Mock HTTP error
        mock_httpx.side_effect = Exception("Network error")
        
        # Mock queue service
        with patch('app.pipeline.podcast_workers.get_queue_service') as mock_queue:
            mock_queue_service = Mock()
            mock_queue.return_value = mock_queue_service
            
            # Create processor
            processor = TaskProcessor()
            
            # Create download task
            task = Mock()
            task.id = 1
            task.task_type = TaskType.DOWNLOAD_AUDIO.value
            task.content_id = 100
            task.retry_count = 0
            
            # Process should fail
            result = await processor.process_task(task)
            assert result is False
            
            # Verify content was marked as failed
            assert mock_podcast_content.status == ContentStatus.FAILED.value
            assert mock_podcast_content.error_message is not None
            assert mock_podcast_content.retry_count == 1


# Helper for async mocks
class AsyncMock(Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)