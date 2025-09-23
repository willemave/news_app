"""Test HTML strategy event loop handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.processing_strategies.html_strategy import HtmlProcessorStrategy


class TestHtmlStrategyEventLoop:
    """Test HTML strategy handling of event loop conflicts."""
    
    @pytest.mark.asyncio
    async def test_html_strategy_async_extract_data(self):
        """Test that HTML strategy correctly uses async extract_data."""
        # Create strategy instance with mock http client
        mock_http_client = MagicMock()
        strategy = HtmlProcessorStrategy(mock_http_client)
        
        # Mock AsyncWebCrawler
        with patch("app.processing_strategies.html_strategy.AsyncWebCrawler") as mock_crawler_class:
            # Create mock result object
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.markdown = MagicMock()
            mock_result.markdown.raw_markdown = "Test content extracted from page"
            mock_result.metadata = {"title": "Test Article"}
            mock_result.url = "https://example.com/article"
            mock_result.cleaned_html = "<html><body>Test content</body></html>"
            
            # Create async context manager mock
            mock_crawler_instance = AsyncMock()
            mock_crawler_instance.arun = AsyncMock(return_value=mock_result)
            
            mock_crawler_class.return_value.__aenter__ = AsyncMock(return_value=mock_crawler_instance)
            mock_crawler_class.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Test extract_data
            result = await strategy.extract_data("dummy_content", "https://example.com/article")
            
            # Verify results
            assert result["title"] == "Test Article"
            assert result["text_content"] == "Test content extracted from page"
            assert result["final_url_after_redirects"] == "https://example.com/article"
            assert result["content_type"] == "html"
            
            # Verify AsyncWebCrawler was called correctly
            mock_crawler_instance.arun.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_html_strategy_error_handling(self):
        """Test that HTML strategy handles extraction errors gracefully."""
        # Create strategy instance with mock http client
        mock_http_client = MagicMock()
        strategy = HtmlProcessorStrategy(mock_http_client)
        
        # Mock AsyncWebCrawler to raise an error
        with patch("app.processing_strategies.html_strategy.AsyncWebCrawler") as mock_crawler_class:
            # Create async context manager mock that raises error
            mock_crawler_instance = AsyncMock()
            mock_crawler_instance.arun = AsyncMock(side_effect=Exception("Crawl4ai extraction failed"))
            
            mock_crawler_class.return_value.__aenter__ = AsyncMock(return_value=mock_crawler_instance)
            mock_crawler_class.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Test extract_data
            result = await strategy.extract_data("dummy_content", "https://example.com/article")
            
            # Verify error handling
            assert result["title"] == "Extraction Failed"
            assert result["text_content"] == ""
            assert result["content_type"] == "html"
    
    @pytest.mark.asyncio
    async def test_html_strategy_concurrent_extractions(self):
        """Test that HTML strategy can handle concurrent extractions."""
        # Create strategy instance with mock http client
        mock_http_client = MagicMock()
        strategy = HtmlProcessorStrategy(mock_http_client)
        
        # Mock AsyncWebCrawler
        with patch("app.processing_strategies.html_strategy.AsyncWebCrawler") as mock_crawler_class:
            # Create mock result object
            def create_mock_result(url):
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.markdown = MagicMock()
                mock_result.markdown.raw_markdown = f"Content from {url}"
                mock_result.metadata = {"title": f"Title for {url}"}
                mock_result.url = url
                mock_result.cleaned_html = f"<html><body>Content from {url}</body></html>"
                return mock_result
            
            # Create async context manager mock
            mock_crawler_instance = AsyncMock()
            mock_crawler_instance.arun = AsyncMock(side_effect=lambda url, config: create_mock_result(url))
            
            mock_crawler_class.return_value.__aenter__ = AsyncMock(return_value=mock_crawler_instance)
            mock_crawler_class.return_value.__aexit__ = AsyncMock(return_value=None)
            
            # Test concurrent extractions
            urls = [
                "https://example.com/article1",
                "https://example.com/article2",
                "https://example.com/article3"
            ]
            
            results = await asyncio.gather(*[
                strategy.extract_data("dummy", url) for url in urls
            ])
            
            # Verify all results
            assert len(results) == 3
            for i, result in enumerate(results):
                expected_url = urls[i]
                assert result["title"] == f"Title for {expected_url}"
                assert result["text_content"] == f"Content from {expected_url}"
                assert result["final_url_after_redirects"] == expected_url
    
    @pytest.mark.asyncio
    async def test_html_strategy_with_different_sources(self):
        """Test that HTML strategy correctly detects and handles different sources."""
        # Create strategy instance with mock http client
        mock_http_client = MagicMock()
        strategy = HtmlProcessorStrategy(mock_http_client)
        
        # Test URLs from different sources
        test_cases = [
            ("https://example.substack.com/p/article", "Substack"),
            ("https://medium.com/@user/article", "Medium"),
            ("https://pubmed.ncbi.nlm.nih.gov/12345", "PubMed"),
            ("https://arxiv.org/abs/2301.00001", "Arxiv"),
            ("https://chinatalk.media/p/article", "ChinaTalk"),
            ("https://example.com/article", "web")
        ]
        
        # Mock AsyncWebCrawler
        with patch("app.processing_strategies.html_strategy.AsyncWebCrawler") as mock_crawler_class:
            # Create mock result object
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.markdown = MagicMock()
            mock_result.markdown.raw_markdown = "Test content"
            mock_result.metadata = {"title": "Test Article"}
            mock_result.cleaned_html = "<html><body>Test content</body></html>"
            
            # Create async context manager mock
            mock_crawler_instance = AsyncMock()
            mock_crawler_instance.arun = AsyncMock(return_value=mock_result)
            
            mock_crawler_class.return_value.__aenter__ = AsyncMock(return_value=mock_crawler_instance)
            mock_crawler_class.return_value.__aexit__ = AsyncMock(return_value=None)
            
            for url, expected_source in test_cases:
                mock_result.url = url
                result = await strategy.extract_data("dummy", url)
                assert result["source"] == expected_source, f"Failed for URL: {url}"