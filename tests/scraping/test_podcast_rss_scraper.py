import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from app.scraping.podcast_rss_scraper import PodcastRSSScraper
from app.models import Podcasts, PodcastStatus


class TestPodcastRSSScraperExistingPodcasts:
    """Test that existing podcasts continue processing instead of being skipped."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        with patch('app.scraping.podcast_rss_scraper.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            yield mock_session

    @pytest.fixture
    def scraper(self):
        """Create a scraper instance with mock feeds."""
        with patch('app.scraping.podcast_rss_scraper.load_podcast_feeds') as mock_load:
            mock_load.return_value = [
                {'name': 'Test Podcast', 'url': 'http://example.com/feed.xml', 'limit': 5}
            ]
            return PodcastRSSScraper()

    def test_existing_podcast_new_status_queues_download(self, scraper, mock_db_session):
        """Test that existing podcast with 'new' status gets queued for download."""
        # Mock existing podcast with 'new' status
        existing_podcast = Mock()
        existing_podcast.id = 123
        existing_podcast.status.value = 'new'
        existing_podcast.enclosure_url = 'http://example.com/audio.mp3'
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_podcast
        
        # Mock the download task
        with patch('app.queue.download_podcast_task') as mock_download_task:
            # Create mock entry
            entry = {
                'title': 'Test Episode',
                'link': 'http://example.com/episode1',
                'enclosures': [Mock(href='http://example.com/audio.mp3', type='audio/mpeg')]
            }
            
            scraper.create_podcast_record(entry, 'Test Podcast', 'http://example.com/audio.mp3')
            
            # Verify download task was called
            mock_download_task.assert_called_once_with(123)

    def test_existing_podcast_downloaded_status_queues_transcription(self, scraper, mock_db_session):
        """Test that existing podcast with 'downloaded' status gets queued for transcription."""
        # Mock existing podcast with 'downloaded' status
        existing_podcast = Mock()
        existing_podcast.id = 456
        existing_podcast.status.value = 'downloaded'
        existing_podcast.enclosure_url = 'http://example.com/audio.mp3'
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_podcast
        
        # Mock the transcription task
        with patch('app.queue.transcribe_podcast_task') as mock_transcribe_task:
            # Create mock entry
            entry = {
                'title': 'Test Episode',
                'link': 'http://example.com/episode1',
                'enclosures': [Mock(href='http://example.com/audio.mp3', type='audio/mpeg')]
            }
            
            scraper.create_podcast_record(entry, 'Test Podcast', 'http://example.com/audio.mp3')
            
            # Verify transcription task was called
            mock_transcribe_task.assert_called_once_with(456)

    def test_existing_podcast_transcribed_status_queues_summarization(self, scraper, mock_db_session):
        """Test that existing podcast with 'transcribed' status gets queued for summarization."""
        # Mock existing podcast with 'transcribed' status
        existing_podcast = Mock()
        existing_podcast.id = 789
        existing_podcast.status.value = 'transcribed'
        existing_podcast.enclosure_url = 'http://example.com/audio.mp3'
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_podcast
        
        # Mock the summarization task
        with patch('app.queue.summarize_podcast_task') as mock_summarize_task:
            # Create mock entry
            entry = {
                'title': 'Test Episode',
                'link': 'http://example.com/episode1',
                'enclosures': [Mock(href='http://example.com/audio.mp3', type='audio/mpeg')]
            }
            
            scraper.create_podcast_record(entry, 'Test Podcast', 'http://example.com/audio.mp3')
            
            # Verify summarization task was called
            mock_summarize_task.assert_called_once_with(789)

    def test_existing_podcast_summarized_status_no_action(self, scraper, mock_db_session):
        """Test that existing podcast with 'summarized' status takes no action."""
        # Mock existing podcast with 'summarized' status
        existing_podcast = Mock()
        existing_podcast.id = 999
        existing_podcast.status.value = 'summarized'
        existing_podcast.enclosure_url = 'http://example.com/audio.mp3'
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_podcast
        
        # Mock all tasks to ensure none are called
        with patch('app.queue.download_podcast_task') as mock_download, \
             patch('app.queue.transcribe_podcast_task') as mock_transcribe, \
             patch('app.queue.summarize_podcast_task') as mock_summarize:
            
            # Create mock entry
            entry = {
                'title': 'Test Episode',
                'link': 'http://example.com/episode1',
                'enclosures': [Mock(href='http://example.com/audio.mp3', type='audio/mpeg')]
            }
            
            scraper.create_podcast_record(entry, 'Test Podcast', 'http://example.com/audio.mp3')
            
            # Verify no tasks were called
            mock_download.assert_not_called()
            mock_transcribe.assert_not_called()
            mock_summarize.assert_not_called()

    def test_existing_podcast_enclosure_url_update(self, scraper, mock_db_session):
        """Test that enclosure URL gets updated if it has changed."""
        # Mock existing podcast with different enclosure URL
        existing_podcast = Mock()
        existing_podcast.id = 111
        existing_podcast.status.value = 'summarized'
        existing_podcast.enclosure_url = 'http://example.com/old_audio.mp3'
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_podcast
        
        # Create mock entry with new enclosure URL
        entry = {
            'title': 'Test Episode',
            'link': 'http://example.com/episode1',
            'enclosures': [Mock(href='http://example.com/new_audio.mp3', type='audio/mpeg')]
        }
        
        scraper.create_podcast_record(entry, 'Test Podcast', 'http://example.com/new_audio.mp3')
        
        # Verify enclosure URL was updated
        assert existing_podcast.enclosure_url == 'http://example.com/new_audio.mp3'
        mock_db_session.commit.assert_called()

    def test_existing_podcast_failed_status_no_action(self, scraper, mock_db_session):
        """Test that existing podcast with 'failed' status takes no action."""
        # Mock existing podcast with 'failed' status
        existing_podcast = Mock()
        existing_podcast.id = 888
        existing_podcast.status.value = 'failed'
        existing_podcast.enclosure_url = 'http://example.com/audio.mp3'
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_podcast
        
        # Mock all tasks to ensure none are called
        with patch('app.queue.download_podcast_task') as mock_download, \
             patch('app.queue.transcribe_podcast_task') as mock_transcribe, \
             patch('app.queue.summarize_podcast_task') as mock_summarize:
            
            # Create mock entry
            entry = {
                'title': 'Test Episode',
                'link': 'http://example.com/episode1',
                'enclosures': [Mock(href='http://example.com/audio.mp3', type='audio/mpeg')]
            }
            
            scraper.create_podcast_record(entry, 'Test Podcast', 'http://example.com/audio.mp3')
            
            # Verify no tasks were called
            mock_download.assert_not_called()
            mock_transcribe.assert_not_called()
            mock_summarize.assert_not_called()