"""
Test implemented fixes for URL preprocessing, models, and enums.
"""
import pytest
from unittest.mock import patch

from app.processor import url_preprocessor
from app.schemas import ArticleSummary
from app.models import LinkStatus


class TestUrlPreprocessing:
    """Test URL preprocessing functionality."""

    def test_arxiv_url_conversion(self):
        """Test arXiv URL conversion to PDF format."""
        arxiv_url = "https://arxiv.org/abs/2504.16980"
        processed_url = url_preprocessor(arxiv_url)
        expected_url = "https://arxiv.org/pdf/2504.16980"
        
        assert processed_url == expected_url

    def test_arxiv_url_different_paper_ids(self):
        """Test arXiv URL conversion with different paper IDs."""
        test_cases = [
            ("https://arxiv.org/abs/1234.5678", "https://arxiv.org/pdf/1234.5678"),
            ("https://arxiv.org/abs/2024.12345", "https://arxiv.org/pdf/2024.12345"),
            ("https://arxiv.org/abs/0801.1234", "https://arxiv.org/pdf/0801.1234"),
        ]
        
        for input_url, expected_url in test_cases:
            result = url_preprocessor(input_url)
            assert result == expected_url

    def test_regular_url_unchanged(self):
        """Test that regular URLs remain unchanged."""
        regular_urls = [
            "https://example.com/article",
            "https://github.com/user/repo",
            "https://news.ycombinator.com/item?id=123",
            "https://techcrunch.com/article",
        ]
        
        for url in regular_urls:
            with patch('app.processor.extract_pubmed_full_text_link'):
                result = url_preprocessor(url)
                assert result == url

    @patch('app.processor.extract_pubmed_full_text_link')
    def test_pubmed_url_with_full_text(self, mock_extract):
        """Test PubMed URL processing when full text link is found."""
        pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/12345678"
        full_text_url = "https://pmc.ncbi.nlm.nih.gov/articles/PMC123456/"
        mock_extract.return_value = full_text_url
        
        result = url_preprocessor(pubmed_url)
        
        assert result == full_text_url
        mock_extract.assert_called_once_with(pubmed_url)

    @patch('app.processor.extract_pubmed_full_text_link')
    def test_pubmed_url_without_full_text(self, mock_extract):
        """Test PubMed URL processing when no full text link is found."""
        pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/12345678"
        mock_extract.return_value = None
        
        result = url_preprocessor(pubmed_url)
        
        assert result == pubmed_url

    def test_pubmed_url_detection(self):
        """Test PubMed URL detection logic."""
        pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/12345678"
        regular_url = "https://example.com/article"
        
        # Test detection logic
        is_pubmed1 = 'pubmed.ncbi.nlm.nih.gov' in pubmed_url
        is_pubmed2 = 'pubmed.ncbi.nlm.nih.gov' in regular_url
        
        assert is_pubmed1 is True
        assert is_pubmed2 is False


class TestArticleSummaryModel:
    """Test ArticleSummary Pydantic model."""

    def test_article_summary_creation_valid(self):
        """Test creating ArticleSummary with valid data."""
        summary_data = {
            "short_summary": "This is a short summary.",
            "detailed_summary": "This is a detailed summary with more information."
        }
        
        summary = ArticleSummary(**summary_data)
        
        assert summary.short_summary == summary_data["short_summary"]
        assert summary.detailed_summary == summary_data["detailed_summary"]

    def test_article_summary_no_keywords_field(self):
        """Test that ArticleSummary does not have keywords field."""
        summary_data = {
            "short_summary": "Short summary",
            "detailed_summary": "Detailed summary"
        }
        
        summary = ArticleSummary(**summary_data)
        
        # Verify keywords field doesn't exist
        assert not hasattr(summary, 'keywords')
        
        # Verify only expected fields exist
        expected_fields = {'short_summary', 'detailed_summary'}
        actual_fields = set(ArticleSummary.model_fields.keys())
        assert actual_fields == expected_fields

    def test_article_summary_missing_required_fields(self):
        """Test ArticleSummary validation with missing required fields."""
        # Test with missing short_summary
        with pytest.raises(ValueError):
            ArticleSummary(detailed_summary="Only detailed summary")
        
        # Test with missing detailed_summary
        with pytest.raises(ValueError):
            ArticleSummary(short_summary="Only short summary")
        
        # Test with empty dict
        with pytest.raises(ValueError):
            ArticleSummary()

    def test_article_summary_json_serialization(self):
        """Test ArticleSummary JSON serialization."""
        summary_data = {
            "short_summary": "Short summary",
            "detailed_summary": "Detailed summary"
        }
        
        summary = ArticleSummary(**summary_data)
        json_data = summary.model_dump()
        
        assert json_data == summary_data
        assert isinstance(json_data, dict)

    def test_new_json_structure_compatibility(self):
        """Test the new JSON structure for LLM responses."""
        # New structure (current expected format)
        new_structure = {
            "short_summary": "summary",
            "detailed_summary": "detailed summary"
        }
        
        # Verify new structure works with ArticleSummary
        summary = ArticleSummary(**new_structure)
        assert summary.short_summary == "summary"
        assert summary.detailed_summary == "detailed summary"

    def test_old_structure_incompatible(self):
        """Test that old JSON structure is incompatible."""
        # Old structure (should not work anymore)
        old_structure = {
            "short": "summary",
            "detailed": "detailed summary",
            "keywords": ["key1", "key2"]
        }
        
        # Should raise validation error
        with pytest.raises(ValueError):
            ArticleSummary(**old_structure)

    def test_article_summary_empty_strings(self):
        """Test ArticleSummary with empty strings."""
        summary_data = {
            "short_summary": "",
            "detailed_summary": ""
        }
        
        # Should be valid even with empty strings
        summary = ArticleSummary(**summary_data)
        assert summary.short_summary == ""
        assert summary.detailed_summary == ""

    def test_article_summary_long_content(self):
        """Test ArticleSummary with long content."""
        long_summary = "A" * 1000
        long_detailed = "B" * 5000
        
        summary_data = {
            "short_summary": long_summary,
            "detailed_summary": long_detailed
        }
        
        summary = ArticleSummary(**summary_data)
        assert summary.short_summary == long_summary
        assert summary.detailed_summary == long_detailed


class TestLinkStatusEnum:
    """Test LinkStatus enum functionality."""

    def test_skipped_status_exists(self):
        """Test that the 'skipped' status is available."""
        assert hasattr(LinkStatus, 'skipped')
        assert LinkStatus.skipped.value == "skipped"

    def test_all_expected_statuses_exist(self):
        """Test that all expected statuses are available."""
        expected_statuses = ["new", "processing", "processed", "failed", "skipped"]
        actual_statuses = [status.value for status in LinkStatus]
        
        for status in expected_statuses:
            assert status in actual_statuses, f"Status '{status}' should be available"

    def test_individual_status_values(self):
        """Test individual status values."""
        assert LinkStatus.new.value == "new"
        assert LinkStatus.processing.value == "processing"
        assert LinkStatus.processed.value == "processed"
        assert LinkStatus.failed.value == "failed"
        assert LinkStatus.skipped.value == "skipped"

    def test_status_enum_completeness(self):
        """Test that we have exactly the expected statuses."""
        expected_statuses = {"new", "processing", "processed", "failed", "skipped"}
        actual_statuses = {status.value for status in LinkStatus}
        
        assert actual_statuses == expected_statuses

    def test_status_enum_types(self):
        """Test that status enum values are proper enum members."""
        for status in LinkStatus:
            assert isinstance(status, LinkStatus)
            assert isinstance(status.value, str)

    def test_status_enum_iteration(self):
        """Test that we can iterate over all statuses."""
        statuses = list(LinkStatus)
        assert len(statuses) == 5
        
        status_values = [status.value for status in statuses]
        expected_values = ["new", "processing", "processed", "failed", "skipped"]
        
        for expected in expected_values:
            assert expected in status_values

    def test_status_enum_comparison(self):
        """Test status enum comparison."""
        assert LinkStatus.new == LinkStatus.new
        assert LinkStatus.new != LinkStatus.processing
        assert LinkStatus.skipped != LinkStatus.failed


class TestIntegrationFixes:
    """Integration tests for all fixes working together."""

    @patch('app.processor.extract_pubmed_full_text_link')
    def test_complete_workflow_simulation(self, mock_extract):
        """Test a complete workflow with all fixes."""
        mock_extract.return_value = None
        
        # 1. URL preprocessing
        arxiv_url = "https://arxiv.org/abs/2024.12345"
        processed_url = url_preprocessor(arxiv_url)
        assert processed_url == "https://arxiv.org/pdf/2024.12345"
        
        # 2. Article summary creation
        summary_data = {
            "short_summary": "Research paper summary",
            "detailed_summary": "Detailed analysis of the research findings"
        }
        summary = ArticleSummary(**summary_data)
        assert summary.short_summary == "Research paper summary"
        
        # 3. Status management
        assert LinkStatus.skipped.value == "skipped"
        assert hasattr(LinkStatus, 'processed')

    def test_arxiv_to_summary_workflow(self):
        """Test workflow from arXiv URL to summary creation."""
        # Start with arXiv URL
        original_url = "https://arxiv.org/abs/1234.5678"
        
        # Process URL
        processed_url = url_preprocessor(original_url)
        assert processed_url == "https://arxiv.org/pdf/1234.5678"
        
        # Create summary (simulating LLM response)
        llm_response = {
            "short_summary": "This paper discusses machine learning techniques.",
            "detailed_summary": "• Key topics: ML, AI, algorithms\n\nThis paper provides a comprehensive analysis of modern machine learning techniques and their applications in various domains."
        }
        
        summary = ArticleSummary(**llm_response)
        assert "machine learning" in summary.short_summary
        assert "Key topics" in summary.detailed_summary

    def test_status_transitions(self):
        """Test typical status transitions."""
        # Typical workflow statuses
        statuses = [
            LinkStatus.new,
            LinkStatus.processing,
            LinkStatus.processed
        ]
        
        for status in statuses:
            assert isinstance(status, LinkStatus)
        
        # Alternative workflow with skipping
        alt_statuses = [
            LinkStatus.new,
            LinkStatus.processing,
            LinkStatus.skipped
        ]
        
        for status in alt_statuses:
            assert isinstance(status, LinkStatus)
        
        # Failure workflow
        fail_statuses = [
            LinkStatus.new,
            LinkStatus.processing,
            LinkStatus.failed
        ]
        
        for status in fail_statuses:
            assert isinstance(status, LinkStatus)