"""Tests for synchronous methods added to services."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx

from app.services.http import HttpService, NonRetryableError
from app.services.google_flash import GoogleFlashService
from app.models.metadata import StructuredSummary


class TestHttpServiceSync:
    """Test synchronous methods in HttpService."""
    
    @pytest.fixture
    def http_service(self):
        """Create HttpService instance."""
        return HttpService()
    
    def test_fetch_content_sync_success(self, http_service):
        """Test successful synchronous content fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            content, headers = http_service.fetch_content_sync("https://example.com")
            
            assert content == "<html><body>Test content</body></html>"
            assert headers["Content-Type"] == "text/html"
            mock_client.get.assert_called_once()
    
    def test_fetch_content_sync_binary(self, http_service):
        """Test fetching binary content synchronously."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.content = b"PDF binary content"
        mock_response.raise_for_status = Mock()
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            content, headers = http_service.fetch_content_sync("https://example.com/file.pdf")
            
            assert content == b"PDF binary content"
            assert headers["Content-Type"] == "application/pdf"
    
    def test_fetch_content_sync_http_error(self, http_service):
        """Test HTTP error handling in sync fetch."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=Mock(),
            response=mock_response
        )
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            with pytest.raises(NonRetryableError):
                http_service.fetch_content_sync("https://example.com/missing")
    
    def test_fetch_content_sync_ssl_error(self, http_service):
        """Test SSL error handling in sync fetch."""
        ssl_error = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]")
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.get.side_effect = ssl_error
            mock_client_class.return_value = mock_client
            
            with pytest.raises(NonRetryableError) as exc_info:
                http_service.fetch_content_sync("https://example.com")
            
            assert "SSL error" in str(exc_info.value)


class TestGoogleFlashServiceSync:
    """Test synchronous methods in GoogleFlashService."""
    
    @pytest.fixture
    def google_flash_service(self):
        """Create GoogleFlashService instance with mocked client."""
        with patch('app.services.google_flash.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = 'test-key'
            with patch('google.genai.Client'):
                service = GoogleFlashService()
                service.client = Mock()
                return service
    
    def test_summarize_content_sync_success(self, google_flash_service):
        """Test successful synchronous content summarization."""
        # Mock the Google provider response
        mock_response = Mock()
        mock_response.text = '''
        {
            "title": "Test Article Summary",
            "overview": "This is a comprehensive overview of the test content that provides context.",
            "bullet_points": [
                {"text": "First key point", "category": "key_finding"},
                {"text": "Second key point", "category": "methodology"}
            ],
            "quotes": [
                {"text": "This is an important quote from the content.", "context": "Author Name"}
            ],
            "topics": ["testing", "summary", "llm"],
            "classification": "to_read"
        }
        '''
        
        google_flash_service.client.models.generate_content.return_value = mock_response
        
        result = google_flash_service.summarize_content_sync("Test content to summarize")
        
        assert isinstance(result, StructuredSummary)
        assert result.title == "Test Article Summary"
        assert len(result.bullet_points) == 2
        assert len(result.quotes) == 1
        assert result.classification == "to_read"
    
    def test_summarize_content_sync_json_error(self, google_flash_service):
        """Test JSON parsing error handling."""
        # Mock invalid JSON response
        mock_response = Mock()
        mock_response.text = "Invalid JSON {not closed"
        
        google_flash_service.provider.client = Mock()
        google_flash_service.provider.client.models.generate_content.return_value = mock_response
        google_flash_service.provider.model_name = "test-model"
        
        result = google_flash_service.summarize_content_sync("Test content")
        
        # Should return error dict instead of None
        assert isinstance(result, dict)
        assert result["overview"] == "Failed to generate summary due to JSON parsing error"
        assert result["classification"] == "to_read"
    
    def test_summarize_content_sync_non_google_provider(self, google_flash_service):
        """Test behavior with non-Google provider."""
        # Set provider to non-Google
        google_flash_service.provider = Mock()  # Not GoogleProvider instance
        
        result = google_flash_service.summarize_content_sync("Test content")
        
        # Should return None for non-Google providers
        assert result is None
    
    def test_summarize_content_sync_truncation(self, google_flash_service):
        """Test content truncation for long inputs."""
        # Create very long content
        long_content = "x" * 20000
        
        mock_response = Mock()
        mock_response.text = '{"title": "Test", "overview": "Truncated", "bullet_points": [], "quotes": [], "topics": [], "classification": "to_read"}'
        
        google_flash_service.provider.client = Mock()
        google_flash_service.provider.client.models.generate_content.return_value = mock_response
        google_flash_service.provider.model_name = "test-model"
        
        # Capture the actual prompt sent
        actual_prompt = None
        def capture_prompt(model, contents, config):
            nonlocal actual_prompt
            actual_prompt = contents
            return mock_response
        
        google_flash_service.provider.client.models.generate_content.side_effect = capture_prompt
        
        result = google_flash_service.summarize_content_sync(long_content)
        
        # Verify content was truncated
        assert "..." in actual_prompt
        assert len(actual_prompt) < len(long_content)


class TestScraperRunnerSync:
    """Test synchronous methods in ScraperRunner."""
    
    def test_run_all_sync(self):
        """Test running all scrapers synchronously."""
        from app.scraping.runner import ScraperRunner
        
        with patch('asyncio.new_event_loop') as mock_new_loop:
            mock_loop = Mock()
            mock_new_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = 10
            
            runner = ScraperRunner()
            runner.scrapers = [Mock(name="test_scraper")]
            
            results = runner.run_all_sync()
            
            assert results["test_scraper"] == 10
            mock_loop.close.assert_called_once()
    
    def test_run_scraper_sync_not_found(self):
        """Test running non-existent scraper."""
        from app.scraping.runner import ScraperRunner
        
        runner = ScraperRunner()
        result = runner.run_scraper_sync("nonexistent")
        
        assert result is None


class TestPodcastWorkersSync:
    """Test synchronous methods in podcast workers."""
    
    def test_download_task_sync(self):
        """Test synchronous download task processing."""
        from app.pipeline.podcast_workers import PodcastDownloadWorker
        
        with patch('asyncio.new_event_loop') as mock_new_loop:
            mock_loop = Mock()
            mock_new_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = True
            
            worker = PodcastDownloadWorker()
            result = worker.process_download_task_sync(123)
            
            assert result is True
            mock_loop.close.assert_called_once()
    
    def test_transcribe_task_sync(self):
        """Test synchronous transcribe task processing."""
        from app.pipeline.podcast_workers import PodcastTranscribeWorker
        
        with patch('asyncio.new_event_loop') as mock_new_loop:
            mock_loop = Mock()
            mock_new_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = True
            
            worker = PodcastTranscribeWorker()
            result = worker.process_transcribe_task_sync(456)
            
            assert result is True
            mock_loop.close.assert_called_once()