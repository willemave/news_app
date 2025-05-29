import praw
from typing import List, Dict

from app.config import settings
from .aggregator import scrape_url
from app.llm import summarize_article


def fetch_frontpage_posts(limit: int = 100) -> List[Dict[str, str]]:
    """Fetch top posts from Reddit's front page and summarize their content."""
    reddit = praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_CLIENT_SECRET,
        user_agent=settings.REDDIT_USER_AGENT,
    )

    results = []
    for submission in reddit.front.top(limit=limit):
        if submission.is_self:
            content = submission.selftext or ""
        else:
            scraped = scrape_url(submission.url)
            content = scraped.get("content", "") if scraped else ""

        short_sum, detailed_sum = summarize_article(content)
        results.append(
            {
                "title": submission.title,
                "url": submission.url,
                "short_summary": short_sum,
                "detailed_summary": detailed_sum,
            }
        )
    return results
