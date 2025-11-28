"""Exa search client service for chat agent web search tool."""

from dataclasses import dataclass

from exa_py import Exa

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

_exa_client: Exa | None = None


def get_exa_client() -> Exa | None:
    """Get singleton Exa client instance.

    Returns:
        Exa client if API key is configured, None otherwise.
    """
    global _exa_client

    if _exa_client is not None:
        return _exa_client

    settings = get_settings()
    if not settings.exa_api_key:
        logger.warning("Exa API key not configured, web search will be unavailable")
        return None

    _exa_client = Exa(api_key=settings.exa_api_key)
    logger.info("Initialized Exa client for web search")
    return _exa_client


@dataclass
class ExaSearchResult:
    """A single search result from Exa."""

    title: str
    url: str
    snippet: str | None = None
    published_date: str | None = None


def exa_search(
    query: str,
    num_results: int = 5,
    max_characters: int = 2000,
) -> list[ExaSearchResult]:
    """Search the web using Exa and return results.

    Args:
        query: Search query string.
        num_results: Maximum number of results to return.
        max_characters: Maximum characters to include from each result's text.

    Returns:
        List of ExaSearchResult objects with title, url, and snippet.
    """
    client = get_exa_client()
    if client is None:
        logger.warning("Exa client not available, returning empty results")
        return []

    try:
        logger.info(f"Exa search: {query[:100]}...")
        response = client.search(
            query,
            num_results=num_results,
            contents={"text": {"maxCharacters": max_characters}},
        )

        results: list[ExaSearchResult] = []
        for result in response.results:
            # Extract text snippet
            snippet = None
            if hasattr(result, "text") and result.text:
                snippet = result.text[:500]

            results.append(
                ExaSearchResult(
                    title=result.title or "Untitled",
                    url=result.url,
                    snippet=snippet,
                    published_date=getattr(result, "published_date", None),
                )
            )

        logger.info(f"Exa search returned {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"Exa search failed: {e}")
        return []


def format_exa_results_for_context(results: list[ExaSearchResult]) -> str:
    """Format Exa search results as context string for LLM.

    Args:
        results: List of search results.

    Returns:
        Formatted string suitable for including in LLM context.
    """
    if not results:
        return "No web search results found."

    lines = ["Web search results:"]
    for i, result in enumerate(results, 1):
        lines.append(f"\n[{i}] {result.title}")
        lines.append(f"    URL: {result.url}")
        if result.snippet:
            lines.append(f"    {result.snippet[:300]}...")

    return "\n".join(lines)
