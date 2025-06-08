import pytest
from unittest.mock import patch, MagicMock, mock_open, call
import yaml

# Mock database models before importing the scraper
from app.models import Base
class MockArticle(Base):
    __tablename__ = 'articles'
# Add other models if needed

# Now import the scraper
from app.scraping.substack_scraper import SubstackScraper, load_substack_feeds

# Sample YAML content
SAMPLE_YAML = """
feeds:
  - url: "http://test.com/feed"
"""

# Sample feedparser entry
mock_entry_article = {
    'title': 'Test Article',
    'link': 'http://test.com/article',
    'author': 'Test Author',
    'published_parsed': (2025, 6, 7, 12, 0, 0, 5, 158, 0),
    'content': [{'type': 'text/html', 'value': '<p>Test Content</p>'}]
}

mock_entry_podcast = {
    'title': 'My Test Podcast Episode',
    'link': 'http://podcast.com/episode',
    'author': 'Podcast Host',
    'published_parsed': (2025, 6, 7, 13, 0, 0, 5, 158, 0),
    'summary': 'A summary of the podcast.'
}


@pytest.fixture
def mock_db_session():
    """Fixture for a mocked database session."""
    with patch('app.scraping.substack_scraper.SessionLocal') as mock_session_local:
        mock_session = MagicMock()
        # Configure query chains to simulate no existing data
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_session_local.return_value = mock_session
        yield mock_session

def test_load_substack_feeds():
    """Test loading feeds from a YAML file."""
    with patch('builtins.open', mock_open(read_data=SAMPLE_YAML)) as mock_file:
        feeds = load_substack_feeds('dummy/path.yml')
        assert len(feeds) == 1
        assert feeds[0] == 'http://test.com/feed'
        mock_file.assert_called_once_with('dummy/path.yml', 'r')

@patch('app.scraping.substack_scraper.load_substack_feeds')
@patch('app.scraping.substack_scraper.feedparser.parse')
def test_scrape_process_and_filter(mock_feedparser_parse, mock_load_feeds, mock_db_session):
    """Test the full scrape and process flow, including filtering."""
    # Mock the YAML config loading - now returns list of URLs
    mock_load_feeds.return_value = ['http://test.com/feed']

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

    # Mock file system operations
    with patch('builtins.open', mock_open()) as mock_file, \
         patch('os.makedirs') as mock_makedirs:

        scraper = SubstackScraper()
        scraper.scrape()

        # Assertions
        # 1. Make sure the directory creation was attempted
        mock_makedirs.assert_called_once_with("data/substack", exist_ok=True)

        # 2. Check that the article file was written
        # Verify the specific file we care about was opened
        expected_call = call('data/substack/Test-Article.md', 'w', encoding='utf-8')
        assert expected_call in mock_file.call_args_list
        mock_file().write.assert_called_once_with('<p>Test Content</p>')

        # 3. Verify database interactions for the article
        # Check that an Article and a Link were added
        assert mock_db_session.add.call_count == 2 # One for Link, one for Article
        
        # Check the Link object
        created_link = mock_db_session.add.call_args_list[0][0][0]
        assert created_link.url == 'http://test.com/article'
        assert created_link.source == 'substack'

        # Check the Article object
        created_article = mock_db_session.add.call_args_list[1][0][0]
        assert created_article.title == 'Test Article'
        assert created_article.url == 'http://test.com/article'
        assert created_article.local_path == 'data/substack/Test-Article.md'
        assert created_article.status == 'new'

        # 4. Verify the podcast was filtered and not processed
        # The DB session should only have been committed for the valid article
        mock_db_session.commit.call_count == 2