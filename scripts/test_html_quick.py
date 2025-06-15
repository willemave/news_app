#!/usr/bin/env python3
"""
Quick test of HtmlStrategy with a single URL.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.html_strategy import HtmlProcessorStrategy


async def test_extraction():
    """Test extraction with a simple URL."""
    # Initialize strategy
    http_client = RobustHttpClient()
    strategy = HtmlProcessorStrategy(http_client)
    
    # Test with example.com first (simple page)
    url = "https://example.com"
    print(f"Testing extraction from: {url}\n")
    
    try:
        # Extract content
        result = strategy.extract_data("", url)
        
        print("Extraction Results:")
        print(f"- Success: {result.get('title') != 'Extraction Failed'}")
        print(f"- Title: {result.get('title', 'N/A')}")
        print(f"- Source: {result.get('source', 'N/A')}")
        print(f"- Content Length: {len(result.get('text_content', ''))} characters")
        
        content = result.get('text_content', '')
        if content:
            print(f"\nContent Preview:")
            print("-" * 40)
            print(content[:300])
            print("-" * 40)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import os
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY not set!")
        sys.exit(1)
    
    asyncio.run(test_extraction())