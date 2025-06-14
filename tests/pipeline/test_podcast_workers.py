import os
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.pipeline.podcast_workers import (
    PodcastDownloadWorker,
    PodcastTranscribeWorker,
    sanitize_filename,
    get_file_extension_from_url
)
from app.models.unified import Content, ContentStatus
from app.domain.content import ContentData, ContentType


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = Mock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.commit = Mock()
    return session


@pytest.fixture
def mock_content():
    """Create a mock content object."""
    content = Content()
    content.id = 1
    content.content_type = "podcast"
    content.url = "https://example.com/podcast"
    content.title = "Test Podcast Episode"
    content.status = ContentStatus.NEW.value
    content.content_metadata = {
        "audio_url": "https://example.com/audio.mp3",
        "podcast_feed_name": "Test Podcast Feed"
    }
    return content


class TestPodcastDownloadWorker:
    """Test the PodcastDownloadWorker."""
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        assert sanitize_filename("Hello World!") == "Hello-World"
        assert sanitize_filename("Test @ Episode #123") == "Test-Episode-123"
        assert sanitize_filename("   Spaces   ") == "Spaces"
        assert len(sanitize_filename("A" * 200)) == 100
    
    def test_get_file_extension_from_url(self):
        """Test file extension extraction from URL."""
        assert get_file_extension_from_url("https://example.com/audio.mp3") == ".mp3"
        assert get_file_extension_from_url("https://example.com/audio.m4a?token=123") == ".m4a"
        assert get_file_extension_from_url("https://example.com/audio") == ".mp3"
    
    @pytest.mark.asyncio
    @patch('app.pipeline.podcast_workers.get_db')
    @patch('app.pipeline.podcast_workers.httpx.Client')
    @patch('app.pipeline.podcast_workers.os.path.exists')
    async def test_download_podcast_success(self, mock_exists, mock_httpx, mock_get_db, mock_content):
        """Test successful podcast download."""
        # Setup mocks
        mock_exists.return_value = False  # File doesn't exist yet
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.iter_bytes.return_value = [b"audio data chunk 1", b"audio data chunk 2"]
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.stream.return_value.__enter__.return_value = mock_response
        mock_httpx.return_value.__enter__.return_value = mock_client
        
        # Mock queue service
        with patch('app.pipeline.podcast_workers.get_queue_service') as mock_queue:
            mock_queue_service = Mock()
            mock_queue.return_value = mock_queue_service
            
            # Run test
            worker = PodcastDownloadWorker()
            result = await worker.process_download_task(1)
            
            # Assertions
            assert result is True
            assert mock_db.commit.called
            assert mock_queue_service.enqueue.called
            
            # Check that file path was set in metadata
            metadata_updates = mock_content.content_metadata
            assert 'file_path' in metadata_updates
            assert 'download_date' in metadata_updates
    
    @pytest.mark.asyncio
    @patch('app.pipeline.podcast_workers.get_db')
    @patch('app.pipeline.podcast_workers.os.path.exists')
    async def test_download_podcast_file_exists(self, mock_exists, mock_get_db, mock_content):
        """Test download when file already exists."""
        # Setup mocks
        mock_exists.return_value = True  # File already exists
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        
        # Mock queue service
        with patch('app.pipeline.podcast_workers.get_queue_service') as mock_queue:
            mock_queue_service = Mock()
            mock_queue.return_value = mock_queue_service
            
            # Run test
            worker = PodcastDownloadWorker()
            result = await worker.process_download_task(1)
            
            # Assertions
            assert result is True
            assert mock_db.commit.called
            assert mock_queue_service.enqueue.called
            
            # Check that transcribe task was queued
            mock_queue_service.enqueue.assert_called_with(
                TaskType.TRANSCRIBE,
                content_id=1
            )
    
    @pytest.mark.asyncio
    @patch('app.pipeline.podcast_workers.get_db')
    async def test_download_podcast_no_audio_url(self, mock_get_db):
        """Test download when no audio URL is present."""
        # Setup mock content without audio URL
        mock_content = Content()
        mock_content.id = 1
        mock_content.content_metadata = {}
        
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        
        # Run test
        worker = PodcastDownloadWorker()
        result = await worker.process_download_task(1)
        
        # Assertions
        assert result is False
        assert mock_content.status == ContentStatus.FAILED.value
        assert mock_content.error_message == "No audio URL found"


class TestPodcastTranscribeWorker:
    """Test the PodcastTranscribeWorker."""
    
    @pytest.mark.asyncio
    @patch('app.pipeline.podcast_workers.get_db')
    @patch('app.pipeline.podcast_workers.os.path.exists')
    async def test_transcribe_podcast_success(self, mock_exists, mock_get_db, mock_content):
        """Test successful podcast transcription."""
        # Setup mocks
        mock_exists.return_value = True
        mock_content.content_metadata['file_path'] = "/path/to/audio.mp3"
        
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        
        # Mock Whisper model
        with patch('app.pipeline.podcast_workers.WhisperModel') as mock_whisper:
            mock_model = Mock()
            mock_info = Mock()
            mock_info.language = "en"
            mock_info.language_probability = 0.99
            
            # Mock segments
            mock_segment1 = Mock()
            mock_segment1.text = "This is a test"
            mock_segment2 = Mock()
            mock_segment2.text = " transcript"
            
            mock_model.transcribe.return_value = ([mock_segment1, mock_segment2], mock_info)
            mock_whisper.return_value = mock_model
            
            # Mock queue service
            with patch('app.pipeline.podcast_workers.get_queue_service') as mock_queue:
                mock_queue_service = Mock()
                mock_queue.return_value = mock_queue_service
                
                # Run test
                worker = PodcastTranscribeWorker()
                result = await worker.process_transcribe_task(1)
                
                # Assertions
                assert result is True
                assert mock_db.commit.called
                assert mock_queue_service.enqueue.called
                
                # Check metadata updates
                metadata = mock_content.content_metadata
                assert 'transcript' in metadata
                assert metadata['transcript'] == "This is a test transcript"
                assert 'transcript_path' in metadata
                assert 'detected_language' in metadata
                assert metadata['detected_language'] == "en"
    
    @pytest.mark.asyncio
    @patch('app.pipeline.podcast_workers.get_db')
    async def test_transcribe_podcast_no_file(self, mock_get_db):
        """Test transcription when audio file is missing."""
        # Setup mock content without file path
        mock_content = Content()
        mock_content.id = 1
        mock_content.content_metadata = {}
        
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        
        # Run test
        worker = PodcastTranscribeWorker()
        result = await worker.process_transcribe_task(1)
        
        # Assertions
        assert result is False
        assert mock_content.status == ContentStatus.FAILED.value
        assert "Audio file not found" in mock_content.error_message
    
    def test_cleanup_model(self):
        """Test model cleanup."""
        worker = PodcastTranscribeWorker()
        worker.model = Mock()  # Simulate loaded model
        
        worker.cleanup_model()
        
        assert worker.model is None


class TestTaskIntegration:
    """Test integration between download and transcribe tasks."""
    
    @pytest.mark.asyncio
    @patch('app.pipeline.podcast_workers.get_db')
    @patch('app.pipeline.podcast_workers.httpx.Client')
    @patch('app.pipeline.podcast_workers.os.path.exists')
    @patch('app.pipeline.podcast_workers.os.path.getsize')
    @patch('builtins.open', create=True)
    async def test_download_queues_transcribe(
        self, mock_open, mock_getsize, mock_exists, mock_httpx, mock_get_db, mock_content
    ):
        """Test that download task queues transcribe task."""
        # Setup mocks
        mock_exists.return_value = False
        mock_getsize.return_value = 1000  # File size
        
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.iter_bytes.return_value = [b"audio data"]
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
            
            # Run download
            worker = PodcastDownloadWorker()
            result = await worker.process_download_task(1)
            
            # Verify transcribe task was queued
            assert result is True
            mock_queue_service.enqueue.assert_called_once()
            call_args = mock_queue_service.enqueue.call_args
            assert call_args[0][0].value == "transcribe"
            assert call_args[1]['content_id'] == 1