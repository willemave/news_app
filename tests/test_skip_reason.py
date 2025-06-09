"""
Test skip_reason functionality for filtering and failure logging.
"""
from unittest.mock import patch, Mock

from app.llm import filter_article
from app.utils.failures import record_failure
from app.models import FailurePhase, FailureLogs


class TestFilterArticle:
    """Test filter_article function."""

    @patch('app.llm.genai.Client')
    def test_filter_article_matches_preferences(self, mock_client_class):
        """Test filter_article when content matches preferences."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock the parsed response object
        mock_parsed = Mock()
        mock_parsed.matches = True
        mock_parsed.reason = "Technical content with good depth"
        
        mock_response = Mock()
        mock_response.parsed = mock_parsed
        mock_response.text = '{"matches": true, "reason": "Technical content with good depth"}'
        mock_client.models.generate_content.return_value = mock_response
        
        content = "This article discusses advanced machine learning algorithms and their implementation details."
        
        matches, reason = filter_article(content)
        
        assert matches is True
        assert "Technical content" in reason

    @patch('app.llm.genai.Client')
    def test_filter_article_rejects_promotional(self, mock_client_class):
        """Test filter_article when content is promotional."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock the parsed response object
        mock_parsed = Mock()
        mock_parsed.matches = False
        mock_parsed.reason = "Primarily promotional content with minimal technical value"
        
        mock_response = Mock()
        mock_response.parsed = mock_parsed
        mock_response.text = '{"matches": false, "reason": "Primarily promotional content with minimal technical value"}'
        mock_client.models.generate_content.return_value = mock_response
        
        content = """
        This is a promotional article about our amazing new product that will revolutionize
        your life! Buy now and get 50% off! This is clearly marketing content with no
        technical depth or analysis.
        """
        
        matches, reason = filter_article(content)
        
        assert matches is False
        assert "promotional" in reason.lower()

    @patch('app.llm.genai.Client')
    def test_filter_article_rejects_shallow_news(self, mock_client_class):
        """Test filter_article when content is shallow news."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock the parsed response object
        mock_parsed = Mock()
        mock_parsed.matches = False
        mock_parsed.reason = "Shallow news report without technical analysis"
        
        mock_response = Mock()
        mock_response.parsed = mock_parsed
        mock_response.text = '{"matches": false, "reason": "Shallow news report without technical analysis"}'
        mock_client.models.generate_content.return_value = mock_response
        
        content = "Company X announced a new product today. The stock price went up."
        
        matches, reason = filter_article(content)
        
        assert matches is False
        assert "shallow" in reason.lower() or "news" in reason.lower()

    @patch('app.llm.genai.Client')
    def test_filter_article_accepts_technical_analysis(self, mock_client_class):
        """Test filter_article when content has technical analysis."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock the parsed response object
        mock_parsed = Mock()
        mock_parsed.matches = True
        mock_parsed.reason = "In-depth technical analysis with implementation details"
        
        mock_response = Mock()
        mock_response.parsed = mock_parsed
        mock_response.text = '{"matches": true, "reason": "In-depth technical analysis with implementation details"}'
        mock_client.models.generate_content.return_value = mock_response
        
        content = """
        This article provides a deep dive into the architecture of distributed systems,
        examining consensus algorithms, CAP theorem implications, and practical
        implementation strategies for handling network partitions.
        """
        
        matches, reason = filter_article(content)
        
        assert matches is True
        assert "technical" in reason.lower() or "analysis" in reason.lower()

    @patch('app.llm.genai.Client')
    def test_filter_article_client_error(self, mock_client_class):
        """Test filter_article when LLM client raises an error."""
        # Mock the client to raise an error
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API error")
        
        content = "Some test content"
        
        matches, reason = filter_article(content)
        
        assert matches is False
        assert "Error during filtering" in reason

    @patch('app.llm.genai.Client')
    def test_filter_article_invalid_json_response(self, mock_client_class):
        """Test filter_article when LLM returns invalid JSON."""
        # Mock the client and response with invalid JSON
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.parsed = None  # No parsed object available
        mock_response.text = 'invalid json response'
        mock_client.models.generate_content.return_value = mock_response
        
        content = "Some test content"
        
        matches, reason = filter_article(content)
        
        assert matches is False
        assert "Error parsing filter response" in reason

    @patch('app.llm.genai.Client')
    def test_filter_article_missing_fields_in_response(self, mock_client_class):
        """Test filter_article when LLM response is missing expected fields."""
        # Mock the client and response with missing fields
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.parsed = None  # No parsed object available
        mock_response.text = '{"some_other_field": "value"}'
        mock_client.models.generate_content.return_value = mock_response
        
        content = "Some test content"
        
        matches, reason = filter_article(content)
        
        assert matches is False
        assert reason == "No reason provided"

    @patch('app.llm.genai.Client')
    def test_filter_article_uses_correct_model_and_config(self, mock_client_class):
        """Test that filter_article uses the correct model and configuration."""
        # Mock the client and response
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.text = '{"matches": true, "reason": "Good content"}'
        mock_client.models.generate_content.return_value = mock_response
        
        content = "Test content"
        
        filter_article(content)
        
        # Verify the correct model was used
        call_args = mock_client.models.generate_content.call_args
        assert call_args[1]['model'] == "gemini-2.5-flash-preview-05-20"
        
        # Verify JSON response format was requested
        config = call_args[1]['config']
        assert config.response_mime_type == "application/json"


class TestRecordFailure:
    """Test record_failure function."""

    @patch('app.utils.failures.SessionLocal')
    def test_record_failure_with_skip_reason(self, mock_session_local):
        """Test that record_failure correctly stores skip_reason."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        test_reason = "Test skip reason: promotional content detected"
        
        record_failure(
            phase=FailurePhase.processor,
            msg="Test skip message",
            link_id=123,
            skip_reason=test_reason
        )
        
        # Verify FailureLogs was created with correct data
        mock_db.add.assert_called_once()
        added_failure = mock_db.add.call_args[0][0]
        
        assert isinstance(added_failure, FailureLogs)
        assert added_failure.phase == FailurePhase.processor
        assert added_failure.error_msg == "Test skip message"
        assert added_failure.link_id == 123
        assert added_failure.skip_reason == test_reason
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('app.utils.failures.SessionLocal')
    def test_record_failure_without_skip_reason(self, mock_session_local):
        """Test record_failure without skip_reason."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        record_failure(
            phase=FailurePhase.scraper,
            msg="Network error",
            link_id=456
        )
        
        # Verify FailureLogs was created with correct data
        mock_db.add.assert_called_once()
        added_failure = mock_db.add.call_args[0][0]
        
        assert isinstance(added_failure, FailureLogs)
        assert added_failure.phase == FailurePhase.scraper
        assert added_failure.error_msg == "Network error"
        assert added_failure.link_id == 456
        assert added_failure.skip_reason is None

    @patch('app.utils.failures.SessionLocal')
    def test_record_failure_without_link_id(self, mock_session_local):
        """Test record_failure without link_id."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        record_failure(
            phase=FailurePhase.processor,
            msg="General processing error",
            skip_reason="Content not relevant"
        )
        
        # Verify FailureLogs was created with correct data
        mock_db.add.assert_called_once()
        added_failure = mock_db.add.call_args[0][0]
        
        assert isinstance(added_failure, FailureLogs)
        assert added_failure.phase == FailurePhase.processor
        assert added_failure.error_msg == "General processing error"
        assert added_failure.link_id is None
        assert added_failure.skip_reason == "Content not relevant"

    @patch('app.utils.failures.SessionLocal')
    def test_record_failure_database_exception(self, mock_session_local):
        """Test record_failure when database operation fails."""
        # Mock database session that raises exception
        mock_db = Mock()
        mock_db.add.side_effect = Exception("Database error")
        mock_session_local.return_value = mock_db
        
        # Should not raise exception, but handle it gracefully
        record_failure(
            phase=FailurePhase.processor,
            msg="Test message",
            link_id=789
        )
        
        # Verify rollback was called
        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('app.utils.failures.SessionLocal')
    def test_record_failure_long_messages(self, mock_session_local):
        """Test record_failure with long error messages and skip reasons."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        long_msg = "A" * 200
        long_skip_reason = "B" * 100
        
        record_failure(
            phase=FailurePhase.processor,
            msg=long_msg,
            link_id=999,
            skip_reason=long_skip_reason
        )
        
        # Verify FailureLogs was created with full messages
        mock_db.add.assert_called_once()
        added_failure = mock_db.add.call_args[0][0]
        
        assert added_failure.error_msg == long_msg
        assert added_failure.skip_reason == long_skip_reason


class TestSkipReasonIntegration:
    """Integration tests for skip reason functionality."""

    @patch('app.llm.genai.Client')
    @patch('app.utils.failures.SessionLocal')
    def test_filter_and_record_workflow(self, mock_session_local, mock_client_class):
        """Test complete workflow from filtering to recording skip reason."""
        # Mock LLM client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock the parsed response object
        mock_parsed = Mock()
        mock_parsed.matches = False
        mock_parsed.reason = "Promotional content detected"
        
        mock_response = Mock()
        mock_response.parsed = mock_parsed
        mock_response.text = '{"matches": false, "reason": "Promotional content detected"}'
        mock_client.models.generate_content.return_value = mock_response
        
        # Mock database
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Test content
        promotional_content = "Buy our amazing product now! 50% off!"
        
        # Filter the article
        matches, reason = filter_article(promotional_content)
        
        # Record the failure if not matching
        if not matches:
            record_failure(
                phase=FailurePhase.processor,
                msg=f"Content skipped by LLM filtering: {reason}",
                link_id=123,
                skip_reason=reason
            )
        
        # Verify the workflow
        assert matches is False
        assert "Promotional content" in reason
        
        # Verify failure was recorded
        mock_db.add.assert_called_once()
        added_failure = mock_db.add.call_args[0][0]
        assert added_failure.skip_reason == reason
        assert "Content skipped by LLM filtering" in added_failure.error_msg

    def test_failure_phase_enum_values(self):
        """Test that FailurePhase enum has expected values."""
        assert hasattr(FailurePhase, 'scraper')
        assert hasattr(FailurePhase, 'processor')
        
        assert FailurePhase.scraper.value == "scraper"
        assert FailurePhase.processor.value == "processor"