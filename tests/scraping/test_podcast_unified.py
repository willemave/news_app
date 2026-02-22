import feedparser

from app.scraping.podcast_unified import PodcastUnifiedScraper


def _build_entry(data: dict) -> feedparser.FeedParserDict:
    return feedparser.FeedParserDict(data)


def _build_enclosure(href: str, enclosure_type: str | None = None) -> feedparser.FeedParserDict:
    payload = {"href": href}
    if enclosure_type is not None:
        payload["type"] = enclosure_type
    return feedparser.FeedParserDict(payload)


def test_podcast_fallback_uses_enclosure_when_link_missing() -> None:
    scraper = PodcastUnifiedScraper()
    entry = _build_entry(
        {
            "title": "Episode 1",
            "enclosures": [_build_enclosure("https://cdn.example.com/ep1.mp3", "audio/mpeg")],
        }
    )

    item = scraper._process_entry(
        entry,
        feed_name="Test Feed",
        feed_info={"title": "Test Feed"},
        feed_url="https://example.com/feed.xml",
        user_id=1,
    )

    assert item is not None
    assert item["url"] == "https://cdn.example.com/ep1.mp3"
    assert item["metadata"]["audio_url"] == "https://cdn.example.com/ep1.mp3"


def test_podcast_fallback_uses_alternate_link_when_link_missing() -> None:
    scraper = PodcastUnifiedScraper()
    entry = _build_entry(
        {
            "title": "Episode 2",
            "links": [
                feedparser.FeedParserDict(
                    {"href": "https://example.com/episode-2", "rel": "alternate", "type": "text/html"}
                )
            ],
            "enclosures": [_build_enclosure("https://cdn.example.com/ep2.mp3", "audio/mpeg")],
        }
    )

    item = scraper._process_entry(
        entry,
        feed_name="Test Feed",
        feed_info={"title": "Test Feed"},
        feed_url="https://example.com/feed.xml",
        user_id=1,
    )

    assert item is not None
    assert item["url"] == "https://example.com/episode-2"
    assert item["metadata"]["audio_url"] == "https://cdn.example.com/ep2.mp3"


def test_podcast_fallback_accepts_enclosure_without_type() -> None:
    scraper = PodcastUnifiedScraper()
    entry = _build_entry(
        {
            "title": "Episode 3",
            "enclosures": [_build_enclosure("https://cdn.example.com/ep3.MP3")],
        }
    )

    item = scraper._process_entry(
        entry,
        feed_name="Test Feed",
        feed_info={"title": "Test Feed"},
        feed_url="https://example.com/feed.xml",
        user_id=1,
    )

    assert item is not None
    assert item["url"] == "https://cdn.example.com/ep3.MP3"
    assert item["metadata"]["audio_url"] == "https://cdn.example.com/ep3.MP3"
