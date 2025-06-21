"""
This module defines the factory for URL processing strategies.
"""

from app.core.logging import get_logger
from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.arxiv_strategy import ArxivProcessorStrategy  # Added import
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.processing_strategies.html_strategy import HtmlProcessorStrategy
from app.processing_strategies.image_strategy import ImageProcessorStrategy
from app.processing_strategies.pdf_strategy import PdfProcessorStrategy
from app.processing_strategies.pubmed_strategy import PubMedProcessorStrategy

logger = get_logger(__name__)


class UrlProcessorFactory:
    """
    Factory class to determine and instantiate the appropriate URL processing strategy.
    """

    def __init__(self, http_client: RobustHttpClient):
        """
        Initializes the factory with an HTTP client and registers available strategies.

        Args:
            http_client: An instance of RobustHttpClient.
        """
        self.http_client = http_client
        self._strategies: list[type[UrlProcessorStrategy]] = []
        self._register_default_strategies()

    def _register_default_strategies(self):
        """Registers the default set of strategies."""
        # Order is important: more specific strategies should come before general ones.
        # ArxivStrategy for /abs/ links, which then become PDF links.
        # PubMedStrategy for specific domain.
        # PdfProcessorStrategy for direct .pdf links or Content-Type PDF.
        # ImageProcessorStrategy for image files (before HTML to avoid false matches).
        # HtmlProcessorStrategy as a more general fallback.
        self.register_strategy(ArxivProcessorStrategy)  # Handles arxiv.org/abs/ links
        self.register_strategy(PubMedProcessorStrategy)  # Specific domain
        self.register_strategy(
            PdfProcessorStrategy
        )  # Specific content type by extension/common URL pattern
        self.register_strategy(ImageProcessorStrategy)  # Image files (before HTML fallback)
        self.register_strategy(HtmlProcessorStrategy)  # More general HTML

    def register_strategy(self, strategy_class: type[UrlProcessorStrategy]):
        """
        Registers a strategy class with the factory.

        Args:
            strategy_class: The class of the strategy to register.
        """
        if strategy_class not in self._strategies:
            self._strategies.append(strategy_class)
            logger.info(f"Registered strategy: {strategy_class.__name__}")
        else:
            logger.warning(f"Strategy {strategy_class.__name__} already registered.")

    def get_strategy(self, url: str) -> UrlProcessorStrategy | None:
        """
        Determines and instantiates the appropriate strategy for a given URL.

        It may make a HEAD request to determine content type if necessary.
        Strategies are checked in the order they were registered.

        Args:
            url: The URL to find a strategy for.

        Returns:
            An instantiated UrlProcessorStrategy if a suitable one is found, None otherwise.
        """
        logger.info(f"Factory: Attempting to find strategy for URL: {url}")

        # First, try strategies that can identify themselves by URL pattern alone
        # (like PubMedStrategy or potentially a future ArxivStrategy for /abs/ links)
        for strategy_class in self._strategies:
            # Temporarily instantiate to call can_handle_url without HEAD request first
            # This is a bit of a workaround for strategies that don't need HEAD
            # A more refined approach might involve a static method on strategy or different check.
            temp_instance_for_url_check = strategy_class(self.http_client)
            if temp_instance_for_url_check.can_handle_url(url, response_headers=None):
                logger.info(
                    f"Factory: Strategy {strategy_class.__name__} matched URL pattern for {url}."
                )
                # Return a new instance for actual processing
                return strategy_class(self.http_client)

        # If no URL-pattern match, try with HEAD request to get Content-Type
        response_headers = None
        try:
            logger.debug(f"Factory: Making HEAD request for {url} to determine content type.")
            head_response = self.http_client.head(url)
            response_headers = head_response.headers
            # The actual URL might have changed after redirects from HEAD
            # Strategies should ideally use the final URL from HEAD if it's different
            # For now, the original URL is passed, but strategy's download will follow redirects.
            logger.info(
                f"Factory: HEAD request for {url} successful. Content-Type: {response_headers.get('content-type')}. Final URL: {head_response.url}"
            )
        except Exception as e:
            logger.warning(
                f"Factory: HEAD request for {url} failed: {e}. Will try strategies without headers."
            )
            # Proceed to check strategies that might not rely on Content-Type or handle failure.

        for strategy_class in self._strategies:
            # Pass response_headers if available
            instance = strategy_class(self.http_client)
            if instance.can_handle_url(url, response_headers=response_headers):
                logger.info(
                    f"Factory: Strategy {strategy_class.__name__} selected for {url} (Content-Type based or fallback)."
                )
                return instance

        logger.error(f"Factory: No suitable strategy found for URL: {url}")
        return None
