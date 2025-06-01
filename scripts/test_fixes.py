#!/usr/bin/env python3
"""
Test script to verify the implemented fixes work correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.processor import url_preprocessor
from app.schemas import ArticleSummary
from app.models import LinkStatus

def test_url_preprocessing():
    """Test URL preprocessing for arXiv and PubMed."""
    print("Testing URL preprocessing...")
    
    # Test arXiv URL conversion
    arxiv_url = "https://arxiv.org/abs/2504.16980"
    processed_arxiv = url_preprocessor(arxiv_url)
    expected_arxiv = "https://arxiv.org/pdf/2504.16980"
    
    print(f"arXiv URL: {arxiv_url} -> {processed_arxiv}")
    assert processed_arxiv == expected_arxiv, f"Expected {expected_arxiv}, got {processed_arxiv}"
    
    # Test regular URL (should remain unchanged)
    regular_url = "https://example.com/article"
    processed_regular = url_preprocessor(regular_url)
    
    print(f"Regular URL: {regular_url} -> {processed_regular}")
    assert processed_regular == regular_url, f"Regular URL should not change"
    
    print("✓ URL preprocessing tests passed!")

def test_article_summary_model():
    """Test ArticleSummary pydantic model."""
    print("\nTesting ArticleSummary model...")
    
    # Test valid data
    summary_data = {
        "short_summary": "This is a short summary.",
        "detailed_summary": "This is a detailed summary with more information."
    }
    
    summary = ArticleSummary(**summary_data)
    print(f"Created summary: {summary.short_summary}")
    
    # Test model validation
    assert summary.short_summary == summary_data["short_summary"]
    assert summary.detailed_summary == summary_data["detailed_summary"]
    
    print("✓ ArticleSummary model tests passed!")

def test_link_status_enum():
    """Test that the new 'skipped' status is available."""
    print("\nTesting LinkStatus enum...")
    
    # Test that skipped status exists
    assert hasattr(LinkStatus, 'skipped'), "LinkStatus should have 'skipped' attribute"
    assert LinkStatus.skipped.value == "skipped", "Skipped status value should be 'skipped'"
    
    # Test all statuses
    expected_statuses = ["new", "processing", "processed", "failed", "skipped"]
    actual_statuses = [status.value for status in LinkStatus]
    
    print(f"Available statuses: {actual_statuses}")
    for status in expected_statuses:
        assert status in actual_statuses, f"Status '{status}' should be available"
    
    print("✓ LinkStatus enum tests passed!")

if __name__ == "__main__":
    print("Running tests for implemented fixes...\n")
    
    try:
        test_url_preprocessing()
        test_article_summary_model()
        test_link_status_enum()
        
        print("\n🎉 All tests passed! The fixes have been implemented successfully.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)