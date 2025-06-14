"""
Test cases for LLMService functionality.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.llm import LLMService, MockProvider, OpenAIProvider


class TestLLMService:
    """Test the LLMService class."""
    
    @pytest.mark.asyncio
    async def test_summarize_content_success(self):
        """Test successful content summarization."""
        mock_provider = AsyncMock(spec=MockProvider)
        mock_provider.generate.return_value = "This is a test summary of the content."
        
        service = LLMService()
        service.provider = mock_provider
        
        content = "This is a long article about artificial intelligence and machine learning."
        result = await service.summarize_content(content, max_length=100)
        
        assert result == "This is a test summary of the content."
        mock_provider.generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_summarize_content_with_bytes(self):
        """Test content summarization with bytes input."""
        mock_provider = AsyncMock(spec=MockProvider)
        mock_provider.generate.return_value = "Summary of byte content."
        
        service = LLMService()
        service.provider = mock_provider
        
        content = b"This is byte content that needs to be decoded."
        result = await service.summarize_content(content)
        
        assert result == "Summary of byte content."
        mock_provider.generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_summarize_content_truncates_long_content(self):
        """Test that long content is truncated."""
        mock_provider = AsyncMock(spec=MockProvider)
        mock_provider.generate.return_value = "Summary of truncated content."
        
        service = LLMService()
        service.provider = mock_provider
        
        # Create content longer than 10000 characters
        content = "A" * 15000
        result = await service.summarize_content(content)
        
        assert result == "Summary of truncated content."
        # Verify that the content passed to the provider was truncated
        call_args = mock_provider.generate.call_args
        prompt = call_args.kwargs['prompt']
        assert "A" * 10000 + "..." in prompt
    
    @pytest.mark.asyncio
    async def test_summarize_content_provider_error(self):
        """Test handling of provider errors."""
        mock_provider = AsyncMock(spec=MockProvider)
        mock_provider.generate.side_effect = Exception("API error")
        
        service = LLMService()
        service.provider = mock_provider
        
        content = "Test content"
        result = await service.summarize_content(content)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_extract_topics_success(self):
        """Test successful topic extraction."""
        mock_provider = AsyncMock(spec=MockProvider)
        mock_provider.generate.return_value = '["AI", "Machine Learning", "Technology"]'
        
        service = LLMService()
        service.provider = mock_provider
        
        content = "This article discusses artificial intelligence and machine learning technologies."
        result = await service.extract_topics(content)
        
        assert result == ["AI", "Machine Learning", "Technology"]
        mock_provider.generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_topics_invalid_json(self):
        """Test topic extraction with invalid JSON response."""
        mock_provider = AsyncMock(spec=MockProvider)
        mock_provider.generate.return_value = "Not valid JSON"
        
        service = LLMService()
        service.provider = mock_provider
        
        content = "Test content"
        result = await service.extract_topics(content)
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_extract_topics_provider_error(self):
        """Test topic extraction with provider error."""
        mock_provider = AsyncMock(spec=MockProvider)
        mock_provider.generate.side_effect = Exception("API error")
        
        service = LLMService()
        service.provider = mock_provider
        
        content = "Test content"
        result = await service.extract_topics(content)
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_extract_topics_limits_results(self):
        """Test that topic extraction limits results to 10."""
        mock_provider = AsyncMock(spec=MockProvider)
        # Return more than 10 topics
        topics = [f"Topic{i}" for i in range(15)]
        mock_provider.generate.return_value = f'{topics}'
        
        service = LLMService()
        service.provider = mock_provider
        
        content = "Test content with many topics"
        result = await service.extract_topics(content)
        
        assert len(result) == 10
        assert result == topics[:10]


class TestMockProvider:
    """Test the MockProvider."""
    
    @pytest.mark.asyncio
    async def test_mock_provider_generate(self):
        """Test MockProvider generate method."""
        provider = MockProvider()
        
        prompt = "Test prompt for mock"
        result = await provider.generate(prompt)
        
        assert "Mock response for: Test prompt for mock..." in result


class TestProviderInitialization:
    """Test provider initialization logic."""
    
    @patch('app.services.llm.get_settings')
    def test_initialize_openai_provider(self, mock_get_settings):
        """Test initialization with OpenAI API key."""
        mock_settings = Mock()
        mock_settings.openai_api_key = "test-api-key"
        mock_get_settings.return_value = mock_settings
        
        with patch('app.services.llm.OpenAIProvider') as mock_openai:
            service = LLMService()
            
            mock_openai.assert_called_once_with("test-api-key")
            assert isinstance(service.provider, type(mock_openai.return_value))
    
    @patch('app.services.llm.get_settings')
    def test_initialize_mock_provider_no_key(self, mock_get_settings):
        """Test initialization without API key falls back to mock."""
        mock_settings = Mock()
        mock_settings.openai_api_key = None
        mock_get_settings.return_value = mock_settings
        
        service = LLMService()
        
        assert isinstance(service.provider, MockProvider)