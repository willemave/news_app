"""
Verification tests for the JSON parsing fix.
Tests the exact error scenario from the logs to ensure it's resolved.
"""
import pytest
from unittest.mock import Mock, patch
import json
from app.llm import summarize_podcast_transcript, summarize_article, summarize_pdf
from app.schemas import ArticleSummary


class TestJSONParsingFixVerification:
    """Verification tests for the JSON parsing fixes."""

    def test_exact_log_error_scenario_podcast(self):
        """
        Test the exact error scenario from the logs:
        'JSON parsing error in summarize_podcast_transcript: Expecting ',' delimiter: line 3 column 1241 (char 1647)'
        """
        # This is the exact truncated response that caused the error
        exact_log_response = """{
  "short_summary": "The podcast discusses how major AI players like OpenAI are increasingly building features that compete directly with specialized startups, reigniting concerns about platform risk and the viability of smaller AI companies. It also explores evolving AI strategies, from Klarna's hybrid customer service model to AMD's efforts to foster an open AI ecosystem against Nvidia's dominance.",
  "detailed_summary": "• Klarna's AI transformation: blending AI and human customer service, ..."""
        
        mock_response = Mock()
        mock_response.text = exact_log_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Test podcast transcript about AI companies"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            # This should NOT raise an exception and should return a valid ArticleSummary
            result = summarize_podcast_transcript(test_transcript)
            
            # Verify we get a valid result
            assert isinstance(result, ArticleSummary)
            assert "AI players like OpenAI" in result.short_summary
            assert "platform risk" in result.short_summary
            assert "Klarna's AI transformation" in result.detailed_summary
            
            # Verify it's not an error message
            assert result.short_summary != "Error generating podcast summary"
            assert result.detailed_summary != "Error generating detailed podcast summary"

    def test_character_position_1647_truncation(self):
        """
        Test truncation at exactly character 1647 as mentioned in the error.
        """
        # Create a response that gets truncated at character 1647
        long_response = """{
  "short_summary": "This is a comprehensive podcast episode that covers multiple aspects of the artificial intelligence industry, including competitive dynamics between major tech companies and smaller specialized startups, platform risk considerations, and various strategic approaches to AI implementation across different business sectors.",
  "detailed_summary": "• Major AI companies like OpenAI are increasingly building features that directly compete with specialized AI startups, creating significant platform risk concerns for smaller companies in the ecosystem\\n• The discussion explores how this trend affects the viability and sustainability of AI startups that initially relied on these larger platforms for their foundational technology and infrastructure\\n• Klarna's innovative approach to customer service demonstrates a hybrid model that combines AI automation with human oversight, showing practical implementation strategies that balance efficiency with quality\\n• AMD's strategic efforts to foster an open AI ecosystem represent a significant challenge to Nvidia's dominant position in the AI hardware market, potentially reshaping competitive dynamics\\n• The conversation covers various business models and approaches to AI implementation, highlighting the importance of strategic thinking about platform dependencies\\n• Analysis of market trends, investment patterns, and the future outlook for AI companies of all sizes, emphasizing the need for sustainable competitive advantages\\n• Technical insights into AI development trends, regulatory considerations, and the role of open source in fostering innovation and competition\\n• Discussion of how companies can navigate the evolving AI landscape while building resilient business models that can withstand competitive pressures from larger tech giants\\n\\nThe podcast provides a comprehensive analysis of the current state of the AI industry, with particular focus on the tension between large technology companies and smaller specialized firms. The hosts examine how major players like OpenAI are expanding their offerings to include features that directly compete with startups, creating what many consider to be significant platform risk for entrepreneurs and investors in the AI space. This trend is particularly concerning because it suggests that successful AI startups may eventually face direct competition from the very platforms they initially relied upon for their core technology and infrastructure needs."""
        
        # Truncate at exactly character 1647
        truncated_at_1647 = long_response[:1647]
        
        mock_response = Mock()
        mock_response.text = truncated_at_1647
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Long podcast transcript that would generate a lengthy summary"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript(test_transcript)
            
            assert isinstance(result, ArticleSummary)
            # Should successfully extract content despite truncation
            assert len(result.short_summary) > 50
            assert len(result.detailed_summary) > 50
            assert "Error parsing" not in result.short_summary

    def test_all_summarization_functions_consistency(self):
        """
        Test that all summarization functions handle the same error consistently.
        """
        # Same malformed JSON for all functions
        malformed_json = """{
  "short_summary": "Test summary content"
  "detailed_summary": "• Test point 1\\n• Test point 2"""
        
        mock_response = Mock()
        mock_response.text = malformed_json
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            # Test podcast summarization
            podcast_result = summarize_podcast_transcript("test transcript")
            assert isinstance(podcast_result, ArticleSummary)
            assert "Test summary content" in podcast_result.short_summary
            
            # Test article summarization
            article_result = summarize_article("test article")
            assert isinstance(article_result, ArticleSummary)
            assert "Test summary content" in article_result.short_summary
            
            # Test PDF summarization
            pdf_result = summarize_pdf(b"test pdf content")
            assert isinstance(pdf_result, ArticleSummary)
            assert "Test summary content" in pdf_result.short_summary

    def test_pydantic_validation_error_handling(self):
        """
        Test that Pydantic validation errors are properly caught and handled.
        """
        # JSON with only one field (missing required field)
        incomplete_json = '{"short_summary": "Only short summary provided"}'
        
        mock_response = Mock()
        mock_response.text = incomplete_json
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript("test")
            
            assert isinstance(result, ArticleSummary)
            assert "Only short summary provided" in result.short_summary
            assert result.detailed_summary == "Error parsing detailed summary"

    def test_empty_and_whitespace_handling(self):
        """
        Test handling of empty or whitespace-only responses.
        """
        test_cases = [
            "",  # Empty string
            "   ",  # Whitespace only
            "{}",  # Empty JSON
            '{"short_summary": "", "detailed_summary": ""}',  # Empty fields
            '{"short_summary": "   ", "detailed_summary": "   "}',  # Whitespace fields
        ]
        
        for test_response in test_cases:
            mock_response = Mock()
            mock_response.text = test_response
            
            mock_client = Mock()
            mock_generate_content = Mock(return_value=mock_response)
            mock_client.models.generate_content = mock_generate_content
            
            with patch('app.llm.genai.Client', return_value=mock_client):
                result = summarize_podcast_transcript("test")
                
                assert isinstance(result, ArticleSummary)
                # Should fall back to error messages for empty/whitespace content
                assert result.short_summary == "Error parsing summary"
                assert result.detailed_summary == "Error parsing detailed summary"

    def test_logging_improvements(self):
        """
        Test that the improved logging provides full response text instead of truncated.
        """
        malformed_json = '{"short_summary": "test", invalid_json}'
        
        mock_response = Mock()
        mock_response.text = malformed_json
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            with patch('builtins.print') as mock_print:
                result = summarize_podcast_transcript("test")
                
                # Verify that full response text is logged (not truncated)
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                response_logged = any(malformed_json in call for call in print_calls)
                assert response_logged, "Full response text should be logged"
                
                assert isinstance(result, ArticleSummary)