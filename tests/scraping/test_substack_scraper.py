import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

from app.scraping.substack_unified import SubstackScraper, load_substack_feeds
from app.models.schema import Content, ContentStatus
from app.models.metadata import ContentType

# Sample YAML content
SAMPLE_YAML = """
feeds:
  - url: "http://test.com/feed"
"""

SAMPLE_YAML_WITH_LIMIT = """
feeds:
  - url: "http://test.com/feed"
    name: "Test Feed"
    limit: 2
"""

# Sample feedparser entry
mock_entry_article = {
    'title': 'Test Article',
    'link': 'http://test.com/article',
    'author': 'Test Author',
    'published_parsed': (2025, 6, 7, 12, 0, 0, 5, 158, 0),
    'content': [{'type': 'text/html', 'value': '<p>Test Content</p>'}],
    'id': 'test-entry-123'
}

mock_entry_podcast = {
    'title': 'My Test Podcast Episode',
    'link': 'http://podcast.com/episode',
    'author': 'Podcast Host',
    'published_parsed': (2025, 6, 7, 13, 0, 0, 5, 158, 0),
    'summary': 'A summary of the podcast.',
    'id': 'podcast-entry-456'
}


@pytest.fixture
def mock_db_session():
    """Fixture for a mocked database session."""
    with patch('app.scraping.base.get_db') as mock_get_db:
        mock_session = MagicMock()
        # Configure query chains to simulate no existing data
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_queue_service():
    """Fixture for mocked queue service."""
    with patch('app.scraping.base.get_queue_service') as mock_get_queue:
        mock_service = MagicMock()
        mock_get_queue.return_value = mock_service
        yield mock_service


def test_load_substack_feeds():
    """Test loading feeds from a YAML file."""
    with patch('builtins.open', mock_open(read_data=SAMPLE_YAML)) as mock_file:
        feeds = load_substack_feeds('dummy/path.yml')
        assert len(feeds) == 1
        assert feeds[0]['url'] == 'http://test.com/feed'
        assert feeds[0]['name'] == 'Unknown Substack'  # Default name when not specified
        assert feeds[0]['limit'] == 10  # Default limit when not specified
        mock_file.assert_called_once_with('dummy/path.yml')


def test_load_substack_feeds_with_limit():
    """Test loading feeds with limit from a YAML file."""
    with patch('builtins.open', mock_open(read_data=SAMPLE_YAML_WITH_LIMIT)) as mock_file:
        feeds = load_substack_feeds('dummy/path.yml')
        assert len(feeds) == 1
        assert feeds[0]['url'] == 'http://test.com/feed'
        assert feeds[0]['name'] == 'Test Feed'
        assert feeds[0]['limit'] == 2  # Specific limit from config
        mock_file.assert_called_once_with('dummy/path.yml')


@pytest.mark.asyncio
@patch('app.scraping.substack_unified.feedparser.parse')
async def test_scrape_process_and_filter(mock_feedparser_parse, mock_db_session, mock_queue_service):
    """Test the full scrape and process flow, including filtering."""
    # Mock feedparser results
    mock_feed_result = MagicMock()
    mock_feed_result.bozo = 0
    mock_feed_result.entries = [mock_entry_article]
    # Add feed metadata
    mock_feed_result.feed = {
        'title': 'Test Feed',
        'description': 'A test feed for testing'
    }
    mock_feedparser_parse.return_value = mock_feed_result

    # Create scraper with mocked feeds
    with patch('app.scraping.substack_unified.load_substack_feeds') as mock_load_feeds:
        mock_load_feeds.return_value = [{'url': 'http://test.com/feed', 'name': 'Test Feed', 'limit': 10}]
        
        scraper = SubstackScraper()
        items = await scraper.scrape()

        # Verify one item was processed
        assert len(items) == 1
        
        item = items[0]
        assert item['url'] == 'https://test.com/article'  # Note: normalized to https
        assert item['title'] == 'Test Article'
        assert item['content_type'] == ContentType.ARTICLE
        assert item['metadata']['source'] == 'Test Feed'
        assert item['metadata']['feed_name'] == 'Test Feed'
        assert item['metadata']['author'] == 'Test Author'


@pytest.mark.asyncio
@patch('app.scraping.substack_unified.feedparser.parse')
async def test_scrape_filters_podcasts(mock_feedparser_parse, mock_db_session, mock_queue_service):
    """Test that podcast entries are filtered out."""
    # Mock feedparser results with podcast entry
    mock_feed_result = MagicMock()
    mock_feed_result.bozo = 0
    mock_feed_result.entries = [mock_entry_podcast]
    mock_feed_result.feed = {
        'title': 'Test Feed',
        'description': 'A test feed'
    }
    mock_feedparser_parse.return_value = mock_feed_result

    # Create scraper with mocked feeds
    with patch('app.scraping.substack_unified.load_substack_feeds') as mock_load_feeds:
        mock_load_feeds.return_value = [{'url': 'http://test.com/feed', 'name': 'Test Feed', 'limit': 10}]
        
        scraper = SubstackScraper()
        items = await scraper.scrape()

        # Verify podcast was filtered out
        assert len(items) == 0


@pytest.mark.asyncio
@patch('app.scraping.substack_unified.feedparser.parse')
async def test_scrape_handles_missing_link(mock_feedparser_parse, mock_db_session, mock_queue_service):
    """Test handling of entries without links."""
    # Mock entry without link
    bad_entry = {
        'title': 'Entry Without Link',
        'author': 'Test Author',
        'published_parsed': (2025, 6, 7, 12, 0, 0, 5, 158, 0),
        'content': [{'type': 'text/html', 'value': '<p>Content</p>'}]
    }
    
    mock_feed_result = MagicMock()
    mock_feed_result.bozo = 0
    mock_feed_result.entries = [bad_entry]
    mock_feed_result.feed = {
        'title': 'Test Feed',
        'description': 'A test feed'
    }
    mock_feedparser_parse.return_value = mock_feed_result

    # Create scraper with mocked feeds
    with patch('app.scraping.substack_unified.load_substack_feeds') as mock_load_feeds:
        mock_load_feeds.return_value = [{'url': 'http://test.com/feed', 'name': 'Test Feed', 'limit': 10}]
        
        scraper = SubstackScraper()
        items = await scraper.scrape()

        # Verify entry was skipped
        assert len(items) == 0


@pytest.mark.asyncio
async def test_run_saves_to_database(mock_db_session, mock_queue_service):
    """Test that run() saves items to database and queues tasks."""
    with patch('app.scraping.substack_unified.feedparser.parse') as mock_feedparser_parse:
        # Mock feedparser results
        mock_feed_result = MagicMock()
        mock_feed_result.bozo = 0
        mock_feed_result.entries = [mock_entry_article]
        mock_feed_result.feed = {
            'title': 'Test Feed',
            'description': 'A test feed'
        }
        mock_feedparser_parse.return_value = mock_feed_result

        # Create scraper with mocked feeds
        with patch('app.scraping.substack_unified.load_substack_feeds') as mock_load_feeds:
            mock_load_feeds.return_value = [{'url': 'http://test.com/feed', 'name': 'Test Feed', 'limit': 10}]
            
            scraper = SubstackScraper()
            saved_count = await scraper.run()

            # Verify item was saved
            assert saved_count == 1
            
            # Verify database operations
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once()
            
            # Verify the created content object
            created_content = mock_db_session.add.call_args[0][0]
            assert isinstance(created_content, Content)
            assert created_content.content_type == ContentType.ARTICLE.value
            assert created_content.url == 'https://test.com/article'
            assert created_content.title == 'Test Article'
            assert created_content.status == ContentStatus.NEW.value
            
            # Verify task was queued
            mock_queue_service.enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_run_skips_existing_urls(mock_db_session, mock_queue_service):
    """Test that run() skips URLs that already exist."""
    with patch('app.scraping.substack_unified.feedparser.parse') as mock_feedparser_parse:
        # Mock feedparser results
        mock_feed_result = MagicMock()
        mock_feed_result.bozo = 0
        mock_feed_result.entries = [mock_entry_article]
        mock_feed_result.feed = {
            'title': 'Test Feed',
            'description': 'A test feed'
        }
        mock_feedparser_parse.return_value = mock_feed_result

        # Mock existing content in database
        existing_content = Content()
        existing_content.url = 'https://test.com/article'
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_content

        # Create scraper with mocked feeds
        with patch('app.scraping.substack_unified.load_substack_feeds') as mock_load_feeds:
            mock_load_feeds.return_value = [{'url': 'http://test.com/feed', 'name': 'Test Feed', 'limit': 10}]
            
            scraper = SubstackScraper()
            saved_count = await scraper.run()

            # Verify no new items were saved
            assert saved_count == 0
            mock_db_session.add.assert_not_called()
            mock_queue_service.enqueue.assert_not_called()


def test_url_normalization():
    """Test URL normalization functionality."""
    scraper = SubstackScraper()
    
    # Test http to https conversion
    assert scraper._normalize_url('http://test.com/article') == 'https://test.com/article'
    
    # Test trailing slash removal
    assert scraper._normalize_url('https://test.com/article/') == 'https://test.com/article'
    
    # Test combined normalization
    assert scraper._normalize_url('http://test.com/article/') == 'https://test.com/article'


@pytest.mark.asyncio
@patch('app.scraping.substack_unified.feedparser.parse')
async def test_scrape_respects_limit(mock_feedparser_parse, mock_db_session, mock_queue_service):
    """Test that scraper respects the limit configuration."""
    # Create multiple entries
    entries = []
    for i in range(5):
        entries.append({
            'title': f'Test Article {i}',
            'link': f'http://test.com/article{i}',
            'author': 'Test Author',
            'published_parsed': (2025, 6, 7, 12, 0, 0, 5, 158, 0),
            'content': [{'type': 'text/html', 'value': f'<p>Content {i}</p>'}],
            'id': f'test-entry-{i}'
        })
    
    # Mock feedparser results
    mock_feed_result = MagicMock()
    mock_feed_result.bozo = 0
    mock_feed_result.entries = entries
    mock_feed_result.feed = {
        'title': 'Test Feed',
        'description': 'A test feed for testing'
    }
    mock_feedparser_parse.return_value = mock_feed_result

    # Create scraper with limit of 2
    with patch('app.scraping.substack_unified.load_substack_feeds') as mock_load_feeds:
        mock_load_feeds.return_value = [{'url': 'http://test.com/feed', 'name': 'Test Feed', 'limit': 2}]
        
        scraper = SubstackScraper()
        items = await scraper.scrape()

        # Verify only 2 items were processed despite having 5 entries
        assert len(items) == 2
        assert items[0]['title'] == 'Test Article 0'
        assert items[1]['title'] == 'Test Article 1'


@pytest.mark.asyncio
async def test_no_feeds_configured():
    """Test behavior when no feeds are configured."""
    with patch('app.scraping.substack_unified.load_substack_feeds') as mock_load_feeds:
        mock_load_feeds.return_value = []
        
        scraper = SubstackScraper()
        items = await scraper.scrape()
        
        assert len(items) == 0