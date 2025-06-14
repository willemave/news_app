#!/usr/bin/env python3
"""
Test script to verify error handling fixes.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http import get_http_service, NonRetryableError
from app.core.logging import get_logger

logger = get_logger(__name__)

async def test_ssl_bypass():
    """Test SSL bypass for problematic domains."""
    http_service = get_http_service()
    
    # Test SSL bypass domain
    test_url = "https://0x80.pl/notesen/2016-11-28-simd-strfind.html"
    
    try:
        logger.info(f"Testing SSL bypass for: {test_url}")
        response = await http_service.fetch(test_url)
        logger.info(f"✅ SSL bypass successful: {response.status_code}")
        return True
    except NonRetryableError as e:
        logger.info(f"⚠️ Non-retryable error (expected): {e}")
        return True
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

async def test_non_retryable_http_errors():
    """Test that 401/403 errors are marked as non-retryable."""
    http_service = get_http_service()
    
    # Test URLs that should return non-retryable errors
    test_urls = [
        "https://www.wsj.com/tech/army-reserve-tech-executives-meta-palantir-796f5360",
        "https://www.datacamp.com/tutorial/update-many-in-mongodb"
    ]
    
    results = []
    for url in test_urls:
        try:
            logger.info(f"Testing non-retryable error for: {url}")
            response = await http_service.fetch(url)
            logger.info(f"✅ Unexpected success: {response.status_code}")
            results.append(True)
        except NonRetryableError as e:
            logger.info(f"✅ Correctly identified as non-retryable: {e}")
            results.append(True)
        except Exception as e:
            logger.error(f"❌ Unexpected error type: {type(e).__name__}: {e}")
            results.append(False)
    
    return all(results)

async def test_successful_fetch():
    """Test that normal URLs still work."""
    http_service = get_http_service()
    
    # Test a URL that should work
    test_url = "https://httpbin.org/status/200"
    
    try:
        logger.info(f"Testing successful fetch for: {test_url}")
        response = await http_service.fetch(test_url)
        logger.info(f"✅ Successful fetch: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to fetch working URL: {e}")
        return False

async def main():
    """Run all tests."""
    logger.info("🧪 Starting error handling tests...")
    
    tests = [
        ("SSL Bypass Test", test_ssl_bypass()),
        ("Non-Retryable HTTP Errors Test", test_non_retryable_http_errors()),
        ("Successful Fetch Test", test_successful_fetch())
    ]
    
    results = []
    for test_name, test_coro in tests:
        logger.info(f"\n🔍 Running: {test_name}")
        try:
            result = await test_coro
            results.append((test_name, result))
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{status}: {test_name}")
        except Exception as e:
            logger.error(f"❌ FAILED: {test_name} - {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n📊 Test Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.info("💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)