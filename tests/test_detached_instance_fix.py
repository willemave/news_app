#!/usr/bin/env python3
"""
Test to verify the DetachedInstanceError fix in the checkout system.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.pipeline.checkout import CheckoutManager
from app.domain.content import ContentType, ContentStatus
from app.models.schema import Content
from datetime import datetime


def test_checkout_content_returns_only_ids():
    """Test that checkout_content only returns content IDs, not detached objects."""
    checkout_manager = CheckoutManager()
    
    # Mock the database session and content objects
    mock_content1 = MagicMock(spec=Content)
    mock_content1.id = 1
    mock_content2 = MagicMock(spec=Content)
    mock_content2.id = 2
    
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.with_for_update.return_value = mock_query
    mock_query.all.return_value = [mock_content1, mock_content2]
    
    mock_db.query.return_value = mock_query
    
    with patch('app.pipeline.checkout.get_db') as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db
        
        # Test the checkout context manager
        with checkout_manager.checkout_content("test_worker", batch_size=2) as content_ids:
            # Should return only IDs, not Content objects
            assert content_ids == [1, 2]
            assert isinstance(content_ids, list)
            assert all(isinstance(cid, int) for cid in content_ids)
            
            # Verify we can access the IDs without any session issues
            for content_id in content_ids:
                assert content_id in [1, 2]


def test_checkout_batch_returns_only_ids():
    """Test that _checkout_batch returns only content IDs."""
    checkout_manager = CheckoutManager()
    
    # Mock the database session and content objects
    mock_content1 = MagicMock(spec=Content)
    mock_content1.id = 1
    mock_content2 = MagicMock(spec=Content)
    mock_content2.id = 2
    
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.with_for_update.return_value = mock_query
    mock_query.all.return_value = [mock_content1, mock_content2]
    
    mock_db.query.return_value = mock_query
    
    with patch('app.pipeline.checkout.get_db') as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db
        
        # Test the _checkout_batch method
        result = checkout_manager._checkout_batch("test_worker", batch_size=2)
        
        # Should return only IDs
        assert result == [1, 2]
        assert isinstance(result, list)
        assert all(isinstance(cid, int) for cid in result)


def test_checkout_exception_handling():
    """Test that exception handling works with content IDs instead of objects."""
    checkout_manager = CheckoutManager()
    
    # Mock the database session and content objects
    mock_content = MagicMock(spec=Content)
    mock_content.id = 1
    
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.with_for_update.return_value = mock_query
    mock_query.all.return_value = [mock_content]
    
    mock_db.query.return_value = mock_query
    
    with patch('app.pipeline.checkout.get_db') as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db
        
        # Test exception handling in checkout context manager
        with pytest.raises(ValueError):
            with checkout_manager.checkout_content("test_worker") as content_ids:
                # Should be able to access content_ids without DetachedInstanceError
                assert content_ids == [1]
                # Raise an exception to test the exception handling path
                raise ValueError("Test exception")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])