#!/usr/bin/env python3
"""
Test script to verify skip_reason functionality is working correctly.
"""
import sys
from pathlib import Path

# Add the app directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from app.llm import filter_article
from app.utils.failures import record_failure
from app.models import FailurePhase
from app.database import SessionLocal
from app.models import FailureLogs

def test_filter_article():
    """Test that filter_article returns both decision and reason."""
    print("Testing filter_article function...")
    
    # Test with content that should be rejected
    test_content = """
    This is a promotional article about our amazing new product that will revolutionize 
    your life! Buy now and get 50% off! This is clearly marketing content with no 
    technical depth or analysis.
    """
    
    try:
        matches, reason = filter_article(test_content)
        print(f"Filter result: matches={matches}, reason='{reason}'")
        return True
    except Exception as e:
        print(f"Error testing filter_article: {e}")
        return False

def test_record_failure_with_skip_reason():
    """Test that record_failure correctly stores skip_reason."""
    print("\nTesting record_failure with skip_reason...")
    
    try:
        # Record a test failure with skip reason
        test_reason = "Test skip reason: promotional content detected"
        record_failure(
            phase=FailurePhase.processor,
            msg="Test skip message",
            link_id=None,
            skip_reason=test_reason
        )
        
        # Verify it was stored correctly
        db = SessionLocal()
        try:
            latest_failure = db.query(FailureLogs).order_by(FailureLogs.id.desc()).first()
            if latest_failure and latest_failure.skip_reason == test_reason:
                print(f"✓ Skip reason correctly stored: '{latest_failure.skip_reason}'")
                return True
            else:
                print(f"✗ Skip reason not stored correctly. Expected: '{test_reason}', Got: '{latest_failure.skip_reason if latest_failure else 'None'}'")
                return False
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error testing record_failure: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing skip_reason functionality...\n")
    
    test1_passed = test_filter_article()
    test2_passed = test_record_failure_with_skip_reason()
    
    print("\nTest Results:")
    print(f"Filter article test: {'✓ PASSED' if test1_passed else '✗ FAILED'}")
    print(f"Record failure test: {'✓ PASSED' if test2_passed else '✗ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! Skip reason functionality is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")

if __name__ == "__main__":
    main()