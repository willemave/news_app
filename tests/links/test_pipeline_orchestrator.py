"""
Unit tests for LinkPipelineOrchestrator.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import Future

from app.links.pipeline_orchestrator import LinkPipelineOrchestrator
from app.models import Links, LinkStatus


class TestLinkPipelineOrchestrator:
    """Test LinkPipelineOrchestrator functionality."""

    @pytest.fixture
    def orchestrator(self):
        """Create a LinkPipelineOrchestrator instance."""
        return LinkPipelineOrchestrator(processor_concurrency=2, polling_interval=1)

    @pytest.fixture
    def mock_links(self):
        """Create mock link objects."""
        link1 = Mock(spec=Links)
        link1.id = 1
        link1.url = "https://example.com/1"
        link1.status = LinkStatus.new

        link2 = Mock(spec=Links)
        link2.id = 2
        link2.url = "https://example.com/2"
        link2.status = LinkStatus.new

        return [link1, link2]

    @patch('app.links.pipeline_orchestrator.SessionLocal')
    @patch('app.links.pipeline_orchestrator.LinkCheckoutManager')
    def test_find_available_links(self, mock_checkout_manager_class, mock_session_local, orchestrator, mock_links):
        """Test finding available links."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        # Mock checkout manager
        mock_checkout_manager = Mock()
        mock_checkout_manager_class.return_value = mock_checkout_manager
        mock_checkout_manager.find_available_links.return_value = mock_links

        # Test find_available_links
        result = orchestrator.find_available_links(LinkStatus.new, limit=5)

        # Assertions
        assert result == mock_links
        mock_checkout_manager.find_available_links.assert_called_once_with(LinkStatus.new, 5)
        mock_db.close.assert_called_once()

    @patch('app.links.pipeline_orchestrator.SessionLocal')
    @patch('app.links.pipeline_orchestrator.LinkCheckoutManager')
    def test_release_stale_checkouts(self, mock_checkout_manager_class, mock_session_local, orchestrator):
        """Test releasing stale checkouts."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        # Mock checkout manager
        mock_checkout_manager = Mock()
        mock_checkout_manager_class.return_value = mock_checkout_manager
        mock_checkout_manager.release_stale_checkouts.return_value = 3

        # Test release_stale_checkouts
        result = orchestrator.release_stale_checkouts()

        # Assertions
        assert result == 3
        mock_checkout_manager.release_stale_checkouts.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('app.links.pipeline_orchestrator.ThreadPoolExecutor')
    def test_dispatch_processor_workers_no_links(self, mock_executor_class, orchestrator):
        """Test dispatch when no links are available."""
        # Mock find_available_links to return empty list
        orchestrator.find_available_links = Mock(return_value=[])

        # Test dispatch
        result = orchestrator.dispatch_processor_workers()

        # Assertions
        assert result == {"processed": 0, "failed": 0, "skipped": 0, "total": 0}
        mock_executor_class.assert_not_called()

    @patch('app.links.pipeline_orchestrator.SessionLocal')
    @patch('app.links.pipeline_orchestrator.ThreadPoolExecutor')
    def test_dispatch_processor_workers_success(self, mock_executor_class, mock_session_local, orchestrator, mock_links):
        """Test successful dispatch of processor workers."""
        # Mock find_available_links
        orchestrator.find_available_links = Mock(return_value=mock_links)

        # Mock database session for status checking
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Mock updated links with processed status
        updated_link1 = Mock()
        updated_link1.status = LinkStatus.processed
        updated_link2 = Mock()
        updated_link2.status = LinkStatus.processed
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [updated_link1, updated_link2]

        # Mock ThreadPoolExecutor
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Mock futures and results
        future1 = Mock(spec=Future)
        future1.result.return_value = True
        future2 = Mock(spec=Future)
        future2.result.return_value = True

        mock_executor.submit.side_effect = [future1, future2]
        
        # Mock as_completed to return futures
        with patch('app.links.pipeline_orchestrator.as_completed', return_value=[future1, future2]):
            # Test dispatch
            result = orchestrator.dispatch_processor_workers()

        # Assertions
        assert result["processed"] == 2
        assert result["failed"] == 0
        assert result["skipped"] == 0
        assert result["total"] == 2

        # Verify executor was used correctly
        assert mock_executor.submit.call_count == 2

    @patch('app.links.pipeline_orchestrator.SessionLocal')
    @patch('app.links.pipeline_orchestrator.ThreadPoolExecutor')
    def test_dispatch_processor_workers_with_skipped(self, mock_executor_class, mock_session_local, orchestrator, mock_links):
        """Test dispatch with some links being skipped."""
        # Mock find_available_links
        orchestrator.find_available_links = Mock(return_value=mock_links)

        # Mock database session for status checking
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        # Mock updated links - one processed, one skipped
        updated_link1 = Mock()
        updated_link1.status = LinkStatus.processed
        updated_link2 = Mock()
        updated_link2.status = LinkStatus.skipped
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [updated_link1, updated_link2]

        # Mock ThreadPoolExecutor
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Mock futures and results
        future1 = Mock(spec=Future)
        future1.result.return_value = True
        future2 = Mock(spec=Future)
        future2.result.return_value = True

        mock_executor.submit.side_effect = [future1, future2]
        
        # Mock as_completed to return futures
        with patch('app.links.pipeline_orchestrator.as_completed', return_value=[future1, future2]):
            # Test dispatch
            result = orchestrator.dispatch_processor_workers()

        # Assertions
        assert result["processed"] == 1
        assert result["failed"] == 0
        assert result["skipped"] == 1
        assert result["total"] == 2

    @patch('app.links.pipeline_orchestrator.SessionLocal')
    @patch('app.links.pipeline_orchestrator.ThreadPoolExecutor')
    def test_dispatch_processor_workers_with_failures(self, mock_executor_class, mock_session_local, orchestrator, mock_links):
        """Test dispatch with some processing failures."""
        # Mock find_available_links
        orchestrator.find_available_links = Mock(return_value=mock_links)

        # Mock ThreadPoolExecutor
        mock_executor = Mock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor

        # Mock futures and results - one success, one failure
        future1 = Mock(spec=Future)
        future1.result.return_value = True
        future2 = Mock(spec=Future)
        future2.result.return_value = False

        mock_executor.submit.side_effect = [future1, future2]
        
        # Mock database session for status checking (only for successful one)
        mock_db = Mock()
        mock_session_local.return_value = mock_db
        
        updated_link1 = Mock()
        updated_link1.status = LinkStatus.processed
        mock_db.query.return_value.filter.return_value.first.return_value = updated_link1
        
        # Mock as_completed to return futures
        with patch('app.links.pipeline_orchestrator.as_completed', return_value=[future1, future2]):
            # Test dispatch
            result = orchestrator.dispatch_processor_workers()

        # Assertions
        assert result["processed"] == 1
        assert result["failed"] == 1
        assert result["skipped"] == 0
        assert result["total"] == 2

    def test_run_single_cycle(self, orchestrator):
        """Test running a single processing cycle."""
        # Mock methods
        orchestrator.release_stale_checkouts = Mock(return_value=2)
        orchestrator.dispatch_processor_workers = Mock(return_value={
            "processed": 3, "failed": 1, "skipped": 0, "total": 4
        })

        # Test run_single_cycle
        result = orchestrator.run_single_cycle()

        # Assertions
        assert result['stale_checkouts_released'] == 2
        assert result['processing']['processed'] == 3
        assert result['processing']['failed'] == 1
        assert result['processing']['skipped'] == 0
        assert result['processing']['total'] == 4

        # Verify statistics were updated
        assert orchestrator.stats['cycles_completed'] == 1
        assert orchestrator.stats['links_processed'] == 3
        assert orchestrator.stats['links_failed'] == 1
        assert orchestrator.stats['links_skipped'] == 0
        assert orchestrator.stats['total_processed'] == 4

    def test_run_single_cycle_with_exception(self, orchestrator):
        """Test run_single_cycle with exception handling."""
        # Mock methods to raise exception
        orchestrator.release_stale_checkouts = Mock(side_effect=Exception("Test error"))

        # Test run_single_cycle
        result = orchestrator.run_single_cycle()

        # Assertions
        assert orchestrator.stats['errors'] == 1
        assert 'stale_checkouts_released' in result
        assert 'processing' in result

    @patch('app.links.pipeline_orchestrator.SessionLocal')
    @patch('app.links.pipeline_orchestrator.LinkCheckoutManager')
    def test_get_status(self, mock_checkout_manager_class, mock_session_local, orchestrator):
        """Test getting orchestrator status."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        # Mock checkout manager
        mock_checkout_manager = Mock()
        mock_checkout_manager_class.return_value = mock_checkout_manager
        mock_checkout_manager.get_checkout_status.return_value = {
            'status_counts': {'new': 5, 'processing': 2},
            'active_checkouts': 2,
            'stale_checkouts': 0
        }

        # Set some stats
        orchestrator.stats['cycles_completed'] = 5
        orchestrator.running = True

        # Test get_status
        result = orchestrator.get_status()

        # Assertions
        assert result['running'] is True
        assert result['worker_config']['processors'] == 2
        assert result['polling_interval'] == 1
        assert result['statistics']['cycles_completed'] == 5
        assert 'checkout_status' in result
        mock_db.close.assert_called_once()

    def test_shutdown(self, orchestrator):
        """Test orchestrator shutdown."""
        orchestrator.running = True
        
        # Test shutdown
        orchestrator.shutdown()
        
        # Assertions
        assert orchestrator.running is False
        assert orchestrator.shutdown_event.is_set()

    def test_cleanup(self, orchestrator):
        """Test orchestrator cleanup."""
        # Mock processors
        mock_processor1 = Mock()
        mock_processor2 = Mock()
        orchestrator.processors = [mock_processor1, mock_processor2]
        
        # Test cleanup
        orchestrator.cleanup()
        
        # Verify all processors were cleaned up
        mock_processor1.cleanup.assert_called_once()
        mock_processor2.cleanup.assert_called_once()

    def test_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = LinkPipelineOrchestrator(processor_concurrency=3, polling_interval=5)
        
        # Assertions
        assert orchestrator.processor_concurrency == 3
        assert orchestrator.polling_interval == 5
        assert len(orchestrator.processors) == 3
        assert orchestrator.running is False
        assert not orchestrator.shutdown_event.is_set()
        
        # Check processor IDs
        assert orchestrator.processors[0].instance_id == "1"
        assert orchestrator.processors[1].instance_id == "2"
        assert orchestrator.processors[2].instance_id == "3"