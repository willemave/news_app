from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import sys

sys.modules.setdefault("praw", SimpleNamespace(Reddit=MagicMock()))
sys.modules.setdefault("openai", SimpleNamespace(OpenAI=MagicMock()))

from app.scraping.reddit import fetch_frontpage_posts


def make_submission(title, url, is_self=False, selftext=""):
    sub = SimpleNamespace()
    sub.title = title
    sub.url = url
    sub.is_self = is_self
    sub.selftext = selftext
    return sub


def test_fetch_frontpage_posts():
    submissions = [
        make_submission("Self Post", "https://reddit.com/1", True, "some text"),
        make_submission("Link Post", "https://example.com", False, ""),
    ]

    mock_front = MagicMock()
    mock_front.top.return_value = submissions
    mock_reddit = MagicMock(front=mock_front)

    with patch("praw.Reddit", return_value=mock_reddit):
        with patch("app.scraping.reddit.scrape_url", return_value={"content": "link content"}) as mock_scrape:
            with patch("app.scraping.reddit.summarize_article", return_value=("short", "detailed")) as mock_sum:
                results = fetch_frontpage_posts(limit=2)

    mock_front.top.assert_called_once_with(limit=2)
    mock_scrape.assert_called_once_with("https://example.com")
    assert mock_sum.call_count == 2
    assert len(results) == 2
    assert results[0]["title"] == "Self Post"
    assert results[1]["url"] == "https://example.com"
