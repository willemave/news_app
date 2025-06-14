#!/usr/bin/env python3
"""
Test script to verify error logging infrastructure is working.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.error_logger import create_error_logger
from app.services.http import get_http_service
from app.http_client.robust_http_client import RobustHttpClient
import httpx

async def test_error_logging():
    """Test that errors are properly logged to files."""
    
    print("🧪 Testing error logging infrastructure...")
    
    # Test 1: Direct error logger
    print("\n1. Testing direct error logger...")
    error_logger = create_error_logger("test_component")
    
    try:
        raise ValueError("This is a test error")
    except Exception as e:
        error_logger.log_error(
            error=e,
            operation="test_operation",
            context={"test": "data"},
            item_id="test-item-123"
        )
    
    print("   ✓ Direct error logged")
    
    # Test 2: HTTP service errors
    print("\n2. Testing HTTP service error logging...")
    http_service = get_http_service()
    
    try:
        # This should generate a 404 error
        await http_service.fetch("https://httpbin.org/status/404")
    except httpx.HTTPStatusError as e:
        print(f"   ✓ HTTP error caught: {e.response.status_code}")
    except Exception as e:
        print(f"   ✓ Other error caught: {e}")
    
    try:
        # This should generate a 429 error (like the original issue)
        await http_service.fetch("https://httpbin.org/status/429")
    except httpx.HTTPStatusError as e:
        print(f"   ✓ Rate limit error caught: {e.response.status_code}")
    except Exception as e:
        print(f"   ✓ Other error caught: {e}")
    
    # Test 3: Robust HTTP client errors
    print("\n3. Testing Robust HTTP client error logging...")
    robust_client = RobustHttpClient()
    
    try:
        # This should generate a 403 error (like the original issue)
        robust_client.get("https://httpbin.org/status/403")
    except httpx.HTTPStatusError as e:
        print(f"   ✓ Forbidden error caught: {e.response.status_code}")
    except Exception as e:
        print(f"   ✓ Other error caught: {e}")
    
    finally:
        robust_client.close()
    
    # Check logs directory
    print("\n4. Checking logs directory...")
    logs_dir = Path("logs/errors")
    
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.jsonl"))
        print(f"   ✓ Found {len(log_files)} log files:")
        
        for log_file in log_files:
            print(f"     - {log_file.name}")
            
            # Read and display recent entries
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"       Last entry: {lines[-1].strip()[:100]}...")
                    else:
                        print("       (empty)")
            except Exception as e:
                print(f"       Error reading file: {e}")
    else:
        print("   ❌ Logs directory not found!")
        return False
    
    print("\n✅ Error logging test completed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_error_logging())
    sys.exit(0 if success else 1)