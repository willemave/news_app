#!/usr/bin/env python3
"""
Integration test for the unified system with processing strategies and scrapers.
"""
import pytest
import asyncio
from app.processing_strategies.registry import get_strategy_registry
from app.scraping.runner import ScraperRunner
from app.core.logging import get_logger

logger = get_logger(__name__)

def test_all_strategies_registered():
    """Test that all 5 processing strategies are registered."""
    registry = get_strategy_registry()
    strategies = registry.list_strategies()
    
    expected_strategies = [
        'ArxivProcessorStrategy',
        'PubMedProcessorStrategy', 
        'PdfProcessorStrategy',
        'ImageProcessorStrategy',
        'HtmlProcessorStrategy'
    ]
    
    print(f"Registered strategies: {strategies}")
    assert len(strategies) == 5
    for expected in expected_strategies:
        assert expected in strategies

def test_strategy_selection():
    """Test strategy selection for different URL types."""
    registry = get_strategy_registry()
    
    # Test HTML strategy selection
    html_strategy = registry.get_strategy("https://example.com/article")
    assert html_strategy is not None
    assert html_strategy.__class__.__name__ == 'HtmlProcessorStrategy'
    
    # Test PDF strategy selection
    pdf_strategy = registry.get_strategy("https://example.com/document.pdf")
    assert pdf_strategy is not None
    assert pdf_strategy.__class__.__name__ == 'PdfProcessorStrategy'
    
    # Test ArXiv strategy selection
    arxiv_strategy = registry.get_strategy("https://arxiv.org/abs/2301.12345")
    assert arxiv_strategy is not None
    assert arxiv_strategy.__class__.__name__ == 'ArxivProcessorStrategy'

def test_all_scrapers_available():
    """Test that all scrapers are available in the runner."""
    runner = ScraperRunner()
    scrapers = runner.list_scrapers()
    
    expected_scrapers = ['HackerNews', 'Reddit', 'Substack']
    
    print(f"Available scrapers: {scrapers}")
    assert len(scrapers) == 3
    for expected in expected_scrapers:
        assert expected in scrapers

async def test_scraper_runner_functionality():
    """Test that scraper runner can list and identify scrapers."""
    runner = ScraperRunner()
    
    # Test listing scrapers
    scrapers = runner.list_scrapers()
    assert 'HackerNews' in scrapers
    assert 'Reddit' in scrapers
    assert 'Substack' in scrapers
    
    # Test finding specific scrapers
    for scraper in runner.scrapers:
        assert scraper.name in ['HackerNews', 'Reddit', 'Substack']
        assert hasattr(scraper, 'scrape')
        assert hasattr(scraper, 'run')

def test_strategy_methods():
    """Test that strategies have all required methods."""
    registry = get_strategy_registry()
    
    for strategy_name in registry.list_strategies():
        strategy = registry.get_strategy("https://example.com/test")
        if strategy and strategy.__class__.__name__ == strategy_name:
            # Test required methods exist
            assert hasattr(strategy, 'can_handle_url')
            assert hasattr(strategy, 'download_content')
            assert hasattr(strategy, 'extract_data')
            assert hasattr(strategy, 'prepare_for_llm')
            assert hasattr(strategy, 'preprocess_url')
            break

if __name__ == "__main__":
    print("🧪 Running unified system integration tests...")
    
    # Run sync tests
    test_all_strategies_registered()
    test_strategy_selection()
    test_all_scrapers_available()
    test_strategy_methods()
    
    # Run async tests
    asyncio.run(test_scraper_runner_functionality())
    
    print("✅ All unified system integration tests passed!")