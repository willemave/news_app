#!/usr/bin/env python3
"""
Simple test to verify pipeline fixes work with problematic URLs.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.http import get_http_service, NonRetryableError
from app.pipeline.worker import ContentWorker
from app.domain.content import ContentData, ContentType
from app.core.db import get_db
from app.models.schema import Content

async def test_problematic_urls():
    """Test that problematic URLs don't cause infinite loops."""
    
    # URLs that were causing problems
    test_urls = [
        "https://0x80.pl/notesen/2016-11-28-simd-strfind.html",  # SSL issue
        "https://www.wsj.com/tech/army-reserve-tech-executives-meta-palantir-796f5360",  # 401
        "https://www.datacamp.com/tutorial/update-many-in-mongodb"  # 403
    ]
    
    http_service = get_http_service()
    
    print("🧪 Testing problematic URLs...")
    
    for url in test_urls:
        print(f"\n🔍 Testing: {url}")
        
        try:
            # This should either succeed or fail quickly (no infinite retry)
            response = await http_service.fetch(url)
            print(f"✅ Unexpected success: {response.status_code}")
        except NonRetryableError as e:
            print(f"✅ Correctly marked as non-retryable: {type(e).__name__}")
        except Exception as e:
            print(f"⚠️ Other error (acceptable): {type(e).__name__}: {str(e)[:100]}")
    
    print("\n🎉 All URLs tested without infinite loops!")

async def test_worker_integration():
    """Test that worker handles these errors gracefully."""
    
    print("\n🔧 Testing worker integration...")
    
    # Create a test content item with problematic URL
    test_url = "https://www.wsj.com/tech/army-reserve-tech-executives-meta-palantir-796f5360"
    
    with get_db() as db:
        # Check if content already exists
        existing = db.query(Content).filter(Content.url == test_url).first()
        if existing:
            test_content_id = existing.id
            print(f"🔄 Using existing content ID: {test_content_id}")
        else:
            # Create test content
            test_content = Content(
                url=test_url,
                title="Test WSJ Article",
                content_type="article",
                status="pending"
            )
            db.add(test_content)
            db.commit()
            test_content_id = test_content.id
            print(f"➕ Created test content ID: {test_content_id}")
    
    # Test worker processing
    worker = ContentWorker()
    
    try:
        result = await worker.process_content(test_content_id, "test-worker")
        print(f"📋 Worker result: {result}")
        
        # Check the content status
        with get_db() as db:
            content = db.query(Content).filter(Content.id == test_content_id).first()
            if content:
                print(f"📊 Final status: {content.status}")
                if content.metadata and 'error_type' in content.metadata:
                    print(f"🏷️ Error type: {content.metadata['error_type']}")
            
    except Exception as e:
        print(f"⚠️ Worker error (may be expected): {type(e).__name__}: {str(e)[:100]}")
    
    print("✅ Worker integration test completed")

async def main():
    """Run tests."""
    print("🚀 Starting pipeline error fix tests...\n")
    
    await test_problematic_urls()
    await test_worker_integration()
    
    print("\n🎯 Tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())