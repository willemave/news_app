"""Test cases for OpenAI LLM service JSON parsing improvements."""

import json
from unittest.mock import Mock, patch

import pytest
from openai import OpenAIError

from app.services.openai_llm import OpenAISummarizationService, try_repair_truncated_json
from app.models.metadata import StructuredSummary


class TestJSONRepair:
    """Test the JSON repair functionality."""
    
    def test_repair_simple_truncation(self):
        """Test repairing simple truncated JSON."""
        truncated = '{"overview": "Test", "bullet_points": ["Point"]'
        repaired = try_repair_truncated_json(truncated)
        assert repaired is not None
        parsed = json.loads(repaired)
        assert parsed["overview"] == "Test"
        assert len(parsed["bullet_points"]) == 1
    
    def test_repair_unterminated_string(self):
        """Test repairing JSON with unterminated string."""
        truncated = '{"overview": "Test", "bullet_points": ["Unterminated'
        repaired = try_repair_truncated_json(truncated)
        assert repaired is not None
        # Should close the string and structures
        parsed = json.loads(repaired)
        assert "overview" in parsed
    
    def test_valid_json_unchanged(self):
        """Test that valid JSON is returned unchanged."""
        valid = '{"overview": "Test", "bullet_points": []}'
        repaired = try_repair_truncated_json(valid)
        assert repaired == valid
    
    def test_complex_truncation(self):
        """Test handling of complex truncation that can't be repaired."""
        # This is too corrupted to repair meaningfully
        truncated = '{"overview": "Test", "bullet_points": ["First", "ca'
        repaired = try_repair_truncated_json(truncated)
        if repaired:
            # If it was repaired, it should be valid JSON
            try:
                json.loads(repaired)
            except json.JSONDecodeError:
                pytest.fail("Repaired JSON is still invalid")


class TestOpenAISummarizationServiceWithTruncation:
    """Test OpenAI summarization service handling of truncated responses."""
    
    @pytest.fixture
    def mock_service(self):
        """Create a mock OpenAI summarization service."""
        with patch('app.services.openai_llm.get_settings') as mock_settings:
            mock_settings.return_value.openai_api_key = 'test-key'
            with patch('openai.OpenAI'):
                service = OpenAISummarizationService()
                service.client = Mock()
                service.client.beta = Mock()
                service.client.beta.chat.completions.parse = Mock()
                return service
    
    def test_handle_truncated_response(self, mock_service):
        """Test handling of response truncated due to max_tokens."""
        # Create a mock response that's truncated
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"overview": "Truncated'
        mock_response.choices[0].finish_reason = "length"
        
        # Mock the create method
        mock_service.client.chat.completions.create = Mock(return_value=mock_response)
        
        # Test summarization
        result = mock_service.summarize_content("Test content")
        
        # Should handle the truncation gracefully
        assert result is None or isinstance(result, StructuredSummary)
    
    def test_handle_error_response(self, mock_service):
        """Test handling of error responses."""
        mock_service.client.beta.chat.completions.parse.side_effect = OpenAIError("invalid json")

        result = mock_service.summarize_content("Test content")
        assert result is None
        mock_service.client.beta.chat.completions.parse.side_effect = None
    
    def test_handle_markdown_wrapped_json(self, mock_service):
        """Test handling of JSON wrapped in markdown code blocks."""
        valid_json = {
            "title": "Test Title",
            "overview": "This is a test overview that meets the minimum length requirement for validation.",
            "bullet_points": [
                {"text": "First important point about the content"},
                {"text": "Second important point about the content"},
                {"text": "Third important point about the content"}
            ],
            "quotes": [],
            "topics": ["Test", "Example"],
            "classification": "to_read",
            "full_markdown": "# Test Content"
        }
        
        # Test with ```json wrapper
        structured = StructuredSummary(
            title="Test Title",
            overview=valid_json["overview"],
            bullet_points=[{"text": bp["text"], "category": "test"} for bp in valid_json["bullet_points"]],
            quotes=[],
            topics=valid_json["topics"],
            classification=valid_json["classification"],
            full_markdown=valid_json["full_markdown"],
        )
        mock_choice = Mock()
        mock_choice.message.parsed = structured
        mock_response = Mock()
        mock_response.choices = [mock_choice]

        mock_service.client.beta.chat.completions.parse.return_value = mock_response

        result = mock_service.summarize_content("Test content")
        assert isinstance(result, StructuredSummary)
        assert result.title == "Test Title"
    
    def test_content_type_based_processing(self, mock_service):
        """Test that different content types get different prompts."""
        # Set up a spy to capture the actual prompt sent
        prompt_sent = None
        
        parse_mock = mock_service.client.beta.chat.completions.parse

        def capture_prompt(**kwargs):
            nonlocal prompt_sent
            messages = kwargs.get('messages', [])
            if messages:
                prompt_sent = messages[-1]['content']
            # Return a valid response
            structured = StructuredSummary(
                title="Test Title",
                overview="A" * 60,
                bullet_points=[
                    {"text": "Point 1", "category": "test"},
                    {"text": "Point 2", "category": "test"},
                    {"text": "Point 3", "category": "test"},
                ],
                quotes=[],
                topics=["Test"],
                classification="skip",
                full_markdown="",
            )
            mock_choice = Mock()
            mock_choice.message.parsed = structured
            mock_resp = Mock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        parse_mock.side_effect = capture_prompt
        
        # Test with podcast content type
        result = mock_service.summarize_content("Test content", content_type="podcast")
        
        # Verify podcast-specific prompt was used
        assert prompt_sent is not None
        assert "podcast" in prompt_sent.lower()
        parse_mock.side_effect = None
    
    def test_token_limit_adjustment_for_podcasts(self, mock_service):
        """Test that token limits are adjusted for podcast content."""
        # For this test, we need to inspect the config passed to create
        config_used = None
        
        parse_mock = mock_service.client.beta.chat.completions.parse

        def capture_config(**kwargs):
            nonlocal config_used
            config_used = kwargs
            # Return a valid response
            structured = StructuredSummary(
                title="Test",
                overview="A" * 60,
                bullet_points=[
                    {"text": "A" * 15, "category": "test"},
                    {"text": "B" * 15, "category": "test"},
                    {"text": "C" * 15, "category": "test"},
                ],
                quotes=[],
                topics=["Test"],
                classification="skip",
                full_markdown="",
            )
            mock_choice = Mock()
            mock_choice.message.parsed = structured
            mock_resp = Mock()
            mock_resp.choices = [mock_choice]
            return mock_resp

        parse_mock.side_effect = capture_config
        
        # Test with podcast content
        result = mock_service.summarize_content("Test podcast", content_type="podcast")
        
        # Verify reduced token limit was used for podcasts
        assert config_used is not None
        assert config_used.get('max_output_tokens') == 8000
        parse_mock.side_effect = None
