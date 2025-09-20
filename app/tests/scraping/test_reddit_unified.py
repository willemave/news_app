from collections.abc import Generator
from typing import Any

import pytest
from pytest_mock import MockerFixture

from app.scraping.reddit_unified import REDDIT_USER_AGENT, RedditUnifiedScraper


@pytest.fixture
def mock_httpx_client(mocker: MockerFixture) -> Generator[Any, None, None]:
    """Patch httpx.Client context manager to capture request arguments."""
    mock_client_instance = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.json.return_value = {}
    mock_response.raise_for_status.return_value = None
    mock_client_instance.get.return_value = mock_response

    mock_client_cls = mocker.patch("app.scraping.reddit_unified.httpx.Client")
    mock_client_cls.return_value.__enter__.return_value = mock_client_instance
    mock_client_cls.return_value.__exit__.return_value = None

    yield mock_client_instance


def test_reddit_scraper_sets_required_user_agent(mock_httpx_client: Any) -> None:
    scraper = RedditUnifiedScraper()
    scraper.subreddits = {"artificial": 5}

    scraper.scrape()

    mock_httpx_client.get.assert_called_with(
        "https://www.reddit.com/r/artificial/new.json",
        params={"limit": 5},
        headers={"User-Agent": REDDIT_USER_AGENT},
    )
