"""
Test to reproduce and fix JSON parsing errors in podcast summarization.

This test reproduces the specific error seen in logs:
"JSON parsing error in summarize_podcast_transcript: Expecting ',' delimiter: line 3 column 1241 (char 1647)"
"""
from unittest.mock import Mock, patch
from app.llm import summarize_podcast_transcript, _parse_malformed_summary_response
from app.schemas import ArticleSummary


class TestPodcastSummarizationJSONErrors:
    """Test cases for reproducing JSON parsing errors in podcast summarization."""

    def test_summarize_podcast_transcript_truncated_json_response(self):
        """
        Test that reproduces the JSON parsing error when the LLM response is truncated.
        
        This simulates the exact error from the logs where the detailed_summary field
        is cut off mid-sentence, causing a JSON parsing error.
        """
        # Create a truncated JSON response that matches the error from logs
        truncated_response = """{
  "short_summary": "The podcast discusses how major AI players like OpenAI are increasingly building features that compete directly with specialized startups, reigniting concerns about platform risk and the viability of smaller AI companies. It also explores evolving AI strategies, from Klarna's hybrid customer service model to AMD's efforts to foster an open AI ecosystem against Nvidia's dominance.",
  "detailed_summary": "• Klarna's AI transformation: blending AI and human customer service, ..."""
        
        # Mock the Google Generative AI client and response
        mock_response = Mock()
        mock_response.text = truncated_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        # Test content that would trigger the summarization
        test_transcript = "This is a test podcast transcript about AI companies and platform risk."
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            # This should trigger the JSON parsing error and fallback to malformed response parsing
            result = summarize_podcast_transcript(test_transcript)
            
            # Verify that we get a result despite the JSON error
            assert isinstance(result, ArticleSummary)
            
            # The fallback parser should extract the short_summary successfully
            assert "AI players like OpenAI" in result.short_summary
            
            # The detailed_summary should be extracted from the truncated response
            assert "Klarna's AI transformation" in result.detailed_summary or result.detailed_summary == "Error parsing detailed summary"

    def test_summarize_podcast_transcript_malformed_json_missing_comma(self):
        """
        Test JSON parsing error when comma is missing between fields.
        """
        # JSON missing comma between fields
        malformed_response = """{
  "short_summary": "This podcast covers AI developments and industry trends"
  "detailed_summary": "• AI company strategies\\n• Platform risk concerns\\n\\nDetailed discussion of market dynamics."
}"""
        
        mock_response = Mock()
        mock_response.text = malformed_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Test podcast transcript content"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript(test_transcript)
            
            assert isinstance(result, ArticleSummary)
            # Should fall back to regex parsing and extract the summaries
            assert "AI developments and industry trends" in result.short_summary
            assert "AI company strategies" in result.detailed_summary

    def test_summarize_podcast_transcript_json_with_unescaped_quotes(self):
        """
        Test JSON parsing error when response contains unescaped quotes.
        """
        # JSON with unescaped quotes that would break parsing
        malformed_response = """{
  "short_summary": "The podcast discusses "platform risk" and its implications for startups.",
  "detailed_summary": "• Discussion of "AI competition"\\n• Analysis of "market dynamics" in tech"
}"""
        
        mock_response = Mock()
        mock_response.text = malformed_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Test podcast transcript content"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript(test_transcript)
            
            assert isinstance(result, ArticleSummary)
            # Should handle the parsing error gracefully
            assert len(result.short_summary) > 0
            assert len(result.detailed_summary) > 0

    def test_summarize_podcast_transcript_completely_invalid_json(self):
        """
        Test behavior when response is completely invalid JSON.
        """
        invalid_response = "This is not JSON at all, just plain text response from the LLM about a podcast."
        
        mock_response = Mock()
        mock_response.text = invalid_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Test podcast transcript content"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript(test_transcript)
            
            assert isinstance(result, ArticleSummary)
            # Should fall back to error messages
            assert result.short_summary == "Error parsing summary"
            assert result.detailed_summary == "Error parsing detailed summary"

    def test_summarize_podcast_transcript_json_with_escaped_newlines(self):
        """
        Test that properly escaped JSON with newlines works correctly.
        """
        # Properly formatted JSON with escaped newlines
        valid_response = """{
  "short_summary": "This is a proper short summary of the podcast episode.",
  "detailed_summary": "• First key topic discussed\\n• Second key topic covered\\n• Third important point\\n\\nThis is the detailed analysis that follows the bullet points and provides deeper insights into the podcast content."
}"""
        
        mock_response = Mock()
        mock_response.text = valid_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Test podcast transcript content"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript(test_transcript)
            
            assert isinstance(result, ArticleSummary)
            assert result.short_summary == "This is a proper short summary of the podcast episode."
            assert "First key topic discussed" in result.detailed_summary
            assert "detailed analysis" in result.detailed_summary

    def test_summarize_podcast_transcript_very_long_response_truncation(self):
        """
        Test handling of very long responses that might get truncated by the LLM service.
        """
        # Simulate a response that gets cut off mid-JSON due to length limits
        very_long_response = """{
  "short_summary": "This podcast episode covers a comprehensive analysis of the current state of artificial intelligence development, including discussions about major tech companies, startup ecosystems, platform risks, and the evolving competitive landscape in the AI industry.",
  "detailed_summary": "• Major AI companies like OpenAI are building features that directly compete with specialized startups\\n• Platform risk concerns are growing as big tech companies expand their AI offerings\\n• Klarna's hybrid approach to AI customer service demonstrates practical implementation strategies\\n• AMD is working to create an open AI ecosystem to challenge Nvidia's market dominance\\n• The discussion covers market dynamics, competitive strategies, and the future of AI development\\n• Analysis of how smaller AI companies can survive in an increasingly competitive landscape\\n• Exploration of different business models and approaches to AI implementation\\n• Technical insights into AI development trends and industry best practices\\n• Discussion of regulatory considerations and their impact on AI development\\n• Examination of the role of open source in AI development and competition\\n\\nThe podcast provides a comprehensive overview of the current AI landscape, highlighting the tension between large tech companies and smaller specialized firms. The hosts discuss how major players like OpenAI are increasingly building features that directly compete with startups, creating significant platform risk for smaller companies. This trend is particularly concerning for entrepreneurs and investors in the AI space, as it suggests that successful AI startups may face direct competition from the very platforms they initially relied upon.\\n\\nThe conversation also explores Klarna's innovative approach to customer service, which blends AI automation with human oversight. This hybrid model demonstrates how companies can implement AI solutions while maintaining quality and customer satisfaction. The discussion reveals that this approach has been successful in reducing costs while improving service quality, providing a practical example of effective AI implementation.\\n\\nAdditionally, the podcast covers AMD's strategic efforts to foster an open AI ecosystem as an alternative to Nvidia's dominant position in the AI hardware market. This initiative represents a significant challenge to Nvidia's market leadership and could reshape the competitive dynamics in AI infrastructure. The hosts analyze the potential impact of this competition on AI development costs and accessibility.\\n\\nThe episode concludes with a broader discussion of market trends, investment patterns, and the future outlook for AI companies of all sizes. The hosts emphasize the importance of understanding these dynamics for anyone involved in the AI industry, whether as entrepreneurs, investors, or technology professionals. They highlight the need for strategic thinking about platform dependencies and the importance of building sustainable competitive advantages in an rapidly evolving market"""
        
        # Truncate the response mid-sentence to simulate the actual error
        truncated_at_char_1647 = very_long_response[:1647]
        
        mock_response = Mock()
        mock_response.text = truncated_at_char_1647
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Very long podcast transcript that would generate a lengthy summary..."
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript(test_transcript)
            
            assert isinstance(result, ArticleSummary)
            # Should handle truncation gracefully
            assert len(result.short_summary) > 0
            assert len(result.detailed_summary) > 0
            # Should not contain error messages if fallback parsing works
            assert "Error parsing" not in result.short_summary

    def test_fallback_parser_with_exact_podcast_log_response(self):
        """
        Test the fallback parser with the exact truncated response from the podcast logs.
        """
        # Exact response from the error logs
        log_response = """{
  "short_summary": "The podcast discusses how major AI players like OpenAI are increasingly building features that compete directly with specialized startups, reigniting concerns about platform risk and the viability of smaller AI companies. It also explores evolving AI strategies, from Klarna's hybrid customer service model to AMD's efforts to foster an open AI ecosystem against Nvidia's dominance.",
  "detailed_summary": "• Klarna's AI transformation: blending AI and human customer service, ..."""
        
        result = _parse_malformed_summary_response(log_response)
        
        assert isinstance(result, ArticleSummary)
        assert "AI players like OpenAI" in result.short_summary
        assert "platform risk" in result.short_summary
        assert "Klarna's AI transformation" in result.detailed_summary

    def test_summarize_podcast_transcript_with_special_characters(self):
        """
        Test handling of special characters that might break JSON parsing.
        """
        # Response with various special characters that could cause issues
        response_with_special_chars = """{
  "short_summary": "The podcast discusses AI's impact on society, including "ethical considerations" and the role of AI in decision-making processes.",
  "detailed_summary": "• AI ethics and societal impact\\n• Decision-making algorithms & their biases\\n• The future of human-AI collaboration\\n• Regulatory frameworks (current & proposed)\\n\\nThe discussion covers how AI systems are increasingly being used in critical decision-making processes, from hiring to healthcare. The hosts explore the ethical implications of these systems and discuss various approaches to ensuring fairness and transparency. They also examine current regulatory proposals and their potential impact on AI development."
}"""
        
        mock_response = Mock()
        mock_response.text = response_with_special_chars
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Podcast transcript with discussion of AI ethics and regulation"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript(test_transcript)
            
            assert isinstance(result, ArticleSummary)
            assert "AI's impact on society" in result.short_summary
            assert "AI ethics" in result.detailed_summary

    def test_summarize_podcast_transcript_empty_response(self):
        """
        Test handling of empty or minimal responses.
        """
        empty_response = ""
        
        mock_response = Mock()
        mock_response.text = empty_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Test podcast transcript"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript(test_transcript)
            
            assert isinstance(result, ArticleSummary)
            assert result.short_summary == "Error parsing summary"
            assert result.detailed_summary == "Error parsing detailed summary"

    def test_summarize_podcast_transcript_partial_json_fields(self):
        """
        Test handling when only one field is present or parseable.
        """
        partial_response = """{
  "short_summary": "This podcast covers AI industry developments and competitive dynamics."
}"""
        
        mock_response = Mock()
        mock_response.text = partial_response
        
        mock_client = Mock()
        mock_generate_content = Mock(return_value=mock_response)
        mock_client.models.generate_content = mock_generate_content
        
        test_transcript = "Test podcast transcript"
        
        with patch('app.llm.genai.Client', return_value=mock_client):
            result = summarize_podcast_transcript(test_transcript)
            
            assert isinstance(result, ArticleSummary)
            assert "AI industry developments" in result.short_summary
            # detailed_summary should fall back to error message when not found
            assert result.detailed_summary == "Error parsing detailed summary"