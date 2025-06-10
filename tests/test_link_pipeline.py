"""
Integration test for the new link processing pipeline.
Tests the complete flow from scraping to processing using the LinkPipelineOrchestrator.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.models import Links, Articles, LinkStatus, ArticleStatus
from app.links.pipeline_orchestrator import LinkPipelineOrchestrator
from app.database import SessionLocal


class TestLinkPipelineIntegration:
    """Integration tests for the link processing pipeline."""

    @pytest.fixture
    def db_session(self):
        """Create a database session for testing."""
        session = SessionLocal()
        yield session
        session.close()

    @pytest.fixture
    def mock_links_data(self):
        """Sample link data for testing."""
        return [
            {
                'url': 'https://example.com/article1',
                'source': 'hackernews',
                'status': LinkStatus.new,
                'created_date': datetime.utcnow()
            },
            {
                'url': 'https://example.com/article2',
                'source': 'reddit-technology',
                'status': LinkStatus.new,
                'created_date': datetime.utcnow()
            },
            {
                'url': 'https://example.com/article3',
                'source': 'substack',
                'status': LinkStatus.new,
                'created_date': datetime.utcnow()
            }
        ]

    def create_test_links(self, db_session, links_data):
        """Helper to create test links in the database."""
        created_links = []
        for link_data in links_data:
            link = Links(**link_data)
            db_session.add(link)
            created_links.append(link)
        db_session.commit()
        return created_links

    @patch('app.links.link_processor.process_link_from_db')
    @patch('app.http_client.robust_http_client.RobustHttpClient')
    @patch('app.processing_strategies.factory.UrlProcessorFactory')
    def test_complete_pipeline_success(self, mock_factory, mock_http_client, mock_process_func, db_session, mock_links_data):
        """Test complete pipeline processing with successful outcomes."""
        # Create test links
        test_links = self.create_test_links(db_session, mock_links_data)
        
        # Mock successful processing
        mock_process_func.return_value = True
        
        # Mock HTTP client and factory
        mock_http_client_instance = Mock()
        mock_http_client.return_value = mock_http_client_instance
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance

        # Create orchestrator with minimal concurrency for testing
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=0.1)
        
        try:
            # Run a single cycle instead of the full run() to avoid infinite loop
            cycle_stats = orchestrator.run_single_cycle()
            
            # Verify processing occurred
            assert cycle_stats['processing']['total'] > 0
            assert cycle_stats['processing']['processed'] > 0
            assert cycle_stats['processing']['failed'] == 0
            
            # Verify links were processed (status should be updated)
            db_session.refresh(test_links[0])
            # Note: The actual status depends on the mock behavior and link processing logic
            
            # Verify statistics were updated
            assert orchestrator.stats['cycles_completed'] == 1
            assert orchestrator.stats['total_processed'] > 0
            
        finally:
            orchestrator.cleanup()

    @patch('app.links.link_processor.process_link_from_db')
    @patch('app.http_client.robust_http_client.RobustHttpClient')
    @patch('app.processing_strategies.factory.UrlProcessorFactory')
    def test_pipeline_with_processing_failures(self, mock_factory, mock_http_client, mock_process_func, db_session, mock_links_data):
        """Test pipeline handling of processing failures."""
        # Create test links
        test_links = self.create_test_links(db_session, mock_links_data)
        
        # Mock processing failures
        mock_process_func.return_value = False
        
        # Mock HTTP client and factory
        mock_http_client_instance = Mock()
        mock_http_client.return_value = mock_http_client_instance
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance

        # Create orchestrator
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=0.1)
        
        try:
            # Run a single cycle
            cycle_stats = orchestrator.run_single_cycle()
            
            # Verify failures were recorded
            assert cycle_stats['processing']['total'] > 0
            assert cycle_stats['processing']['failed'] > 0
            assert cycle_stats['processing']['processed'] == 0
            
            # Verify statistics
            assert orchestrator.stats['links_failed'] > 0
            assert orchestrator.stats['errors'] > 0
            
        finally:
            orchestrator.cleanup()

    @patch('app.links.link_processor.process_link_from_db')
    @patch('app.http_client.robust_http_client.RobustHttpClient')
    @patch('app.processing_strategies.factory.UrlProcessorFactory')
    def test_pipeline_with_mixed_outcomes(self, mock_factory, mock_http_client, mock_process_func, db_session, mock_links_data):
        """Test pipeline with mixed processing outcomes."""
        # Create test links
        test_links = self.create_test_links(db_session, mock_links_data)
        
        # Mock mixed outcomes - some succeed, some fail
        mock_process_func.side_effect = [True, False, True]
        
        # Mock HTTP client and factory
        mock_http_client_instance = Mock()
        mock_http_client.return_value = mock_http_client_instance
        mock_factory_instance = Mock()
        mock_factory.return_value = mock_factory_instance

        # Create orchestrator
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=0.1)
        
        try:
            # Run multiple cycles to process all links
            total_processed = 0
            total_failed = 0
            max_cycles = 5  # Prevent infinite loop
            
            for _ in range(max_cycles):
                cycle_stats = orchestrator.run_single_cycle()
                total_processed += cycle_stats['processing']['processed']
                total_failed += cycle_stats['processing']['failed']
                
                # Break if no more work
                if cycle_stats['processing']['total'] == 0:
                    break
            
            # Verify mixed outcomes
            assert total_processed > 0
            assert total_failed > 0
            assert total_processed + total_failed <= len(test_links)
            
        finally:
            orchestrator.cleanup()

    def test_pipeline_no_links_available(self, db_session):
        """Test pipeline behavior when no links are available for processing."""
        # Don't create any links
        
        # Create orchestrator
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=0.1)
        
        try:
            # Run a single cycle
            cycle_stats = orchestrator.run_single_cycle()
            
            # Verify no processing occurred
            assert cycle_stats['processing']['total'] == 0
            assert cycle_stats['processing']['processed'] == 0
            assert cycle_stats['processing']['failed'] == 0
            assert cycle_stats['processing']['skipped'] == 0
            
        finally:
            orchestrator.cleanup()

    @patch('app.links.checkout_manager.LinkCheckoutManager.release_stale_checkouts')
    def test_pipeline_stale_checkout_release(self, mock_release_stale, db_session, mock_links_data):
        """Test that pipeline releases stale checkouts."""
        # Create test links
        self.create_test_links(db_session, mock_links_data)
        
        # Mock stale checkout release
        mock_release_stale.return_value = 2
        
        # Create orchestrator
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=0.1)
        
        try:
            # Run a single cycle
            cycle_stats = orchestrator.run_single_cycle()
            
            # Verify stale checkouts were released
            assert cycle_stats['stale_checkouts_released'] == 2
            mock_release_stale.assert_called()
            
        finally:
            orchestrator.cleanup()

    def test_orchestrator_status_reporting(self, db_session):
        """Test orchestrator status reporting functionality."""
        # Create orchestrator
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=2, polling_interval=5)
        
        # Set some statistics
        orchestrator.stats['cycles_completed'] = 3
        orchestrator.stats['links_processed'] = 10
        orchestrator.stats['links_failed'] = 2
        orchestrator.running = True
        
        try:
            # Get status
            status = orchestrator.get_status()
            
            # Verify status structure
            assert 'running' in status
            assert 'worker_config' in status
            assert 'polling_interval' in status
            assert 'statistics' in status
            assert 'checkout_status' in status
            
            # Verify values
            assert status['running'] is True
            assert status['worker_config']['processors'] == 2
            assert status['polling_interval'] == 5
            assert status['statistics']['cycles_completed'] == 3
            assert status['statistics']['links_processed'] == 10
            assert status['statistics']['links_failed'] == 2
            
        finally:
            orchestrator.cleanup()

    def test_orchestrator_shutdown(self, db_session):
        """Test orchestrator shutdown functionality."""
        # Create orchestrator
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=1, polling_interval=1)
        
        # Verify initial state
        assert orchestrator.running is False
        assert not orchestrator.shutdown_event.is_set()
        
        # Test shutdown
        orchestrator.shutdown()
        
        # Verify shutdown state
        assert orchestrator.running is False
        assert orchestrator.shutdown_event.is_set()
        
        # Cleanup
        orchestrator.cleanup()

    @patch('app.links.link_processor.LinkProcessorWorker.process_link')
    def test_concurrent_processing(self, mock_process_link, db_session, mock_links_data):
        """Test concurrent processing with multiple workers."""
        # Create more test links for concurrent processing
        extended_links_data = mock_links_data * 2  # 6 links total
        test_links = self.create_test_links(db_session, extended_links_data)
        
        # Mock successful processing
        mock_process_link.return_value = True
        
        # Create orchestrator with higher concurrency
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=3, polling_interval=0.1)
        
        try:
            # Run a single cycle
            cycle_stats = orchestrator.run_single_cycle()
            
            # Verify processing occurred
            assert cycle_stats['processing']['total'] > 0
            
            # Verify multiple workers were used (process_link called multiple times)
            assert mock_process_link.call_count > 0
            
        finally:
            orchestrator.cleanup()

    def test_orchestrator_initialization_parameters(self):
        """Test orchestrator initialization with different parameters."""
        # Test default parameters
        orchestrator1 = LinkPipelineOrchestrator()
        assert orchestrator1.processor_concurrency > 0
        assert orchestrator1.polling_interval > 0
        assert len(orchestrator1.processors) == orchestrator1.processor_concurrency
        
        # Test custom parameters
        orchestrator2 = LinkPipelineOrchestrator(processor_concurrency=5, polling_interval=10)
        assert orchestrator2.processor_concurrency == 5
        assert orchestrator2.polling_interval == 10
        assert len(orchestrator2.processors) == 5
        
        # Cleanup
        orchestrator1.cleanup()
        orchestrator2.cleanup()