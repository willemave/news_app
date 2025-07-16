#!/usr/bin/env python3
"""Check content in database."""

import sys
from pathlib import Path

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.db import get_db_session
from app.models.schema import Content

# Get database session
with get_db_session() as db:
    total_content = db.query(Content).count()
    content_with_pub_date = db.query(Content).filter(Content.publication_date != None).count()
    content_without_pub_date = db.query(Content).filter(Content.publication_date == None).count()

    print(f"Total content: {total_content}")
    print(f"Content with publication_date: {content_with_pub_date}")
    print(f"Content without publication_date: {content_without_pub_date}")

    # Show samples
    if total_content > 0:
        # Check for content with publication_date in metadata
        contents_with_meta_pub_date = 0
        for content in db.query(Content).limit(20):
            if content.content_metadata and "publication_date" in content.content_metadata:
                contents_with_meta_pub_date += 1
                print(f"\nContent with metadata publication_date:")
                print(f"  ID: {content.id}")
                print(f"  Title: {content.title[:50]}...")
                print(f"  Created at: {content.created_at}")
                print(f"  DB publication_date: {content.publication_date}")
                print(f"  Metadata publication_date: {content.content_metadata['publication_date']}")
                break
        
        if contents_with_meta_pub_date == 0:
            print("\nNo content found with publication_date in metadata (checked first 20)")