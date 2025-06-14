"""
Test simple fixes that don't require external dependencies.
Tests core functionality like URL patterns, model validation, and enum values.
"""
import pytest
import re

from app.domain.summary import ArticleSummary
from app.models.schema import ContentStatus


class TestArxivUrlPattern:
    """Test arXiv URL pattern matching logic."""

    def test_arxiv_pattern_matching(self):
        """Test arXiv URL pattern matching and conversion logic."""
        url = "https://arxiv.org/abs/2504.16980"
        arxiv_pattern = r'https://arxiv\.org/abs/(\d+\.\d+)'
        arxiv_match = re.match(arxiv_pattern, url)
        
        assert arxiv_match is not None
        paper_id = arxiv_match.group(1)
        assert paper_id == "2504.16980"
        
        pdf_url = f"https://arxiv.org/pdf/{paper_id}"
        expected = "https://arxiv.org/pdf/2504.16980"
        assert pdf_url == expected

    def test_arxiv_pattern_different_ids(self):
        """Test arXiv pattern with different paper IDs."""
        test_cases = [
            ("https://arxiv.org/abs/1234.5678", "1234.5678"),
            ("https://arxiv.org/abs/2024.12345", "2024.12345"),
            ("https://arxiv.org/abs/0801.1234", "0801.1234"),
            ("https://arxiv.org/abs/9912.001", "9912.001"),
        ]
        
        arxiv_pattern = r'https://arxiv\.org/abs/(\d+\.\d+)'
        
        for url, expected_id in test_cases:
            match = re.match(arxiv_pattern, url)
            assert match is not None
            assert match.group(1) == expected_id

    def test_arxiv_pattern_non_matching(self):
        """Test that non-arXiv URLs don't match the pattern."""
        non_arxiv_urls = [
            "https://example.com/article",
            "https://github.com/user/repo",
            "https://arxiv.org/list/cs.AI",  # Different arXiv URL format
            "https://arxiv.org/search/?query=test",
        ]
        
        arxiv_pattern = r'https://arxiv\.org/abs/(\d+\.\d+)'
        
        for url in non_arxiv_urls:
            match = re.match(arxiv_pattern, url)
            assert match is None


class TestPubmedUrlDetection:
    """Test PubMed URL detection logic."""

    def test_pubmed_url_detection_positive(self):
        """Test PubMed URL detection for valid PubMed URLs."""
        pubmed_urls = [
            "https://pubmed.ncbi.nlm.nih.gov/12345678",
            "https://pubmed.ncbi.nlm.nih.gov/87654321/",
            "http://pubmed.ncbi.nlm.nih.gov/11111111",
        ]
        
        for url in pubmed_urls:
            is_pubmed = 'pubmed.ncbi.nlm.nih.gov' in url
            assert is_pubmed is True

    def test_pubmed_url_detection_negative(self):
        """Test PubMed URL detection for non-PubMed URLs."""
        non_pubmed_urls = [
            "https://example.com/article",
            "https://github.com/user/repo",
            "https://arxiv.org/abs/1234.5678",
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC123456/",  # PMC, not PubMed
            "https://ncbi.nlm.nih.gov/other",
        ]
        
        for url in non_pubmed_urls:
            is_pubmed = 'pubmed.ncbi.nlm.nih.gov' in url
            assert is_pubmed is False

    def test_pubmed_detection_case_sensitivity(self):
        """Test that PubMed detection is case sensitive."""
        # Should match (correct case)
        correct_case = "https://pubmed.ncbi.nlm.nih.gov/12345"
        assert 'pubmed.ncbi.nlm.nih.gov' in correct_case
        
        # Should not match (wrong case)
        wrong_case = "https://PUBMED.NCBI.NLM.NIH.GOV/12345"
        assert 'pubmed.ncbi.nlm.nih.gov' not in wrong_case


class TestArticleSummaryModelValidation:
    """Test ArticleSummary Pydantic model validation."""

    def test_article_summary_valid_creation(self):
        """Test creating ArticleSummary with valid data."""
        summary_data = {
            "short_summary": "This is a short summary.",
            "detailed_summary": "This is a detailed summary with more information."
        }
        
        summary = ArticleSummary(**summary_data)
        
        assert summary.short_summary == summary_data["short_summary"]
        assert summary.detailed_summary == summary_data["detailed_summary"]

    def test_article_summary_field_validation(self):
        """Test ArticleSummary field validation."""
        # Test model validation
        summary_data = {
            "short_summary": "Short summary",
            "detailed_summary": "Detailed summary"
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
        
        # Test that keywords are not part of the model
        assert not hasattr(summary, 'keywords')

    def test_article_summary_required_fields(self):
        """Test that both fields are required."""
        # Missing short_summary
        with pytest.raises(ValueError):
            ArticleSummary(detailed_summary="Only detailed")
        
        # Missing detailed_summary
        with pytest.raises(ValueError):
            ArticleSummary(short_summary="Only short")

    def test_article_summary_model_dump(self):
        """Test ArticleSummary model serialization."""
        summary_data = {
            "short_summary": "Short",
            "detailed_summary": "Detailed"
        }
        
        summary = ArticleSummary(**summary_data)
        dumped = summary.model_dump()
        
        assert dumped == summary_data
        assert isinstance(dumped, dict)


class TestContentStatusEnumValidation:
    """Test ContentStatus enum validation."""

    def test_skipped_status_availability(self):
        """Test that the new 'skipped' status is available."""
        assert hasattr(ContentStatus, 'SKIPPED')
        assert ContentStatus.SKIPPED.value == "skipped"

    def test_all_expected_statuses(self):
        """Test that all expected statuses are available."""
        expected_statuses = ["new", "processing", "completed", "failed", "skipped"]
        actual_statuses = [status.value for status in ContentStatus]
        
        for status in expected_statuses:
            assert status in actual_statuses

    def test_status_enum_values(self):
        """Test individual status enum values."""
        assert ContentStatus.NEW.value == "new"
        assert ContentStatus.PROCESSING.value == "processing"
        assert ContentStatus.COMPLETED.value == "completed"
        assert ContentStatus.FAILED.value == "failed"
        assert ContentStatus.SKIPPED.value == "skipped"

    def test_status_enum_count(self):
        """Test that we have exactly 5 statuses."""
        statuses = list(ContentStatus)
        assert len(statuses) == 5

    def test_status_enum_iteration(self):
        """Test iterating over ContentStatus enum."""
        expected_values = {"new", "processing", "completed", "failed", "skipped"}
        actual_values = {status.value for status in ContentStatus}
        
        assert actual_values == expected_values


class TestJsonStructureChanges:
    """Test the expected JSON structure changes for LLM responses."""

    def test_new_json_structure_valid(self):
        """Test that new JSON structure works with ArticleSummary."""
        # New structure (what we expect now)
        new_structure = {
            "short_summary": "summary",
            "detailed_summary": "detailed summary"
        }
        
        # Verify new structure works with ArticleSummary
        summary = ArticleSummary(**new_structure)
        assert summary.short_summary == "summary"
        assert summary.detailed_summary == "detailed summary"

    def test_old_json_structure_invalid(self):
        """Test that old JSON structure is rejected."""
        # Old structure (should not be used anymore)
        old_structure = {
            "short": "summary",
            "detailed": "detailed summary",
            "keywords": ["key1", "key2"]
        }
        
        # Should raise validation error
        with pytest.raises(ValueError):
            ArticleSummary(**old_structure)

    def test_json_structure_field_mapping(self):
        """Test that field names are correctly mapped."""
        # Test that the new field names are used
        data = {
            "short_summary": "test short",
            "detailed_summary": "test detailed"
        }
        
        summary = ArticleSummary(**data)
        
        # Verify field names
        assert hasattr(summary, 'short_summary')
        assert hasattr(summary, 'detailed_summary')
        
        # Verify old field names don't exist
        assert not hasattr(summary, 'short')
        assert not hasattr(summary, 'detailed')
        assert not hasattr(summary, 'keywords')

    def test_json_structure_serialization(self):
        """Test that serialization uses new structure."""
        summary = ArticleSummary(
            short_summary="test short",
            detailed_summary="test detailed"
        )
        
        serialized = summary.model_dump()
        
        # Should have new field names
        assert "short_summary" in serialized
        assert "detailed_summary" in serialized
        
        # Should not have old field names
        assert "short" not in serialized
        assert "detailed" not in serialized
        assert "keywords" not in serialized


class TestIntegrationSimple:
    """Simple integration tests that don't require external dependencies."""

    def test_arxiv_url_to_summary_workflow(self):
        """Test workflow from arXiv URL pattern to summary creation."""
        # Test arXiv URL pattern
        url = "https://arxiv.org/abs/2024.12345"
        arxiv_pattern = r'https://arxiv\.org/abs/(\d+\.\d+)'
        match = re.match(arxiv_pattern, url)
        
        assert match is not None
        paper_id = match.group(1)
        pdf_url = f"https://arxiv.org/pdf/{paper_id}"
        
        # Test summary creation
        summary_data = {
            "short_summary": f"Paper {paper_id} summary",
            "detailed_summary": f"Detailed analysis of paper {paper_id}"
        }
        
        summary = ArticleSummary(**summary_data)
        assert paper_id in summary.short_summary
        assert paper_id in summary.detailed_summary

    def test_status_workflow_simulation(self):
        """Test typical status workflow."""
        # Start with new status
        current_status = ContentStatus.NEW
        assert current_status.value == "new"
        
        # Move to processing
        current_status = ContentStatus.PROCESSING
        assert current_status.value == "processing"
        
        # Can end in different ways
        possible_end_states = [
            ContentStatus.COMPLETED,
            ContentStatus.FAILED,
            ContentStatus.SKIPPED
        ]
        
        for end_state in possible_end_states:
            assert isinstance(end_state, ContentStatus)
            assert end_state.value in ["completed", "failed", "skipped"]

    def test_complete_validation_workflow(self):
        """Test complete validation workflow for all components."""
        # 1. URL pattern validation
        arxiv_url = "https://arxiv.org/abs/1234.5678"
        arxiv_pattern = r'https://arxiv\.org/abs/(\d+\.\d+)'
        assert re.match(arxiv_pattern, arxiv_url) is not None
        
        # 2. PubMed detection
        pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/12345"
        assert 'pubmed.ncbi.nlm.nih.gov' in pubmed_url
        
        # 3. Summary model validation
        summary_data = {
            "short_summary": "Valid summary",
            "detailed_summary": "Valid detailed summary"
        }
        summary = ArticleSummary(**summary_data)
        assert summary.short_summary == "Valid summary"
        
        # 4. Status enum validation
        assert ContentStatus.SKIPPED.value == "skipped"
        assert len(list(ContentStatus)) == 5