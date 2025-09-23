"""Test cases for Google Flash service JSON parsing improvements."""

import json
from unittest.mock import Mock, patch

import pytest

from app.models.metadata import StructuredSummary
from app.services.google_flash import GoogleFlashService
from app.utils.json_repair import try_repair_truncated_json


class TestJSONRepair:
    """Test the JSON repair functionality."""
    
    def test_repair_simple_truncation(self):
        """Test repairing simple truncated JSON."""
        truncated = '{"overview": "Test", "bullet_points": [{"text": "Point"}'
        repaired = try_repair_truncated_json(truncated)
        assert repaired is not None
        parsed = json.loads(repaired)
        assert parsed["overview"] == "Test"
        assert len(parsed["bullet_points"]) == 1
    
    def test_repair_unterminated_string(self):
        """Test repairing JSON with unterminated string."""
        truncated = '{"overview": "Test", "bullet_points": [{"text": "Unterminated'
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
        truncated = '{"overview": "Test", "bullet_points": [{"text": "First", "ca'
        repaired = try_repair_truncated_json(truncated)
        if repaired:
            # If it was repaired, it should be valid JSON
            try:
                json.loads(repaired)
            except json.JSONDecodeError:
                pytest.fail("Repaired JSON is still invalid")


class TestGoogleFlashServiceWithTruncation:
    """Test Google Flash service handling of truncated responses."""
    
    @pytest.fixture
    def mock_service(self):
        """Create a mock Google Flash service."""
        with patch('app.services.google_flash.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = 'test-key'
            with patch('google.genai.Client'):
                service = GoogleFlashService()
                service.client = Mock()
                return service
    
    def test_handle_max_tokens_response(self, mock_service):
        """Test handling of response truncated due to MAX_TOKENS."""
        # Create a mock response that indicates MAX_TOKENS truncation
        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].finish_reason = "FinishReason.MAX_TOKENS"
        mock_response.candidates[0].content.parts = [Mock(text='{"overview": "Truncated')]
        
        # Mock the generate_content method
        mock_service.client.models.generate_content = Mock(return_value=mock_response)
        
        # Test synchronous version
        result = mock_service.summarize_content("Test content")
        
        # Should handle the truncation gracefully
        assert result is None or isinstance(result, StructuredSummary)
    
    def test_handle_error_response(self, mock_service):
        """Test handling of error responses like 'This is not valid JSON'."""
        mock_response = Mock()
        mock_response.text = "This is not valid JSON"
        mock_response.candidates = []
        
        mock_service.client.models.generate_content = Mock(return_value=mock_response)
        
        result = mock_service.summarize_content("Test content")
        assert result is None
    
    def test_handle_markdown_wrapped_json(self, mock_service):
        """Test handling of JSON wrapped in markdown code blocks."""
        valid_json = {
            "title": "Test Title",
            "overview": "This is a test overview that meets the minimum length requirement for validation.",
            "bullet_points": [
                {"text": "First important point about the content", "category": "key_finding"},
                {"text": "Second important point about the content", "category": "methodology"},
                {"text": "Third important point about the content", "category": "conclusion"}
            ],
            "quotes": [],
            "topics": ["Test", "Example"],
            "classification": "to_read",
            "full_markdown": ""
        }
        
        # Test with ```json wrapper
        mock_response = Mock()
        mock_response.text = f"```json\n{json.dumps(valid_json)}\n```"
        mock_response.candidates = []
        
        mock_service.client.models.generate_content = Mock(return_value=mock_response)
        
        result = mock_service.summarize_content("Test content")
        assert isinstance(result, StructuredSummary)
        assert result.title == "Test Title"
    
    def test_content_length_based_truncation(self, mock_service):
        """Test that very long content is truncated more aggressively."""
        # Create very long content
        very_long_content = "A" * 60000
        
        # Set up a spy to capture the actual prompt sent
        prompt_sent = None
        
        def capture_prompt(**kwargs):
            nonlocal prompt_sent
            prompt_sent = kwargs.get('contents', '')
            # Return a valid response
            mock_resp = Mock()
            mock_resp.text = json.dumps({
                "title": "Test Title",
                "overview": "A" * 60,
                "bullet_points": [
                    {"text": "Point 1" + "A" * 10, "category": "test"},
                    {"text": "Point 2" + "A" * 10, "category": "test"},
                    {"text": "Point 3" + "A" * 10, "category": "test"}
                ],
                "quotes": [],
                "topics": ["Test"],
                "classification": "skip",
                "full_markdown": ""
            })
            mock_resp.candidates = []
            return mock_resp
        
        mock_service.client.models.generate_content = Mock(side_effect=capture_prompt)
        
        result = mock_service.summarize_content(very_long_content)
        
        # Verify content was truncated
        assert prompt_sent is not None
        assert "..." in prompt_sent
        assert len(prompt_sent) < len(very_long_content)
    
    def test_token_limit_adjustment(self, mock_service):
        """Test that token limits are adjusted for long content."""
        # For this test, we need to inspect the config passed to generate_content
        config_used = None
        
        def capture_config(**kwargs):
            nonlocal config_used
            config_used = kwargs.get('config', {})
            # Return a valid response
            mock_resp = Mock()
            mock_resp.text = json.dumps({
                "title": "Test",
                "overview": "A" * 60,
                "bullet_points": [
                    {"text": "A" * 15, "category": "test"},
                    {"text": "B" * 15, "category": "test"},
                    {"text": "C" * 15, "category": "test"}
                ],
                "quotes": [],
                "topics": ["Test"],
                "classification": "skip",
                "full_markdown": ""
            })
            mock_resp.candidates = []
            return mock_resp
        
        mock_service.client.models.generate_content = Mock(side_effect=capture_config)
        
        # Test with long content
        long_content = "X" * 15000
        result = mock_service.summarize_content(long_content)
        
        # Verify reduced token limit was used
        assert config_used is not None
        assert config_used.get('max_output_tokens', 50000) < 50000
