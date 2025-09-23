"""Tests for structured summarization in OpenAI LLM service."""
from unittest.mock import Mock, patch

import pytest
from openai import OpenAIError

from app.models.metadata import NewsSummary, StructuredSummary
from app.services.openai_llm import OpenAISummarizationService


class TestOpenAIStructuredSummarization:
    """Test structured summarization functionality."""
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create LLM service with mocked OpenAI client."""
        with patch('app.services.openai_llm.get_settings') as mock_settings:
            mock_settings.return_value.openai_api_key = 'test-key'
            with patch('app.services.openai_llm.OpenAI'):
                service = OpenAISummarizationService()
                service.client = Mock()
                service.client.responses = Mock()
                service.client.responses.parse = Mock()
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
                {"text": "AI model achieves 95% accuracy in code generation tasks", "category": "key_finding"},
                {"text": "Model demonstrates understanding of complex programming concepts", "category": "methodology"},
                {"text": "Development time reduced by 40% in testing scenarios", "category": "conclusion"}
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
            "topics": ["AI", "Software Development", "Research", "Stanford"],
            "classification": "to_read",
            "full_markdown": "# Stanford AI Research\n\nContent here..."
        }
    
    def test_generate_structured_summary_success(
        self, mock_llm_service, sample_content, mock_structured_response
    ):
        """Test successful generation of structured summary."""
        # Mock the OpenAI client's response
        structured = StructuredSummary(**mock_structured_response)
        mock_response = Mock()
        mock_response.output = [Mock()]
        mock_response.output_parsed = structured
        mock_llm_service.client.responses.parse.return_value = mock_response

        result = mock_llm_service.summarize_content(sample_content)

        # Verify result is a StructuredSummary
        assert isinstance(result, StructuredSummary)
        assert result.title == mock_structured_response["title"]
        assert result.overview == mock_structured_response["overview"]
        assert len(result.bullet_points) == 3
        assert len(result.quotes) == 2
        assert len(result.topics) == 4
        assert result.classification == "to_read"
        assert result.full_markdown == "# Stanford AI Research\n\nContent here..."
        
        # Verify bullet points
        assert result.bullet_points[0].text == mock_structured_response["bullet_points"][0]["text"]
        
        # Verify quotes
        assert result.quotes[0].text == mock_structured_response["quotes"][0]["text"]
        assert result.quotes[0].context == "Dr. Jane Smith, lead researcher"
        # Verify quotes are longer (2-3 sentences)
        assert len(result.quotes[0].text) > 100  # Ensuring meaningful length
    
    def test_generate_structured_summary_with_json_markdown(
        self, mock_llm_service, sample_content, mock_structured_response
    ):
        """Test handling of JSON wrapped in markdown code blocks."""
        # Mock response with markdown code blocks
        structured = StructuredSummary(**mock_structured_response)
        mock_response = Mock()
        mock_response.output = [Mock()]
        mock_response.output_parsed = structured
        mock_llm_service.client.responses.parse.return_value = mock_response
        
        result = mock_llm_service.summarize_content(sample_content)
        
        assert isinstance(result, StructuredSummary)
        assert result.title == mock_structured_response["title"]
        assert result.overview == mock_structured_response["overview"]

    def test_generate_structured_summary_invalid_json(
        self, mock_llm_service, sample_content
    ):
        """Test handling of invalid JSON response."""
        # Mock invalid JSON response
        invalid_response = "This is not valid JSON"
        mock_llm_service.client.responses.parse.side_effect = OpenAIError(invalid_response)

        result = mock_llm_service.summarize_content(sample_content)

        assert result is None
        mock_llm_service.client.responses.parse.side_effect = None
    
    def test_summarize_content(
        self, mock_llm_service, sample_content, mock_structured_response
    ):
        """Test summarize_content returns structured summary."""
        structured = StructuredSummary(**mock_structured_response)
        mock_response = Mock()
        mock_response.output = [Mock()]
        mock_response.output_parsed = structured
        mock_llm_service.client.responses.parse.return_value = mock_response
        
        result = mock_llm_service.summarize_content(sample_content)
        
        assert isinstance(result, StructuredSummary)
        assert len(result.bullet_points) >= 3

    def test_news_digest_summary(
        self, mock_llm_service
    ):
        """Ensure news digest requests return NewsSummary objects."""
        news_payload = {
            "title": "TechMeme: EU backs landmark AI audit rules",
            "article_url": "https://example.com/eu-ai-audit-rules",
            "key_points": [
                "EU regulators approve binding AI audit framework with phased rollout",
                "Compliance obligations begin Q1 2026 for frontier model providers",
                "Framework mandates independent model evaluations and public reporting",
            ],
            "summary": "EU lawmakers approve a binding audit regime for high-risk AI systems, forcing major vendors to submit to independent evaluations starting in 2026.",
            "classification": "to_read",
        }
        news_summary = NewsSummary(**news_payload)
        mock_response = Mock()
        mock_response.output = [Mock()]
        mock_response.output_parsed = news_summary
        mock_llm_service.client.responses.parse.return_value = mock_response

        result = mock_llm_service.summarize_content(
            "Article Content", content_type="news_digest", max_bullet_points=4, max_quotes=0
        )

        assert isinstance(result, NewsSummary)
        assert result.title == news_payload["title"]
        assert str(result.article_url) == news_payload["article_url"]
        assert len(result.key_points) == 3
    
    def test_summarize_content_with_parameters(
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
            "topics": ["Test", "Summary", "Analysis"],
            "classification": "to_read",
            "full_markdown": ""
        }
        structured = StructuredSummary(**mock_response)
        mock_resp = Mock()
        mock_resp.output = [Mock()]
        mock_resp.output_parsed = structured
        mock_llm_service.client.responses.parse.return_value = mock_resp
        
        result = mock_llm_service.summarize_content(
            sample_content,
            max_bullet_points=3,
            max_quotes=2
        )
        
        # Should return StructuredSummary
        assert isinstance(result, StructuredSummary)
        assert len(result.overview) >= 50
        assert len(result.bullet_points) >= 3
    
    def test_podcast_content_type(
        self, mock_llm_service, sample_content
    ):
        """Test that podcast content type uses different prompt and token limit."""
        mock_response = {
            "title": "Test Podcast Title",
            "overview": "This is a comprehensive podcast overview that meets the minimum length requirement.",
            "bullet_points": [{"text": "First key point from the podcast"}, {"text": "Second important insight"}, {"text": "Third significant discussion topic"}],
            "quotes": [],
            "topics": ["Podcast", "Test"],
            "classification": "to_read",
            "full_markdown": ""
        }
        
        structured = StructuredSummary(**mock_response)
        mock_resp = Mock()
        mock_resp.output = [Mock()]
        mock_resp.output_parsed = structured

        parse_mock = mock_llm_service.client.responses.parse
        parse_mock.return_value = mock_resp

        result = mock_llm_service.summarize_content(
            sample_content,
            content_type="podcast"
        )

        # Verify podcast-specific handling
        assert isinstance(result, StructuredSummary)
        call_kwargs = parse_mock.call_args.kwargs
        assert call_kwargs['max_output_tokens'] == 8000
        
        # Check that the prompt mentions podcast
        messages = call_kwargs['input']
        user_message = next((m for m in messages if m['role'] == 'user'), None)
        assert user_message is not None
        assert 'podcast' in user_message['content'].lower()
    
    def test_hackernews_content_type(
        self, mock_llm_service, sample_content
    ):
        """Test that HackerNews content type uses specific prompt."""
        mock_response = {
            "title": "Test HackerNews Title",
            "overview": "This is a comprehensive HackerNews discussion overview that meets the minimum length requirement.",
            "bullet_points": [{"text": "First key point from the podcast"}, {"text": "Second important insight"}, {"text": "Third significant discussion topic"}],
            "quotes": [{"text": "HN user comment", "context": "HN user [username]"}],
            "topics": ["HackerNews", "Discussion"],
            "classification": "to_read",
            "full_markdown": "Article and comments"
        }
        
        structured = StructuredSummary(**mock_response)
        mock_resp = Mock()
        mock_resp.output = [Mock()]
        mock_resp.output_parsed = structured

        parse_mock = mock_llm_service.client.responses.parse
        parse_mock.return_value = mock_resp
        
        result = mock_llm_service.summarize_content(
            sample_content,
            content_type="hackernews"
        )
        
        # Verify HackerNews-specific handling
        assert isinstance(result, StructuredSummary)

        messages = parse_mock.call_args.kwargs['input']
        user_message = next((m for m in messages if m['role'] == 'user'), None)
        assert user_message is not None
        assert 'hackernews' in user_message['content'].lower()
        assert 'discussion' in user_message['content'].lower()
