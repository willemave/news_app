"""
Unit tests for LinkCheckoutManager.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.links.checkout_manager import LinkCheckoutManager
from app.models import Links, LinkStatus


class TestLinkCheckoutManager:
    """Test LinkCheckoutManager functionality."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def checkout_manager(self, mock_db_session):
        """Create checkout manager with mock session."""
        return LinkCheckoutManager(mock_db_session, timeout_minutes=30)

    def test_checkout_link_success(self, checkout_manager, mock_db_session):
        """Test successful link checkout."""
        # Mock link object
        mock_link = Mock()
        mock_link.id = 123
        mock_link.status = LinkStatus.new
        mock_link.checked_out_by = None
        mock_link.checked_out_at = None

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.with_for_update.return_value.first.return_value = mock_link
        mock_db_session.query.return_value = mock_query

        # Test checkout
        result = checkout_manager.checkout_link(123, "worker_1", LinkStatus.new)

        # Assertions
        assert result == mock_link
        assert mock_link.checked_out_by == "worker_1"
        assert isinstance(mock_link.checked_out_at, datetime)
        mock_db_session.commit.assert_called_once()

    def test_checkout_link_not_available(self, checkout_manager, mock_db_session):
        """Test checkout when link is not available."""
        # Mock query returns None (link not available)
        mock_query = Mock()
        mock_query.filter.return_value.with_for_update.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Test checkout
        result = checkout_manager.checkout_link(123, "worker_1", LinkStatus.new)

        # Assertions
        assert result is None
        mock_db_session.commit.assert_not_called()

    def test_checkout_link_database_error(self, checkout_manager, mock_db_session):
        """Test checkout with database error."""
        # Mock database error
        mock_db_session.query.side_effect = Exception("Database error")

        # Test checkout
        result = checkout_manager.checkout_link(123, "worker_1", LinkStatus.new)

        # Assertions
        assert result is None
        mock_db_session.rollback.assert_called_once()

    def test_checkin_link_success(self, checkout_manager, mock_db_session):
        """Test successful link checkin."""
        # Mock link object
        mock_link = Mock()
        mock_link.id = 123
        mock_link.checked_out_by = "worker_1"
        mock_link.checked_out_at = datetime.utcnow()

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.with_for_update.return_value.first.return_value = mock_link
        mock_db_session.query.return_value = mock_query

        # Test checkin
        result = checkout_manager.checkin_link(123, "worker_1", LinkStatus.processed)

        # Assertions
        assert result is True
        assert mock_link.status == LinkStatus.processed
        assert mock_link.checked_out_by is None
        assert mock_link.checked_out_at is None
        assert isinstance(mock_link.processed_date, datetime)
        mock_db_session.commit.assert_called_once()

    def test_checkin_link_not_checked_out_by_worker(self, checkout_manager, mock_db_session):
        """Test checkin when link is not checked out by the worker."""
        # Mock query returns None (link not checked out by this worker)
        mock_query = Mock()
        mock_query.filter.return_value.with_for_update.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Test checkin
        result = checkout_manager.checkin_link(123, "worker_1", LinkStatus.processed)

        # Assertions
        assert result is False
        mock_db_session.commit.assert_not_called()

    def test_checkin_link_with_error_message(self, checkout_manager, mock_db_session):
        """Test checkin with error message."""
        # Mock link object
        mock_link = Mock()
        mock_link.id = 123
        mock_link.checked_out_by = "worker_1"

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.with_for_update.return_value.first.return_value = mock_link
        mock_db_session.query.return_value = mock_query

        # Test checkin with error
        result = checkout_manager.checkin_link(123, "worker_1", LinkStatus.failed, "Processing error")

        # Assertions
        assert result is True
        assert mock_link.status == LinkStatus.failed
        assert mock_link.error_message == "Processing error"
        mock_db_session.commit.assert_called_once()

    def test_release_stale_checkouts(self, checkout_manager, mock_db_session):
        """Test releasing stale checkouts."""
        # Mock stale links
        stale_link1 = Mock()
        stale_link1.id = 1
        stale_link1.checked_out_by = "worker_1"
        stale_link1.checked_out_at = datetime.utcnow() - timedelta(hours=1)

        stale_link2 = Mock()
        stale_link2.id = 2
        stale_link2.checked_out_by = "worker_2"
        stale_link2.checked_out_at = datetime.utcnow() - timedelta(hours=2)

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.with_for_update.return_value.all.return_value = [stale_link1, stale_link2]
        mock_db_session.query.return_value = mock_query

        # Test release stale checkouts
        result = checkout_manager.release_stale_checkouts()

        # Assertions
        assert result == 2
        assert stale_link1.checked_out_by is None
        assert stale_link1.checked_out_at is None
        assert stale_link2.checked_out_by is None
        assert stale_link2.checked_out_at is None
        mock_db_session.commit.assert_called_once()

    def test_is_checked_out_true(self, checkout_manager, mock_db_session):
        """Test is_checked_out returns True for checked out link."""
        # Mock link object
        mock_link = Mock()
        mock_link.id = 123

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_link
        mock_db_session.query.return_value = mock_query

        # Test is_checked_out
        result = checkout_manager.is_checked_out(123)

        # Assertions
        assert result is True

    def test_is_checked_out_false(self, checkout_manager, mock_db_session):
        """Test is_checked_out returns False for non-checked out link."""
        # Mock query returns None
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Test is_checked_out
        result = checkout_manager.is_checked_out(123)

        # Assertions
        assert result is False

    def test_find_available_links(self, checkout_manager, mock_db_session):
        """Test finding available links."""
        # Mock available links
        link1 = Mock()
        link1.id = 1
        link1.status = LinkStatus.new

        link2 = Mock()
        link2.id = 2
        link2.status = LinkStatus.new

        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.limit.return_value.all.return_value = [link1, link2]
        mock_db_session.query.return_value = mock_query

        # Test find available links
        result = checkout_manager.find_available_links(LinkStatus.new, limit=5)

        # Assertions
        assert len(result) == 2
        assert result[0] == link1
        assert result[1] == link2

    def test_get_checkout_status(self, checkout_manager, mock_db_session):
        """Test getting checkout status."""
        # Mock query results
        mock_db_session.query.return_value.filter.return_value.count.return_value = 5
        
        # Test get checkout status
        result = checkout_manager.get_checkout_status()

        # Assertions
        assert 'status_counts' in result
        assert 'active_checkouts' in result
        assert 'stale_checkouts' in result
        assert 'timeout_minutes' in result
        assert result['timeout_minutes'] == 30