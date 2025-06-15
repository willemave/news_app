"""
Test cases for LLMService JSON parsing robustness.
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock, PropertyMock
from datetime import datetime

from app.services.llm import LLMService, MockProvider, OpenAIProvider, GoogleProvider
from app.models.metadata import StructuredSummary


class TestLLMServiceJSONParsing:
    """Test the LLMService JSON parsing robustness."""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create LLM service with mock provider."""
        service = LLMService()
        service.provider = Mock()
        return service
    
    @pytest.mark.asyncio
    async def test_summarize_content_valid_json(self, mock_llm_service):
        """Test successful JSON parsing for structured summary."""
        valid_response = {
            "overview": "This is a comprehensive test overview that provides detailed context about the content being summarized. It meets the minimum length requirement.",
            "bullet_points": [
                {"text": "First key finding from the analysis", "category": "key_finding"},
                {"text": "Important methodology used in the process", "category": "methodology"},
                {"text": "Significant conclusion drawn from the data", "category": "conclusion"}
            ],
            "quotes": [
                {"text": "This is a notable quote", "context": "Author Name"}
            ],
            "topics": ["AI", "Technology"]
        }
        
        mock_llm_service.provider.generate = AsyncMock(
            return_value=json.dumps(valid_response)
        )
        
        content = "Test content for summarization"
        result = await mock_llm_service.summarize_content(content)
        
        assert isinstance(result, StructuredSummary)
        assert result.overview == valid_response["overview"]
        assert len(result.bullet_points) == 3
        assert len(result.quotes) == 1
        assert len(result.topics) == 2
    
    @pytest.mark.asyncio
    async def test_summarize_content_malformed_json(self, mock_llm_service):
        """Test handling of malformed JSON response."""
        # Missing closing brace
        malformed_json = '{"overview": "Test", "bullet_points": ['
        
        mock_llm_service.provider.generate = AsyncMock(
            return_value=malformed_json
        )
        
        content = "Test content"
        result = await mock_llm_service.summarize_content(content)
        
        # Should return dict with error message
        assert isinstance(result, dict)
        assert result["overview"] == "Failed to generate summary due to JSON parsing error"
        assert result["bullet_points"] == []
    
    @pytest.mark.asyncio
    async def test_summarize_content_truncated_json(self, mock_llm_service):
        """Test handling of truncated JSON response."""
        # JSON truncated mid-way
        truncated_json = '''{
            "overview": "This is a test overview",
            "bullet_points": [
                {"text": "First point", "category": "key_finding"},
                {"text": "Second point", "categ'''
        
        mock_llm_service.provider.generate = AsyncMock(
            return_value=truncated_json
        )
        
        content = "Test content"
        result = await mock_llm_service.summarize_content(content)
        
        # Should return dict with error message
        assert isinstance(result, dict)
        assert result["overview"] == "Failed to generate summary due to JSON parsing error"
    
    @pytest.mark.asyncio
    async def test_summarize_content_with_bytes(self, mock_llm_service):
        """Test content summarization with bytes input."""
        valid_response = {
            "overview": "Summary of byte content that meets the minimum length requirement for validation purposes.",
            "bullet_points": [
                {"text": "Key finding from byte content", "category": "key_finding"},
                {"text": "Analysis methodology applied", "category": "methodology"},
                {"text": "Important conclusion reached", "category": "conclusion"}
            ],
            "quotes": [],
            "topics": ["Bytes", "Content"]
        }
        
        mock_llm_service.provider.generate = AsyncMock(
            return_value=json.dumps(valid_response)
        )
        
        content = b"This is byte content that needs to be decoded."
        result = await mock_llm_service.summarize_content(content)
        
        assert isinstance(result, StructuredSummary)
        assert "byte content" in result.overview
    
    @pytest.mark.asyncio
    async def test_summarize_content_truncates_long_content(self, mock_llm_service):
        """Test that long content is truncated."""
        valid_response = {
            "overview": "Summary of truncated content that meets the minimum length requirement for proper validation.",
            "bullet_points": [
                {"text": "Content was truncated for processing", "category": "key_finding"},
                {"text": "Analysis performed on truncated data", "category": "methodology"},
                {"text": "Results based on partial content", "category": "conclusion"}
            ],
            "quotes": [],
            "topics": ["Truncated"]
        }
        
        mock_llm_service.provider.generate = AsyncMock(
            return_value=json.dumps(valid_response)
        )
        
        # Create content longer than 15000 characters
        content = "A" * 20000
        result = await mock_llm_service.summarize_content(content)
        
        assert isinstance(result, StructuredSummary)
        # Verify that the content passed to the provider was truncated
        call_args = mock_llm_service.provider.generate.call_args
        prompt = call_args[1]['prompt']
        assert len(prompt) < 20000
        assert "..." in prompt
    
    @pytest.mark.asyncio
    async def test_summarize_content_provider_error(self, mock_llm_service):
        """Test handling of provider errors."""
        mock_llm_service.provider.generate = AsyncMock(
            side_effect=Exception("API error")
        )
        
        content = "Test content"
        result = await mock_llm_service.summarize_content(content)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_summarize_content_missing_required_fields(self, mock_llm_service):
        """Test handling of response missing required fields."""
        # Missing bullet_points
        incomplete_response = {
            "overview": "This is a test overview that meets minimum length requirements for validation.",
            "quotes": [],
            "topics": ["Test"]
        }
        
        mock_llm_service.provider.generate = AsyncMock(
            return_value=json.dumps(incomplete_response)
        )
        
        content = "Test content"
        result = await mock_llm_service.summarize_content(content)
        
        # Should return None on validation error (bullet_points requires min 3 items)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_summarize_content_invalid_field_types(self, mock_llm_service):
        """Test handling of invalid field types in response."""
        invalid_response = {
            "overview": "Valid overview that meets the minimum length requirement for proper validation.",
            "bullet_points": "This should be an array",  # Wrong type
            "quotes": [],
            "topics": ["Test"]
        }
        
        mock_llm_service.provider.generate = AsyncMock(
            return_value=json.dumps(invalid_response)
        )
        
        content = "Test content"
        result = await mock_llm_service.summarize_content(content)
        
        # Should return None on validation error
        assert result is None


class TestMockProvider:
    """Test the MockProvider."""
    
    @pytest.mark.asyncio
    async def test_mock_provider_generate(self):
        """Test MockProvider returns structured summary JSON."""
        provider = MockProvider()
        
        prompt = "Test prompt for mock"
        result = await provider.generate(prompt)
        
        # Should return valid JSON for structured summary
        parsed = json.loads(result)
        assert "overview" in parsed
        assert "bullet_points" in parsed
        assert "quotes" in parsed
        assert "topics" in parsed
        assert len(parsed["bullet_points"]) >= 3


class TestProviderInitialization:
    """Test provider initialization logic."""
    
    @patch('app.services.llm.settings')
    def test_initialize_google_provider(self, mock_settings):
        """Test initialization with Google API key."""
        mock_settings.google_api_key = "test-google-key"
        mock_settings.openai_api_key = "test-openai-key"
        
        with patch('app.services.llm.GoogleProvider') as mock_google:
            service = LLMService()
            
            # Should prefer Google provider when available
            mock_google.assert_called_once_with("test-google-key")
            assert service.provider == mock_google.return_value
    
    @patch('app.services.llm.settings')
    def test_initialize_openai_provider(self, mock_settings):
        """Test initialization with OpenAI API key."""
        # Delete google_api_key attribute to simulate it not existing
        if hasattr(mock_settings, 'google_api_key'):
            delattr(mock_settings, 'google_api_key')
        mock_settings.openai_api_key = "test-api-key"
        
        with patch('app.services.llm.OpenAIProvider') as mock_openai:
            service = LLMService()
            
            mock_openai.assert_called_once_with("test-api-key")
            assert service.provider == mock_openai.return_value
    
    @patch('app.services.llm.settings')
    def test_initialize_mock_provider_no_key(self, mock_settings):
        """Test initialization without API key falls back to mock."""
        # Delete both attributes to simulate them not existing
        if hasattr(mock_settings, 'google_api_key'):
            delattr(mock_settings, 'google_api_key')
        mock_settings.openai_api_key = None
        
        service = LLMService()
        
        assert isinstance(service.provider, MockProvider)