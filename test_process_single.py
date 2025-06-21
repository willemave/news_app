#!/usr/bin/env python3
"""Test processing a single content item to debug logging."""

import logging
from app.core.logging import setup_logging
from app.pipeline.worker import ContentWorker
from app.core.db import get_db
from app.models.schema import Content

# Set up logging with DEBUG level
logger = setup_logging(level="DEBUG")

# Create worker
worker = ContentWorker()

# Get a single new content item
with get_db() as db:
    content = db.query(Content).filter(Content.status == "new").first()
    if content:
        print(f"\nProcessing content {content.id}: {content.url}")
        print(f"Content type: {content.content_type}")
        print("-" * 80)
        
        # Process it
        success = worker.process_content(content.id, "test-worker")
        
        print("-" * 80)
        print(f"Processing result: {'SUCCESS' if success else 'FAILED'}")
        
        # Check updated status
        db.refresh(content)
        print(f"Final status: {content.status}")
    else:
        print("No new content found")