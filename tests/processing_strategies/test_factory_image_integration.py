"""
Tests for factory integration with ImageProcessorStrategy.
"""
import pytest
from unittest.mock import Mock
import httpx

from app.processing_strategies.factory import UrlProcessorFactory
from app.processing_strategies.image_strategy import ImageProcessorStrategy
from app.http_client.robust_http_client import RobustHttpClient


class TestFactoryImageIntegration:
    """Test cases for factory integration with ImageProcessorStrategy."""

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        return Mock(spec=RobustHttpClient)

    @pytest.fixture
    def factory(self, mock_http_client):
        """Create a UrlProcessorFactory instance."""
        return UrlProcessorFactory(mock_http_client)

    def test_factory_registers_image_strategy(self, factory):
        """Test that factory registers the image strategy."""
        strategy_classes = [type(strategy).__name__ for strategy in 
                          [cls(factory.http_client) for cls in factory._strategies]]
        assert 'ImageProcessorStrategy' in strategy_classes

    def test_factory_selects_image_strategy_for_image_urls(self, factory):
        """Test that factory selects image strategy for image URLs."""
        image_urls = [
            "https://example.com/photo.jpg",
            "https://example.com/image.png",
            "https://example.com/animation.gif"
        ]
        
        for url in image_urls:
            strategy = factory.get_strategy(url)
            assert strategy is not None
            assert isinstance(strategy, ImageProcessorStrategy)

    def test_factory_image_strategy_comes_before_html(self, factory):
        """Test that image strategy is registered before HTML strategy."""
        strategy_names = [cls.__name__ for cls in factory._strategies]
        image_index = strategy_names.index('ImageProcessorStrategy')
        html_index = strategy_names.index('HtmlProcessorStrategy')
        assert image_index < html_index, "Image strategy should come before HTML strategy"

    def test_factory_with_image_content_type_header(self, factory, mock_http_client):
        """Test factory selection with image Content-Type header."""
        # Use a URL that ends with .txt so HTML strategy won't claim it in first pass
        url = "https://example.com/photo.txt"
        
        # Mock HEAD request response
        mock_response = Mock()
        mock_response.headers = httpx.Headers({"content-type": "image/jpeg"})
        mock_response.url = url
        mock_http_client.head.return_value = mock_response
        
        strategy = factory.get_strategy(url)
        assert strategy is not None
        assert isinstance(strategy, ImageProcessorStrategy)

    def test_factory_does_not_select_image_for_non_image_urls(self, factory):
        """Test that factory doesn't select image strategy for non-image URLs."""
        non_image_urls = [
            "https://example.com/article.html",
            "https://example.com/document.pdf"
        ]
        
        for url in non_image_urls:
            strategy = factory.get_strategy(url)
            # Should get a strategy, but not the image strategy
            if strategy is not None:
                assert not isinstance(strategy, ImageProcessorStrategy)