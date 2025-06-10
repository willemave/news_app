"""
Integration tests for scrapers with the new LinkPipelineOrchestrator.
Tests the complete flow from scraping to processing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.models import Links, Articles, LinkStatus, ArticleStatus
from app.links.pipeline_orchestrator import LinkPipelineOrchestrator
from app.database import SessionLocal


class TestScraperPipelineIntegration:
    """Integration tests for scrapers with the new pipeline."""

    @pytest.fixture
    def db_session(self):
        """Create a database session for testing."""
        session = SessionLocal()
        yield session
        session.close()

    @patch('app.scraping.hackernews_scraper.requests.get')
    @patch('app.links.link_processor.process_link_from_db')
    @patch('app.http_client.robust_http_client.RobustHttpClient')
    @patch('app.processing_strategies.factory.UrlProcessorFactory')
    def test_hackernews_scraper_with_pipeline(self, mock_factory, mock_http_client, mock_process_func, mock_requests, db_session):
        """Test HackerNews scraper integration with pipeline processing."""
        from app.scraping.hackernews_scraper import process_hackernews_articles
        
        # Mock HackerNews API response
        mock_response = Mock()
        mock_response.json.return_value = [1, 2, 3]  # Mock story IDs
        mock_response.status_code = 200
        mock_requests.return_value = mock_response
        
        # Mock individual story responses
        story_responses = [
            Mock(json=lambda: {
                'id': 1,
                'title': 'Test Story 1',
                'url': 'https://example.com/story1',
                'by': 'user1',
                'time': 1640995200,
                'score': 100
            }, status_code=200),
            Mock(json=lambda: {
                'id': 2,
                'title': 'Test Story 2',
                'url': 'https://example.com/story2',
                'by': 'user2',
                'time': 1640995300,
                'score': 150
            }, status_code=200),
            Mock(json=lambda: {
                'id': 3,
                'title': 'Test Story 3',
                'url': 'https://example.com/story3',
                'by': 'user3',
                'time': 1640995400,
                'score': 200
            }, status_code=200)
        ]
        
        # Configure requests.get to return different responses for different URLs
        def mock_get_side_effect(url):
            if 'topstories' in url:
                return mock_response
            elif 'item/1.json' in url:
                return story_responses[0]
            elif 'item/2.json' in url:
                return story_responses[1]
            elif 'item/3.json' in url:
                return story_responses[2]
            return Mock(status_code=404)
        
        mock_requests.side_effect = mock_get_side_effect
        
        # Mock successful link processing
        mock_process_func.return_value = True
        
        # Mock HTTP client and factory
        mock_http_client_instance = Mock()
        mock_http_client.return_value = mock_http_client_instance
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        
        # Run HackerNews scraper
        hn_stats = process_hackernews_articles()
        
        # Verify scraper created links
        assert hn_stats['total_links'] == 3
        assert hn_stats['queued_links'] == 3
        assert hn_stats['errors'] == 0
        
        # Verify links were created in database
        new_links = db_session.query(Links).filter(Links.status == LinkStatus.new).all()
        assert len(new_links) >= 3
        
        # Run pipeline to process the links
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=0.1)
        
        try:
            # Run a single cycle to process the links
            cycle_stats = orchestrator.run_single_cycle()
            
            # Verify processing occurred
            assert cycle_stats['processing']['total'] > 0
            assert cycle_stats['processing']['processed'] > 0
            
        finally:
            orchestrator.cleanup()

    @patch('app.scraping.reddit.praw.Reddit')
    @patch('app.links.link_processor.process_link_from_db')
    @patch('app.http_client.robust_http_client.RobustHttpClient')
    @patch('app.processing_strategies.factory.UrlProcessorFactory')
    def test_reddit_scraper_with_pipeline(self, mock_factory, mock_http_client, mock_process_func, mock_reddit, db_session):
        """Test Reddit scraper integration with pipeline processing."""
        from app.scraping.reddit import process_reddit_articles
        
        # Mock Reddit API
        mock_reddit_instance = Mock()
        mock_reddit.return_value = mock_reddit_instance
        
        # Mock subreddit and submissions
        mock_subreddit = Mock()
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        
        # Mock submissions
        mock_submission1 = Mock()
        mock_submission1.title = "Test Reddit Post 1"
        mock_submission1.url = "https://example.com/reddit1"
        mock_submission1.author.name = "reddit_user1"
        mock_submission1.created_utc = 1640995200
        mock_submission1.score = 50
        mock_submission1.is_self = False
        
        mock_submission2 = Mock()
        mock_submission2.title = "Test Reddit Post 2"
        mock_submission2.url = "https://example.com/reddit2"
        mock_submission2.author.name = "reddit_user2"
        mock_submission2.created_utc = 1640995300
        mock_submission2.score = 75
        mock_submission2.is_self = False
        
        mock_subreddit.top.return_value = [mock_submission1, mock_submission2]
        
        # Mock successful link processing
        mock_process_func.return_value = True
        
        # Mock HTTP client and factory
        mock_http_client_instance = Mock()
        mock_http_client.return_value = mock_http_client_instance
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        
        # Run Reddit scraper
        reddit_stats = process_reddit_articles(
            subreddit_name="technology",
            limit=10,
            time_filter="day"
        )
        
        # Verify scraper created links
        assert reddit_stats['total_posts'] == 2
        assert reddit_stats['external_links'] == 2
        assert reddit_stats['queued_links'] == 2
        assert reddit_stats['errors'] == 0
        
        # Verify links were created in database
        new_links = db_session.query(Links).filter(
            Links.status == LinkStatus.new,
            Links.source.like('reddit-%')
        ).all()
        assert len(new_links) >= 2
        
        # Run pipeline to process the links
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=0.1)
        
        try:
            # Run a single cycle to process the links
            cycle_stats = orchestrator.run_single_cycle()
            
            # Verify processing occurred
            assert cycle_stats['processing']['total'] > 0
            assert cycle_stats['processing']['processed'] > 0
            
        finally:
            orchestrator.cleanup()

    @patch('app.scraping.substack_scraper.feedparser.parse')
    @patch('app.scraping.substack_scraper.load_substack_feeds')
    @patch('builtins.open')
    @patch('os.makedirs')
    @patch('app.links.link_processor.process_link_from_db')
    @patch('app.http_client.robust_http_client.RobustHttpClient')
    @patch('app.processing_strategies.factory.UrlProcessorFactory')
    def test_substack_scraper_with_pipeline(self, mock_factory, mock_http_client, mock_process_func, 
                                          mock_makedirs, mock_open, mock_load_feeds, mock_feedparser, db_session):
        """Test Substack scraper integration with pipeline processing."""
        from app.scraping.substack_scraper import SubstackScraper
        
        # Mock feed loading
        mock_load_feeds.return_value = ['https://example.substack.com/feed']
        
        # Mock feedparser response
        mock_feed_result = Mock()
        mock_feed_result.bozo = 0
        mock_feed_result.feed = {
            'title': 'Test Substack',
            'description': 'A test substack feed'
        }
        
        # Mock feed entries
        mock_entry = {
            'title': 'Test Substack Article',
            'link': 'https://example.substack.com/p/test-article',
            'author': 'Substack Author',
            'published_parsed': (2025, 6, 7, 12, 0, 0, 5, 158, 0),
            'content': [{'type': 'text/html', 'value': '<p>Test content</p>'}]
        }
        
        mock_feed_result.entries = [mock_entry]
        mock_feedparser.return_value = mock_feed_result
        
        # Mock file operations
        mock_file_handle = Mock()
        mock_open.return_value.__enter__.return_value = mock_file_handle
        
        # Mock successful link processing
        mock_process_func.return_value = True
        
        # Mock HTTP client and factory
        mock_http_client_instance = Mock()
        mock_http_client.return_value = mock_http_client_instance
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        
        # Run Substack scraper
        scraper = SubstackScraper()
        scraper.scrape()
        
        # Verify links were created in database
        new_links = db_session.query(Links).filter(
            Links.status == LinkStatus.new,
            Links.source == 'substack'
        ).all()
        assert len(new_links) >= 1
        
        # Run pipeline to process the links
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=0.1)
        
        try:
            # Run a single cycle to process the links
            cycle_stats = orchestrator.run_single_cycle()
            
            # Verify processing occurred
            assert cycle_stats['processing']['total'] > 0
            assert cycle_stats['processing']['processed'] > 0
            
        finally:
            orchestrator.cleanup()

    @patch('app.scraping.hackernews_scraper.requests.get')
    @patch('app.scraping.reddit.praw.Reddit')
    @patch('app.links.link_processor.process_link_from_db')
    @patch('app.http_client.robust_http_client.RobustHttpClient')
    @patch('app.processing_strategies.factory.UrlProcessorFactory')
    def test_multiple_scrapers_with_pipeline(self, mock_factory, mock_http_client, mock_process_func, 
                                           mock_reddit, mock_requests, db_session):
        """Test multiple scrapers running together with pipeline processing."""
        from app.scraping.hackernews_scraper import process_hackernews_articles
        from app.scraping.reddit import process_reddit_articles
        
        # Mock HackerNews API
        mock_hn_response = Mock()
        mock_hn_response.json.return_value = [1, 2]
        mock_hn_response.status_code = 200
        
        story_response = Mock()
        story_response.json.return_value = {
            'id': 1,
            'title': 'HN Test Story',
            'url': 'https://example.com/hn-story',
            'by': 'hn_user',
            'time': 1640995200,
            'score': 100
        }
        story_response.status_code = 200
        
        def mock_hn_get(url):
            if 'topstories' in url:
                return mock_hn_response
            elif 'item/1.json' in url:
                return story_response
            elif 'item/2.json' in url:
                return story_response
            return Mock(status_code=404)
        
        mock_requests.side_effect = mock_hn_get
        
        # Mock Reddit API
        mock_reddit_instance = Mock()
        mock_reddit.return_value = mock_reddit_instance
        mock_subreddit = Mock()
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        
        mock_submission = Mock()
        mock_submission.title = "Reddit Test Post"
        mock_submission.url = "https://example.com/reddit-post"
        mock_submission.author.name = "reddit_user"
        mock_submission.created_utc = 1640995200
        mock_submission.score = 50
        mock_submission.is_self = False
        
        mock_subreddit.top.return_value = [mock_submission]
        
        # Mock successful link processing
        mock_process_func.return_value = True
        
        # Mock HTTP client and factory
        mock_http_client_instance = Mock()
        mock_http_client.return_value = mock_http_client_instance
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance
        
        # Run both scrapers
        hn_stats = process_hackernews_articles()
        reddit_stats = process_reddit_articles("technology", limit=5, time_filter="day")
        
        # Verify both scrapers created links
        assert hn_stats['queued_links'] > 0
        assert reddit_stats['queued_links'] > 0
        
        # Count total new links
        total_new_links = db_session.query(Links).filter(Links.status == LinkStatus.new).count()
        assert total_new_links >= (hn_stats['queued_links'] + reddit_stats['queued_links'])
        
        # Run pipeline to process all links
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=2, polling_interval=0.1)
        
        try:
            # Run multiple cycles to process all links
            total_processed = 0
            max_cycles = 5
            
            for _ in range(max_cycles):
                cycle_stats = orchestrator.run_single_cycle()
                total_processed += cycle_stats['processing']['total']
                
                # Break if no more work
                if cycle_stats['processing']['total'] == 0:
                    break
            
            # Verify processing occurred
            assert total_processed > 0
            
            # Verify final statistics
            final_status = orchestrator.get_status()
            assert final_status['statistics']['total_processed'] > 0
            
        finally:
            orchestrator.cleanup()

    @patch('app.links.link_processor.process_link_from_db')
    def test_pipeline_with_processing_failures(self, mock_process_func, db_session):
        """Test pipeline handling when link processing fails."""
        # Create test links directly in database
        test_links = [
            Links(
                url='https://example.com/fail1',
                source='test',
                status=LinkStatus.new,
                scraped_date=datetime.utcnow()
            ),
            Links(
                url='https://example.com/fail2',
                source='test',
                status=LinkStatus.new,
                scraped_date=datetime.utcnow()
            )
        ]
        
        for link in test_links:
            db_session.add(link)
        db_session.commit()
        
        # Mock processing failures
        mock_process_func.return_value = False
        
        # Run pipeline
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=0.1)
        
        try:
            cycle_stats = orchestrator.run_single_cycle()
            
            # Verify failures were handled
            assert cycle_stats['processing']['failed'] > 0
            assert orchestrator.stats['links_failed'] > 0
            
        finally:
            orchestrator.cleanup()

    def test_pipeline_status_monitoring(self, db_session):
        """Test pipeline status monitoring and reporting."""
        # Create test links
        test_links = [
            Links(
                url='https://example.com/monitor1',
                source='test',
                status=LinkStatus.new,
                scraped_date=datetime.utcnow()
            ),
            Links(
                url='https://example.com/monitor2',
                source='test',
                status=LinkStatus.processing,
                scraped_date=datetime.utcnow(),
                checked_out_by='test_worker',
                checked_out_at=datetime.utcnow()
            )
        ]
        
        for link in test_links:
            db_session.add(link)
        db_session.commit()
        
        # Create orchestrator
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=2, polling_interval=1)
        
        try:
            # Get status
            status = orchestrator.get_status()
            
            # Verify status structure
            assert 'running' in status
            assert 'worker_config' in status
            assert 'statistics' in status
            assert 'checkout_status' in status
            
            # Verify checkout status includes link counts
            checkout_status = status['checkout_status']
            assert 'status_counts' in checkout_status
            assert 'active_checkouts' in checkout_status
            
        finally:
            orchestrator.cleanup()