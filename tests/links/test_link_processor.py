"""
Unit tests for LinkProcessorWorker.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from app.links.link_processor import LinkProcessorWorker
from app.models import Links, LinkStatus


class TestLinkProcessorWorker:
    """Test LinkProcessorWorker functionality."""

    @pytest.fixture
    def worker(self):
        """Create a LinkProcessorWorker instance."""
        return LinkProcessorWorker(instance_id="test")

    @pytest.fixture
    def mock_link(self):
        """Create a mock link object."""
        link = Mock(spec=Links)
        link.id = 123
        link.url = "https://example.com/test"
        link.status = LinkStatus.new
        return link

    @patch('app.links.link_processor.SessionLocal')
    @patch('app.links.link_processor.LinkCheckoutManager')
    @patch('app.links.link_processor.process_link_from_db')
    def test_process_link_success(self, mock_process_func, mock_checkout_manager_class, mock_session_local, worker, mock_link):
        """Test successful link processing."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        # Mock checkout manager
        mock_checkout_manager = Mock()
        mock_checkout_manager_class.return_value = mock_checkout_manager
        
        # Mock successful checkout and processing
        mock_checkout_manager.checkout_link.side_effect = [mock_link, mock_link]  # Two checkouts
        mock_checkout_manager.checkin_link.return_value = True
        mock_process_func.return_value = True

        # Test process_link
        result = worker.process_link(123)

        # Assertions
        assert result is True
        
        # Verify checkout calls
        assert mock_checkout_manager.checkout_link.call_count == 2
        mock_checkout_manager.checkout_link.assert_any_call(123, "link_processor_test", LinkStatus.new)
        mock_checkout_manager.checkout_link.assert_any_call(123, "link_processor_test", LinkStatus.processing)
        
        # Verify checkin calls
        assert mock_checkout_manager.checkin_link.call_count == 2
        mock_checkout_manager.checkin_link.assert_any_call(123, "link_processor_test", LinkStatus.processing)
        mock_checkout_manager.checkin_link.assert_any_call(123, "link_processor_test")
        
        # Verify processing was called
        mock_process_func.assert_called_once_with(mock_link, worker.http_client, worker.factory)

    @patch('app.links.link_processor.SessionLocal')
    @patch('app.links.link_processor.LinkCheckoutManager')
    def test_process_link_checkout_failed(self, mock_checkout_manager_class, mock_session_local, worker):
        """Test link processing when initial checkout fails."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        # Mock checkout manager
        mock_checkout_manager = Mock()
        mock_checkout_manager_class.return_value = mock_checkout_manager
        
        # Mock failed checkout
        mock_checkout_manager.checkout_link.return_value = None

        # Test process_link
        result = worker.process_link(123)

        # Assertions
        assert result is False
        mock_checkout_manager.checkout_link.assert_called_once_with(123, "link_processor_test", LinkStatus.new)

    @patch('app.links.link_processor.SessionLocal')
    @patch('app.links.link_processor.LinkCheckoutManager')
    def test_process_link_status_update_failed(self, mock_checkout_manager_class, mock_session_local, worker, mock_link):
        """Test link processing when status update to processing fails."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        # Mock checkout manager
        mock_checkout_manager = Mock()
        mock_checkout_manager_class.return_value = mock_checkout_manager
        
        # Mock successful initial checkout but failed status update
        mock_checkout_manager.checkout_link.return_value = mock_link
        mock_checkout_manager.checkin_link.return_value = False

        # Test process_link
        result = worker.process_link(123)

        # Assertions
        assert result is False
        mock_checkout_manager.checkout_link.assert_called_once_with(123, "link_processor_test", LinkStatus.new)
        mock_checkout_manager.checkin_link.assert_called_once_with(123, "link_processor_test", LinkStatus.processing)

    @patch('app.links.link_processor.SessionLocal')
    @patch('app.links.link_processor.LinkCheckoutManager')
    def test_process_link_re_checkout_failed(self, mock_checkout_manager_class, mock_session_local, worker, mock_link):
        """Test link processing when re-checkout in processing state fails."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        # Mock checkout manager
        mock_checkout_manager = Mock()
        mock_checkout_manager_class.return_value = mock_checkout_manager
        
        # Mock successful initial checkout and status update, but failed re-checkout
        mock_checkout_manager.checkout_link.side_effect = [mock_link, None]
        mock_checkout_manager.checkin_link.return_value = True

        # Test process_link
        result = worker.process_link(123)

        # Assertions
        assert result is False
        assert mock_checkout_manager.checkout_link.call_count == 2

    @patch('app.links.link_processor.SessionLocal')
    @patch('app.links.link_processor.LinkCheckoutManager')
    @patch('app.links.link_processor.process_link_from_db')
    def test_process_link_processing_failed(self, mock_process_func, mock_checkout_manager_class, mock_session_local, worker, mock_link):
        """Test link processing when the actual processing fails."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        # Mock checkout manager
        mock_checkout_manager = Mock()
        mock_checkout_manager_class.return_value = mock_checkout_manager
        
        # Mock successful checkouts but failed processing
        mock_checkout_manager.checkout_link.side_effect = [mock_link, mock_link]
        mock_checkout_manager.checkin_link.return_value = True
        mock_process_func.return_value = False

        # Test process_link
        result = worker.process_link(123)

        # Assertions
        assert result is False
        
        # Verify final checkin with failed status
        final_checkin_call = mock_checkout_manager.checkin_link.call_args_list[-1]
        assert final_checkin_call[0] == (123, "link_processor_test", LinkStatus.failed, "Processing failed")

    @patch('app.links.link_processor.SessionLocal')
    @patch('app.links.link_processor.LinkCheckoutManager')
    @patch('app.links.link_processor.process_link_from_db')
    def test_process_link_processing_exception(self, mock_process_func, mock_checkout_manager_class, mock_session_local, worker, mock_link):
        """Test link processing when the actual processing raises an exception."""
        # Mock database session
        mock_db = Mock()
        mock_session_local.return_value = mock_db

        # Mock checkout manager
        mock_checkout_manager = Mock()
        mock_checkout_manager_class.return_value = mock_checkout_manager
        
        # Mock successful checkouts but processing exception
        mock_checkout_manager.checkout_link.side_effect = [mock_link, mock_link]
        mock_checkout_manager.checkin_link.return_value = True
        mock_process_func.side_effect = Exception("Processing error")

        # Test process_link
        result = worker.process_link(123)

        # Assertions
        assert result is False
        
        # Verify final checkin with failed status and error message
        final_checkin_call = mock_checkout_manager.checkin_link.call_args_list[-1]
        assert final_checkin_call[0][0] == 123  # link_id
        assert final_checkin_call[0][1] == "link_processor_test"  # worker_id
        assert final_checkin_call[0][2] == LinkStatus.failed  # status
        assert "Processing error" in final_checkin_call[0][3]  # error message

    def test_worker_id_generation(self):
        """Test that worker ID is generated correctly."""
        worker1 = LinkProcessorWorker(instance_id="1")
        worker2 = LinkProcessorWorker(instance_id="2")
        
        assert worker1.worker_id == "link_processor_1"
        assert worker2.worker_id == "link_processor_2"

    def test_cleanup(self, worker):
        """Test worker cleanup."""
        # Mock http_client
        worker.http_client = Mock()
        worker.http_client.close = Mock()
        
        # Test cleanup
        worker.cleanup()
        
        # Verify http_client.close was called
        worker.http_client.close.assert_called_once()

    def test_cleanup_no_http_client(self, worker):
        """Test worker cleanup when http_client is None."""
        worker.http_client = None
        
        # Test cleanup (should not raise exception)
        worker.cleanup()