"""Unit tests for the arXiv processing strategy."""

from unittest.mock import Mock

import pytest

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.arxiv_strategy import ArxivProcessorStrategy


@pytest.fixture
def strategy() -> ArxivProcessorStrategy:
    """Return an ArxivProcessorStrategy with a mocked HTTP client."""
    return ArxivProcessorStrategy(Mock(spec=RobustHttpClient))


def test_can_handle_arxiv_abs_url(strategy: ArxivProcessorStrategy) -> None:
    """Strategy should accept canonical arXiv abstract URLs."""
    assert strategy.can_handle_url("https://arxiv.org/abs/2509.15194")


def test_can_handle_arxiv_pdf_url_with_www(strategy: ArxivProcessorStrategy) -> None:
    """Strategy should accept direct PDF URLs on www.arxiv.org."""
    assert strategy.can_handle_url("https://www.arxiv.org/pdf/2509.15194")


def test_cannot_handle_non_arxiv_domain(strategy: ArxivProcessorStrategy) -> None:
    """Strategy should reject non-arXiv domains."""
    assert not strategy.can_handle_url("https://example.com/pdf/2509.15194")


def test_preprocess_converts_abs_to_pdf(strategy: ArxivProcessorStrategy) -> None:
    """Abstract URLs should be converted to canonical PDF URLs."""
    normalized = strategy.preprocess_url(
        "http://www.arxiv.org/abs/2509.15194v2?context=cs"
    )
    assert normalized == "https://arxiv.org/pdf/2509.15194v2"


def test_preprocess_normalizes_pdf_host(strategy: ArxivProcessorStrategy) -> None:
    """Direct PDF URLs should be normalized to https://arxiv.org."""
    normalized = strategy.preprocess_url("https://www.arxiv.org/pdf/2509.15194")
    assert normalized == "https://arxiv.org/pdf/2509.15194"


def test_preprocess_preserves_pdf_query(strategy: ArxivProcessorStrategy) -> None:
    """Query parameters for direct PDFs should be preserved."""
    normalized = strategy.preprocess_url("https://arxiv.org/pdf/2509.15194.pdf?download=1")
    assert normalized == "https://arxiv.org/pdf/2509.15194.pdf?download=1"
