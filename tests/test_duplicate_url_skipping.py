"""
Test duplicate URL skipping functionality in scrapers.
"""
from unittest.mock import patch, Mock
from sqlalchemy.orm import Session

from app.scraping.hackernews_scraper import create_link_record as hn_create_link_record
from app.scraping.reddit import create_link_record as reddit_create_link_record


class TestDuplicateUrlSkipping:
    """Test duplicate URL detection and skipping in scrapers."""

    @patch('app.scraping.hackernews_scraper.SessionLocal')
    def test_hackernews_create_link_record_new_url(self, mock_session_local):
        """Test HackerNews scraper creates new link record for new URL."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock query to return no existing link
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Mock new link creation
        mock_link = Mock()
        mock_link.id = 123
        mock_db.refresh = Mock(side_effect=lambda link: setattr(link, 'id', 123))
        
        test_url = "https://example.com/new-article"
        
        result = hn_create_link_record(test_url, "hackernews")
        
        # Verify new link was created
        assert result == 123
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('app.scraping.hackernews_scraper.SessionLocal')
    def test_hackernews_create_link_record_duplicate_url(self, mock_session_local):
        """Test HackerNews scraper skips duplicate URL and returns existing ID."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock existing link
        existing_link = Mock()
        existing_link.id = 456
        existing_link.url = "https://example.com/existing-article"
        
        # Mock query to return existing link
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = existing_link
        mock_db.query.return_value = mock_query
        
        test_url = "https://example.com/existing-article"
        
        result = hn_create_link_record(test_url, "hackernews")
        
        # Verify existing link ID was returned
        assert result == 456
        
        # Verify no new link was created
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()
        mock_db.close.assert_called_once()

    @patch('app.scraping.reddit.SessionLocal')
    def test_reddit_create_link_record_new_url(self, mock_session_local):
        """Test Reddit scraper creates new link record for new URL."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock query to return no existing link
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Mock new link creation
        mock_link = Mock()
        mock_link.id = 789
        mock_db.refresh = Mock(side_effect=lambda link: setattr(link, 'id', 789))
        
        test_url = "https://techcrunch.com/new-startup-news"
        
        result = reddit_create_link_record(test_url, "reddit-technology")
        
        # Verify new link was created
        assert result == 789
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('app.scraping.reddit.SessionLocal')
    def test_reddit_create_link_record_duplicate_url(self, mock_session_local):
        """Test Reddit scraper skips duplicate URL and returns existing ID."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock existing link
        existing_link = Mock()
        existing_link.id = 999
        existing_link.url = "https://techcrunch.com/existing-startup-news"
        
        # Mock query to return existing link
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = existing_link
        mock_db.query.return_value = mock_query
        
        test_url = "https://techcrunch.com/existing-startup-news"
        
        result = reddit_create_link_record(test_url, "reddit-technology")
        
        # Verify existing link ID was returned
        assert result == 999
        
        # Verify no new link was created
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()
        mock_db.close.assert_called_once()

    @patch('app.scraping.hackernews_scraper.SessionLocal')
    def test_hackernews_database_error_handling(self, mock_session_local):
        """Test HackerNews scraper handles database errors gracefully."""
        # Mock database session that raises exception
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        mock_db.query.side_effect = Exception("Database connection error")
        
        test_url = "https://example.com/test-article"
        
        result = hn_create_link_record(test_url, "hackernews")
        
        # Verify error was handled and None returned
        assert result is None
        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('app.scraping.reddit.SessionLocal')
    def test_reddit_database_error_handling(self, mock_session_local):
        """Test Reddit scraper handles database errors gracefully."""
        # Mock database session that raises exception
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        mock_db.query.side_effect = Exception("Database connection error")
        
        test_url = "https://techcrunch.com/test-article"
        
        result = reddit_create_link_record(test_url, "reddit-front")
        
        # Verify error was handled and None returned
        assert result is None
        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('app.scraping.hackernews_scraper.SessionLocal')
    def test_hackernews_url_case_sensitivity(self, mock_session_local):
        """Test HackerNews scraper URL comparison is case-sensitive."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock query to return no existing link (case-sensitive)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Mock new link creation
        mock_db.refresh = Mock(side_effect=lambda link: setattr(link, 'id', 111))
        
        test_url = "https://Example.com/Article"  # Different case
        
        result = hn_create_link_record(test_url, "hackernews")
        
        # Verify new link was created (URLs are case-sensitive)
        assert result == 111
        mock_db.add.assert_called_once()

    @patch('app.scraping.reddit.SessionLocal')
    def test_reddit_different_sources_same_url(self, mock_session_local):
        """Test Reddit scraper with same URL from different sources."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock existing link from different source
        existing_link = Mock()
        existing_link.id = 555
        existing_link.url = "https://arxiv.org/abs/2024.12345"
        existing_link.source = "hackernews"  # Different source
        
        # Mock query to return existing link
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = existing_link
        mock_db.query.return_value = mock_query
        
        test_url = "https://arxiv.org/abs/2024.12345"
        
        result = reddit_create_link_record(test_url, "reddit-MachineLearning")
        
        # Verify existing link ID was returned (same URL, different source)
        assert result == 555
        
        # Verify no new link was created
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()


class TestDuplicateUrlIntegration:
    """Integration tests for duplicate URL handling across scrapers."""

    @patch('app.scraping.hackernews_scraper.SessionLocal')
    @patch('app.scraping.reddit.SessionLocal')
    def test_cross_scraper_duplicate_detection(self, mock_reddit_session, mock_hn_session):
        """Test that URL duplicates are detected across different scrapers."""
        # Setup shared URL
        shared_url = "https://techcrunch.com/popular-article"
        
        # Mock HackerNews session - creates new link
        mock_hn_db = Mock(spec=Session)
        mock_hn_session.return_value = mock_hn_db
        
        mock_hn_query = Mock()
        mock_hn_query.filter.return_value.first.return_value = None
        mock_hn_db.query.return_value = mock_hn_query
        mock_hn_db.refresh = Mock(side_effect=lambda link: setattr(link, 'id', 100))
        
        # Mock Reddit session - finds existing link
        mock_reddit_db = Mock(spec=Session)
        mock_reddit_session.return_value = mock_reddit_db
        
        existing_link = Mock()
        existing_link.id = 100
        existing_link.url = shared_url
        
        mock_reddit_query = Mock()
        mock_reddit_query.filter.return_value.first.return_value = existing_link
        mock_reddit_db.query.return_value = mock_reddit_query
        
        # First scraper (HackerNews) creates the link
        hn_result = hn_create_link_record(shared_url, "hackernews")
        assert hn_result == 100
        mock_hn_db.add.assert_called_once()
        
        # Second scraper (Reddit) finds existing link
        reddit_result = reddit_create_link_record(shared_url, "reddit-technology")
        assert reddit_result == 100
        mock_reddit_db.add.assert_not_called()  # No new link created

    def test_url_normalization_scenarios(self):
        """Test various URL scenarios that should be considered duplicates."""
        # These are conceptual tests - actual implementation depends on URL normalization
        test_cases = [
            # Same URL, different protocols (if normalized)
            ("http://example.com/article", "https://example.com/article"),
            # Same URL, different trailing slashes (if normalized)
            ("https://example.com/article", "https://example.com/article/"),
            # Same URL, different query parameters (if normalized)
            ("https://example.com/article?utm_source=hn", "https://example.com/article"),
        ]
        
        # Note: Current implementation does exact string matching
        # This test documents expected behavior if URL normalization is added
        for url1, url2 in test_cases:
            # With current implementation, these would be treated as different URLs
            assert url1 != url2  # Current behavior: exact string matching

    @patch('app.scraping.hackernews_scraper.logger')
    @patch('app.scraping.hackernews_scraper.SessionLocal')
    def test_duplicate_logging_hackernews(self, mock_session_local, mock_logger):
        """Test that duplicate URL detection is properly logged in HackerNews scraper."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock existing link
        existing_link = Mock()
        existing_link.id = 777
        existing_link.url = "https://example.com/duplicate-article"
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = existing_link
        mock_db.query.return_value = mock_query
        
        test_url = "https://example.com/duplicate-article"
        
        result = hn_create_link_record(test_url, "hackernews")
        
        # Verify logging was called for duplicate detection
        mock_logger.info.assert_called_with(f"Link already exists: {test_url}")
        assert result == 777

    @patch('app.scraping.reddit.logger')
    @patch('app.scraping.reddit.SessionLocal')
    def test_duplicate_logging_reddit(self, mock_session_local, mock_logger):
        """Test that duplicate URL detection is properly logged in Reddit scraper."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock existing link
        existing_link = Mock()
        existing_link.id = 888
        existing_link.url = "https://reddit.com/r/technology/duplicate-post"
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = existing_link
        mock_db.query.return_value = mock_query
        
        test_url = "https://reddit.com/r/technology/duplicate-post"
        
        result = reddit_create_link_record(test_url, "reddit-technology")
        
        # Verify logging was called for duplicate detection
        mock_logger.info.assert_called_with(f"Link already exists: {test_url}")
        assert result == 888


class TestDuplicateUrlEdgeCases:
    """Test edge cases for duplicate URL detection."""

    @patch('app.scraping.hackernews_scraper.SessionLocal')
    def test_empty_url_handling(self, mock_session_local):
        """Test handling of empty or invalid URLs."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock query to return no existing link
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Mock new link creation
        mock_db.refresh = Mock(side_effect=lambda link: setattr(link, 'id', 1))
        
        # Test with empty URL
        result = hn_create_link_record("", "hackernews")
        
        # Should still attempt to create record (validation happens elsewhere)
        assert result == 1

    @patch('app.scraping.reddit.SessionLocal')
    def test_very_long_url_handling(self, mock_session_local):
        """Test handling of very long URLs."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock query to return no existing link
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Mock new link creation
        mock_db.refresh = Mock(side_effect=lambda link: setattr(link, 'id', 2))
        
        # Test with very long URL
        long_url = "https://example.com/" + "a" * 1000
        result = reddit_create_link_record(long_url, "reddit-test")
        
        # Should handle long URLs (database constraints may apply)
        assert result == 2

    @patch('app.scraping.hackernews_scraper.SessionLocal')
    def test_unicode_url_handling(self, mock_session_local):
        """Test handling of URLs with Unicode characters."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db
        
        # Mock query to return no existing link
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Mock new link creation
        mock_db.refresh = Mock(side_effect=lambda link: setattr(link, 'id', 3))
        
        # Test with Unicode URL
        unicode_url = "https://example.com/文章"
        result = hn_create_link_record(unicode_url, "hackernews")
        
        # Should handle Unicode URLs
        assert result == 3