"""
Test to reproduce JSON parsing error in summarize_article function.

This test reproduces the specific error seen in logs:
"JSON parsing error in summarize_article: Expecting ',' delimiter: line 4 column 1 (char 3526)"
"""
import pytest
from unittest.mock import Mock, patch
import json
from app.llm import summarize_article
from app.schemas import ArticleSummary


class TestLLMJSONParsingError:
    """Test cases for reproducing JSON parsing errors in LLM functions."""

    def test_summarize_article_truncated_json_response(self):
        """
        Test that reproduces the JSON parsing error when the LLM response is truncated.
        
        This simulates the exact error from the logs where the detailed_summary field
        is cut off mid-sentence, causing a JSON parsing error.
        """
        # Create a truncated JSON response that matches the error from logs
        truncated_response = """{
  "short_summary": "The article challenges the pervasive assumption that AI safety is an intrinsic property of models, arguing instead that it depends heavily on the context and environment of deployment. This implies that current safety efforts, focused solely on model alignment and red teaming, are inherently limited and often ineffective against misuse.",
  "detailed_summary": "• The widespread but flawed assumption that AI safety is an intrinsic property of AI models.\\n• AI safety is large"""
        
        # Mock the Google Generative AI client and response
        mock_response = Mock()
        mock_response.text = truncated_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        # Test content that would trigger the summarization
        test_content = "This is a test article about AI safety and model properties."
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            # This should trigger the JSON parsing error and fallback to malformed response parsing
            result = summarize_article(test_content)
            
            # Verify that we get a result despite the JSON error
            assert isinstance(result, ArticleSummary)
            
            # The fallback parser should extract the short_summary successfully
            assert "AI safety is an intrinsic property of models" in result.short_summary
            
            # The detailed_summary should be extracted from the truncated response
            assert "AI safety is large" in result.detailed_summary or result.detailed_summary == "Error parsing detailed summary"

    def test_summarize_article_malformed_json_missing_comma(self):
        """
        Test JSON parsing error when comma is missing between fields.
        """
        # JSON missing comma between fields
        malformed_response = """{
  "short_summary": "This is a short summary"
  "detailed_summary": "• Key point 1\\n• Key point 2\\n\\nDetailed analysis follows."
}"""
        
        mock_response = Mock()
        mock_response.text = malformed_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_content = "Test article content"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_article(test_content)
            
            assert isinstance(result, ArticleSummary)
            # Should fall back to regex parsing and extract the summaries
            assert "This is a short summary" in result.short_summary
            assert "Key point 1" in result.detailed_summary

    def test_summarize_article_json_with_unescaped_quotes(self):
        """
        Test JSON parsing error when response contains unescaped quotes.
        """
        # JSON with unescaped quotes that would break parsing
        malformed_response = """{
  "short_summary": "The article discusses "AI safety" and its implications.",
  "detailed_summary": "• Point about "model alignment"\\n• Discussion of "red teaming" approaches"
}"""
        
        mock_response = Mock()
        mock_response.text = malformed_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_content = "Test article content"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_article(test_content)
            
            assert isinstance(result, ArticleSummary)
            # Should handle the parsing error gracefully
            assert len(result.short_summary) > 0
            assert len(result.detailed_summary) > 0

    def test_summarize_article_completely_invalid_json(self):
        """
        Test behavior when response is completely invalid JSON.
        """
        invalid_response = "This is not JSON at all, just plain text response from the LLM."
        
        mock_response = Mock()
        mock_response.text = invalid_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_content = "Test article content"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_article(test_content)
            
            assert isinstance(result, ArticleSummary)
            # Should fall back to error messages
            assert result.short_summary == "Error parsing summary"
            assert result.detailed_summary == "Error parsing detailed summary"

    def test_summarize_article_json_with_escaped_newlines(self):
        """
        Test that properly escaped JSON with newlines works correctly.
        """
        # Properly formatted JSON with escaped newlines
        valid_response = """{
  "short_summary": "This is a proper short summary of the article.",
  "detailed_summary": "• First key point\\n• Second key point\\n• Third key point\\n\\nThis is the detailed analysis that follows the bullet points."
}"""
        
        mock_response = Mock()
        mock_response.text = valid_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_content = "Test article content"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_article(test_content)
            
            assert isinstance(result, ArticleSummary)
            assert result.short_summary == "This is a proper short summary of the article."
            assert "First key point" in result.detailed_summary
            assert "detailed analysis" in result.detailed_summary

    def test_fallback_parser_with_exact_log_response(self):
        """
        Test the fallback parser with the exact truncated response from the logs.
        """
        from app.llm import _parse_malformed_summary_response
        
        # Exact response from the error logs
        log_response = """{
  "short_summary": "The article challenges the pervasive assumption that AI safety is an intrinsic property of models, arguing instead that it depends heavily on the context and environment of deployment. This implies that current safety efforts, focused solely on model alignment and red teaming, are inherently limited and often ineffective against misuse.",
  "detailed_summary": "• The widespread but flawed assumption that AI safety is an intrinsic property of AI models.\\n• AI safety is large"""
        
        result = _parse_malformed_summary_response(log_response)
        
        assert isinstance(result, ArticleSummary)
        assert "AI safety is an intrinsic property of models" in result.short_summary
        assert "AI safety is large" in result.detailed_summary