#!/usr/bin/env python3
"""
Generate test data for the news_app database.

This script creates realistic test data that exercises all fields in the metadata models
(ArticleMetadata, PodcastMetadata, NewsMetadata) with properly structured summaries.

Features:
- Generates articles, podcasts, and news items with complete metadata
- Creates structured summaries with bullet points, quotes, topics, questions, and counter-arguments
- Mimics the structure from app/tests/fixtures/content_samples.json
- Supports flexible configuration via command-line arguments
- Includes items in various states (new, processing, completed) by default

Usage:
    # Generate default amounts (10 articles, 5 podcasts, 15 news items)
    python scripts/generate_test_data.py

    # Custom amounts
    python scripts/generate_test_data.py --articles 20 --podcasts 10 --news 30

    # Only completed items (no pending/processing states)
    python scripts/generate_test_data.py --no-pending

    # Dry run (generate but don't insert)
    python scripts/generate_test_data.py --dry-run

Examples:
    # Large dataset for performance testing
    python scripts/generate_test_data.py --articles 100 --podcasts 50 --news 200

    # Minimal dataset for quick testing
    python scripts/generate_test_data.py --articles 2 --podcasts 1 --news 3
"""

from __future__ import annotations

import os
import random
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from app.core.db import get_db, init_db
from app.models.metadata import (
    ArticleMetadata,
    ContentQuote,
    ContentStatus,
    ContentType,
    NewsSummary,
    PodcastMetadata,
    StructuredSummary,
    SummaryBulletPoint,
)
from app.models.schema import Content

# Sample data pools
ARTICLE_SOURCES = [
    "Import AI",
    "Stratechery",
    "hackernews",
    "Benedict Evans",
    "Lex Fridman Blog",
]

PODCAST_SOURCES = [
    "Lenny's Podcast",
    "BG2 Pod",
    "Acquired",
    "All-In Podcast",
    "The Knowledge Project",
]

NEWS_PLATFORMS = ["hackernews", "techmeme", "reddit"]

TOPICS = [
    ["AI", "Machine Learning", "Technology"],
    ["Startups", "Venture Capital", "Business"],
    ["Software Engineering", "DevOps", "Cloud"],
    ["Cybersecurity", "Privacy", "Ethics"],
    ["Product Management", "Design", "UX"],
    ["Leadership", "Management", "Career"],
    ["Economics", "Finance", "Markets"],
]

ARTICLE_TITLES = [
    "Understanding Modern Machine Learning Architectures",
    "The Future of Distributed Systems at Scale",
    "Building Resilient Microservices with Kubernetes",
    "How AI is Transforming Software Development",
    "The Economics of Open Source Software",
    "Scaling Engineering Teams: Lessons Learned",
    "Deep Dive into Rust's Memory Safety Model",
    "The Evolution of NoSQL Databases",
]

PODCAST_TITLES = [
    "Building the Next Generation of AI Products",
    "From Startup to IPO: The Journey",
    "Mastering Product-Market Fit",
    "The Art of Engineering Leadership",
    "Investing in Early-Stage Startups",
    "Building Developer Tools That Scale",
]

NEWS_HEADLINES = [
    "OpenAI Announces GPT-5 with Enhanced Reasoning Capabilities",
    "Major Tech Company Acquires AI Startup for $2B",
    "New Breakthrough in Quantum Computing Stability",
    "Security Flaw Discovered in Popular Open Source Library",
    "Federal Reserve Announces Interest Rate Decision",
]


def random_datetime(days_back: int = 30) -> datetime:
    """Generate a random datetime within the last N days."""
    delta = timedelta(days=random.randint(0, days_back))
    return datetime.now(UTC).replace(tzinfo=None) - delta


def generate_bullet_points(count: int = 4) -> list[dict[str, str]]:
    """Generate sample bullet points with categories."""
    categories = ["key_finding", "methodology", "conclusion", "insight", "context", "review"]
    points = [
        "The research introduces a novel approach to solving the problem with innovative techniques.",
        "Experimental results demonstrate significant improvements over baseline methods.",
        "The methodology combines existing frameworks with new optimization strategies.",
        "Key findings suggest a paradigm shift in how we approach this domain.",
        "Implementation details reveal important trade-offs between performance and complexity.",
        "The author provides comprehensive analysis backed by empirical evidence.",
    ]

    return [
        {"text": random.choice(points), "category": random.choice(categories)} for _ in range(count)
    ]


def generate_quotes(count: int = 2) -> list[dict[str, str]]:
    """Generate sample quotes with context."""
    quotes = [
        (
            "The future belongs to those who understand both the technical and business implications of AI.",
            "Author's perspective",
        ),
        (
            "We're not just building technology; we're shaping how humans interact with machines.",
            "CEO Interview",
        ),
        (
            "The key to success in this field is relentless iteration and learning from failure.",
            "Industry Expert",
        ),
    ]

    return [
        {"text": text, "context": ctx}
        for text, ctx in random.sample(quotes, min(count, len(quotes)))
    ]


def generate_questions(count: int = 2) -> list[str]:
    """Generate thought-provoking questions."""
    questions = [
        "How might this technology impact existing industry practices?",
        "What are the potential ethical implications of widespread adoption?",
        "Could this approach be applied to other domains effectively?",
        "What barriers exist to implementing this at scale?",
    ]
    return random.sample(questions, min(count, len(questions)))


def generate_counter_arguments(count: int = 2) -> list[str]:
    """Generate counter-arguments or alternative perspectives."""
    arguments = [
        "Critics argue that the claimed improvements may not generalize beyond specific benchmarks.",
        "Alternative approaches might offer better explainability at the cost of performance.",
        "The methodology's reliance on proprietary data limits reproducibility.",
        "Some researchers question whether the results justify the computational costs.",
    ]
    return random.sample(arguments, min(count, len(arguments)))


class ArticleGenerator:
    """Generate article test data with full metadata."""

    @staticmethod
    def generate(
        url_base: str = "https://example.com/article",
        status: str = ContentStatus.COMPLETED.value,
    ) -> dict[str, Any]:
        """Generate a complete article with metadata."""
        article_id = random.randint(1000, 999999)
        url = f"{url_base}-{article_id}"
        title = random.choice(ARTICLE_TITLES)
        source = random.choice(ARTICLE_SOURCES)
        topics = random.choice(TOPICS)

        # Generate structured summary
        summary = StructuredSummary(
            title=title,
            overview=f"This article explores {topics[0].lower()} with a focus on practical applications and future implications. It provides comprehensive analysis backed by research and real-world examples.",
            bullet_points=[
                SummaryBulletPoint(**bp) for bp in generate_bullet_points(random.randint(3, 6))
            ],
            quotes=[ContentQuote(**q) for q in generate_quotes(random.randint(1, 3))],
            topics=topics,
            questions=generate_questions(random.randint(1, 3)),
            counter_arguments=generate_counter_arguments(random.randint(1, 2)),
            summarization_date=random_datetime(7),
            classification="to_read" if random.random() > 0.2 else "skip",
            full_markdown=f"# {title}\n\nFull article content in markdown format...",
        )

        # Generate article metadata
        metadata = ArticleMetadata(
            source=source,
            content="Full article text content with multiple paragraphs...",
            author=f"{random.choice(['John', 'Jane', 'Alex'])} {random.choice(['Smith', 'Doe', 'Johnson'])}",
            publication_date=random_datetime(30),
            content_type="html",
            final_url_after_redirects=url,
            word_count=random.randint(500, 3000),
            summary=summary,
        )

        return {
            "content_type": ContentType.ARTICLE.value,
            "url": url,
            "title": title,
            "source": source,
            "platform": "web",
            "status": status,
            "classification": summary.classification,
            "content_metadata": metadata.model_dump(mode="json", exclude_none=True),
            "publication_date": metadata.publication_date,
            "processed_at": random_datetime(5) if status == ContentStatus.COMPLETED.value else None,
        }


class PodcastGenerator:
    """Generate podcast test data with full metadata."""

    @staticmethod
    def generate(
        url_base: str = "https://example.com/podcast",
        status: str = ContentStatus.COMPLETED.value,
    ) -> dict[str, Any]:
        """Generate a complete podcast with metadata."""
        episode_id = random.randint(1000, 999999)
        url = f"{url_base}/episode-{episode_id}.mp3"
        title = random.choice(PODCAST_TITLES)
        source = random.choice(PODCAST_SOURCES)
        topics = random.choice(TOPICS)
        episode_number = random.randint(1, 200)

        # Generate structured summary
        summary = StructuredSummary(
            title=title,
            overview=f"In this episode, the hosts discuss {topics[0].lower()} and share insights from their experiences. The conversation covers key strategies, common pitfalls, and actionable advice for listeners.",
            bullet_points=[
                SummaryBulletPoint(**bp) for bp in generate_bullet_points(random.randint(4, 8))
            ],
            quotes=[ContentQuote(**q) for q in generate_quotes(random.randint(2, 4))],
            topics=topics,
            questions=generate_questions(random.randint(2, 3)),
            counter_arguments=generate_counter_arguments(random.randint(1, 2)),
            summarization_date=random_datetime(7),
            classification="to_read" if random.random() > 0.15 else "skip",
            full_markdown=f"# {title}\n\nFull episode summary in markdown...",
        )

        # Generate podcast metadata
        metadata = PodcastMetadata(
            source=source,
            audio_url=url,
            transcript="Welcome to the podcast. Today we're discussing... [full transcript]",
            duration=random.randint(1200, 7200),
            episode_number=episode_number,
            word_count=random.randint(3000, 10000),
            summary=summary,
        )

        return {
            "content_type": ContentType.PODCAST.value,
            "url": url,
            "title": title,
            "source": source,
            "platform": "podcast",
            "status": status,
            "classification": summary.classification,
            "content_metadata": metadata.model_dump(mode="json", exclude_none=True),
            "publication_date": random_datetime(60),
            "processed_at": random_datetime(5) if status == ContentStatus.COMPLETED.value else None,
        }


class NewsGenerator:
    """Generate news test data with full metadata."""

    @staticmethod
    def generate(
        url_base: str = "https://example.com/news",
        status: str = ContentStatus.COMPLETED.value,
    ) -> dict[str, Any]:
        """Generate a complete news item with metadata."""
        news_id = random.randint(1000, 999999)
        article_url = f"{url_base}/story-{news_id}"
        headline = random.choice(NEWS_HEADLINES)
        platform = random.choice(NEWS_PLATFORMS)
        source_domain = "example.com"

        # Generate news summary
        summary = NewsSummary(
            title=headline,
            article_url=article_url,
            key_points=[
                "Major announcement reveals significant industry impact",
                "Experts predict long-term implications for the sector",
                "Initial reactions from market analysts are mixed",
            ],
            summary="Breaking news with significant implications for the technology industry and broader markets.",
            classification="to_read" if random.random() > 0.3 else "skip",
            summarization_date=random_datetime(3),
        )

        # Generate news metadata
        metadata = {
            "source": source_domain,
            "platform": platform,
            "article": {
                "url": article_url,
                "title": headline,
                "source_domain": source_domain,
            },
            "aggregator": {
                "name": "Hacker News" if platform == "hackernews" else "Techmeme",
                "url": f"https://news.ycombinator.com/item?id={news_id}"
                if platform == "hackernews"
                else f"https://techmeme.com/{news_id}",
                "external_id": str(news_id),
                "metadata": {"score": random.randint(50, 500)} if platform == "hackernews" else {},
            },
            "discovery_time": random_datetime(2),
            "summary": summary.model_dump(mode="json", exclude_none=True),
        }

        return {
            "content_type": ContentType.NEWS.value,
            "url": article_url,
            "title": headline,
            "source": source_domain,
            "platform": platform,
            "status": status,
            "classification": summary.classification,
            "content_metadata": metadata,
            "publication_date": random_datetime(7),
            "processed_at": random_datetime(2) if status == ContentStatus.COMPLETED.value else None,
        }


def generate_test_data(
    num_articles: int = 10,
    num_podcasts: int = 5,
    num_news: int = 15,
    include_pending: bool = True,
) -> list[dict[str, Any]]:
    """
    Generate a mix of test data across all content types.

    Args:
        num_articles: Number of articles to generate
        num_podcasts: Number of podcasts to generate
        num_news: Number of news items to generate
        include_pending: Include some items in pending/processing states

    Returns:
        List of content dictionaries ready for database insertion
    """
    data = []

    # Generate articles
    for i in range(num_articles):
        if include_pending and i % 5 == 0:
            status = random.choice([ContentStatus.NEW.value, ContentStatus.PROCESSING.value])
        else:
            status = ContentStatus.COMPLETED.value
        data.append(ArticleGenerator.generate(status=status))

    # Generate podcasts
    for i in range(num_podcasts):
        if include_pending and i % 4 == 0:
            status = random.choice([ContentStatus.NEW.value, ContentStatus.PROCESSING.value])
        else:
            status = ContentStatus.COMPLETED.value
        data.append(PodcastGenerator.generate(status=status))

    # Generate news
    for i in range(num_news):
        if include_pending and i % 6 == 0:
            status = random.choice([ContentStatus.NEW.value, ContentStatus.PROCESSING.value])
        else:
            status = ContentStatus.COMPLETED.value
        data.append(NewsGenerator.generate(status=status))

    return data


def insert_test_data(session: Session, data: list[dict[str, Any]]) -> list[int]:
    """
    Insert test data into the database.

    Args:
        session: SQLAlchemy session
        data: List of content dictionaries

    Returns:
        List of inserted content IDs
    """
    inserted_ids = []

    for item in data:
        content = Content(**item)
        session.add(content)
        session.flush()  # Get the ID
        inserted_ids.append(content.id)

    session.commit()
    return inserted_ids


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate test data for news_app")
    parser.add_argument("--articles", type=int, default=10, help="Number of articles to generate")
    parser.add_argument("--podcasts", type=int, default=5, help="Number of podcasts to generate")
    parser.add_argument("--news", type=int, default=15, help="Number of news items to generate")
    parser.add_argument(
        "--no-pending",
        action="store_true",
        help="Don't include items in pending/processing states",
    )
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't insert data")

    args = parser.parse_args()

    # Generate data
    print("Generating test data:")
    print(f"  - {args.articles} articles")
    print(f"  - {args.podcasts} podcasts")
    print(f"  - {args.news} news items")

    data = generate_test_data(
        num_articles=args.articles,
        num_podcasts=args.podcasts,
        num_news=args.news,
        include_pending=not args.no_pending,
    )

    if args.dry_run:
        print(f"\nDry run - generated {len(data)} items (not inserted)")
        print("\nSample article:")
        article_sample = next((d for d in data if d["content_type"] == "article"), None)
        if article_sample:
            print(f"  Title: {article_sample['title']}")
            print(f"  Source: {article_sample['source']}")
            print(f"  Status: {article_sample['status']}")
        return

    # Insert into database
    print("\nInserting data into database...")
    init_db()
    with get_db() as session:
        inserted_ids = insert_test_data(session, data)

    print(f"\nSuccessfully inserted {len(inserted_ids)} items")
    print(f"  IDs: {min(inserted_ids)} - {max(inserted_ids)}")

    # Print summary by type
    articles = sum(1 for d in data if d["content_type"] == "article")
    podcasts = sum(1 for d in data if d["content_type"] == "podcast")
    news = sum(1 for d in data if d["content_type"] == "news")

    print("\nBreakdown:")
    print(f"  Articles: {articles}")
    print(f"  Podcasts: {podcasts}")
    print(f"  News: {news}")


if __name__ == "__main__":
    main()
