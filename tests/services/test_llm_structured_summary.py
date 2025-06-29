"""Tests for structured summarization in LLM service."""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.google_flash import GoogleFlashService
from app.models.metadata import StructuredSummary, SummaryBulletPoint, ContentQuote


class TestStructuredSummarization:
    """Test structured summarization functionality."""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create LLM service with mocked Google client."""
        with patch('app.services.google_flash.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = 'test-key'
            service = GoogleFlashService()
            service.client = Mock()
            return service
    
    @pytest.fixture
    def sample_content(self):
        """Sample content for testing."""
        return """
        Artificial Intelligence Research Makes Major Breakthrough
        
        Researchers at Stanford University have developed a new AI model that can 
        understand and generate code with unprecedented accuracy. Dr. Jane Smith, 
        lead researcher, stated: "This represents a paradigm shift in how AI can 
        assist software development."
        
        The key findings include:
        - 95% accuracy in code generation tasks
        - Ability to understand complex programming concepts
        - Reduced development time by 40%
        
        "We believe this will revolutionize the industry," added Dr. John Doe, 
        co-author of the study. The team plans to open-source their model next month.
        """
    
    @pytest.fixture
    def mock_structured_response(self):
        """Mock structured response from LLM."""
        return {
            "title": "Stanford AI Breakthrough: 95% Accurate Code Generation Model Transforms Software Development",
            "overview": "Stanford researchers develop groundbreaking AI model for code generation with 95% accuracy.",
            "bullet_points": [
                {
                    "text": "AI model achieves 95% accuracy in code generation tasks",
                    "category": "key_finding"
                },
                {
                    "text": "Model demonstrates understanding of complex programming concepts",
                    "category": "methodology"
                },
                {
                    "text": "Development time reduced by 40% in testing scenarios",
                    "category": "conclusion"
                }
            ],
            "quotes": [
                {
                    "text": "This represents a paradigm shift in how AI can assist software development. "
                    "The advances we're seeing now are just the beginning of what's possible. "
                    "Our model demonstrates that AI can truly understand the intent behind code, not just pattern match.",
                    "context": "Dr. Jane Smith, lead researcher"
                },
                {
                    "text": "We believe this will revolutionize the industry. "
                    "The implications go far beyond just code generation - we're talking about fundamentally changing how software is designed and built. "
                    "Teams using this technology could see productivity gains we've never imagined before.",
                    "context": "Dr. John Doe, co-author"
                }
            ],
            "topics": ["AI", "Software Development", "Research", "Stanford"]
        }
    
    @pytest.mark.asyncio
    async def test_generate_structured_summary_success(
        self, mock_llm_service, sample_content, mock_structured_response
    ):
        """Test successful generation of structured summary."""
        # Mock the Google client's response
        mock_response = Mock()
        mock_response.text = json.dumps(mock_structured_response)
        mock_llm_service.client.models.generate_content = Mock(return_value=mock_response)
        
        result = await mock_llm_service.summarize_content(sample_content)
        
        # Verify result is a StructuredSummary
        assert isinstance(result, StructuredSummary)
        assert result.title == mock_structured_response["title"]
        assert result.overview == mock_structured_response["overview"]
        assert len(result.bullet_points) == 3
        assert len(result.quotes) == 2
        assert len(result.topics) == 4
        
        # Verify bullet points
        assert result.bullet_points[0].text == mock_structured_response["bullet_points"][0]["text"]
        assert result.bullet_points[0].category == "key_finding"
        
        # Verify quotes
        assert result.quotes[0].text == mock_structured_response["quotes"][0]["text"]
        assert result.quotes[0].context == "Dr. Jane Smith, lead researcher"
        # Verify quotes are longer (2-3 sentences)
        assert len(result.quotes[0].text) > 100  # Ensuring meaningful length
    
    @pytest.mark.asyncio
    async def test_generate_structured_summary_with_json_markdown(
        self, mock_llm_service, sample_content, mock_structured_response
    ):
        """Test handling of JSON wrapped in markdown code blocks."""
        # Mock response with markdown code blocks
        wrapped_response = f"```json\n{json.dumps(mock_structured_response)}\n```"
        mock_response = Mock()
        mock_response.text = wrapped_response
        mock_llm_service.client.models.generate_content = Mock(return_value=mock_response)
        
        result = await mock_llm_service.summarize_content(sample_content)
        
        assert isinstance(result, StructuredSummary)
        assert result.title == mock_structured_response["title"]
        assert result.overview == mock_structured_response["overview"]
    
    @pytest.mark.asyncio
    async def test_generate_structured_summary_invalid_json(
        self, mock_llm_service, sample_content
    ):
        """Test handling of invalid JSON response."""
        # Mock invalid JSON response
        invalid_response = "This is not valid JSON"
        mock_response = Mock()
        mock_response.text = invalid_response
        mock_llm_service.client.models.generate_content = Mock(return_value=mock_response)
        
        result = await mock_llm_service.summarize_content(sample_content)
        
        # Should return None on error
        assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_structured_summary_content_truncation(
        self, mock_llm_service, mock_structured_response
    ):
        """Test that long content is truncated."""
        # Create very long content
        long_content = "x" * 20000
        
        mock_response = Mock()
        mock_response.text = json.dumps(mock_structured_response)
        mock_llm_service.client.models.generate_content = Mock(return_value=mock_response)
        
        await mock_llm_service.summarize_content(long_content)
        
        # Verify the content was truncated
        call_args = mock_llm_service.client.models.generate_content.call_args
        contents = call_args[1]["contents"]
        assert "x" * 15000 in contents
        assert "..." in contents
    
    @pytest.mark.asyncio
    async def test_summarize_content(
        self, mock_llm_service, sample_content, mock_structured_response
    ):
        """Test summarize_content returns structured summary."""
        mock_response = Mock()
        mock_response.text = json.dumps(mock_structured_response)
        mock_llm_service.client.models.generate_content = Mock(return_value=mock_response)
        
        result = await mock_llm_service.summarize_content(sample_content)
        
        assert isinstance(result, StructuredSummary)
        assert len(result.bullet_points) >= 3
    
    @pytest.mark.asyncio
    async def test_summarize_content_with_parameters(
        self, mock_llm_service, sample_content
    ):
        """Test summarize_content with custom parameters."""
        mock_response = {
            "title": "Comprehensive Test Analysis Reveals Key Insights",
            "overview": "This is a comprehensive test overview that provides detailed context about the content being summarized. It meets the minimum length requirement.",
            "bullet_points": [
                {"text": "First key finding from the analysis", "category": "key_finding"},
                {"text": "Important methodology used in the process", "category": "methodology"},
                {"text": "Significant conclusion drawn from the data", "category": "conclusion"}
            ],
            "quotes": [],
            "topics": ["Test", "Summary", "Analysis"]
        }
        mock_resp = Mock()
        mock_resp.text = json.dumps(mock_response)
        mock_llm_service.client.models.generate_content = Mock(return_value=mock_resp)
        
        result = await mock_llm_service.summarize_content(
            sample_content,
            max_bullet_points=3,
            max_quotes=2
        )
        
        # Should return StructuredSummary
        assert isinstance(result, StructuredSummary)
        assert len(result.overview) >= 50
        assert len(result.bullet_points) >= 3
    
    # Test removed - MockProvider no longer exists
    
    @pytest.mark.asyncio
    async def test_bullet_point_categories(
        self, mock_llm_service, sample_content
    ):
        """Test that bullet point categories are properly validated."""
        response_with_categories = {
            "title": "Research Study Reveals Key Findings and Future Recommendations",
            "overview": "This is a comprehensive test overview that meets the minimum length requirement for validation",
            "bullet_points": [
                {"text": "This is the first key finding from the research", "category": "key_finding"},
                {"text": "This describes the methodology used in the study", "category": "methodology"},
                {"text": "This is an important warning about the limitations", "category": "warning"},
                {"text": "This is a recommendation for future research", "category": "recommendation"}
            ],
            "quotes": [],
            "topics": ["Test"]
        }
        
        mock_response = Mock()
        mock_response.text = json.dumps(response_with_categories)
        mock_llm_service.client.models.generate_content = Mock(return_value=mock_response)
        
        result = await mock_llm_service.summarize_content(sample_content)
        
        assert isinstance(result, StructuredSummary)
        categories = [bp.category for bp in result.bullet_points]
        assert "key_finding" in categories
        assert "methodology" in categories
        assert "warning" in categories
        assert "recommendation" in categories