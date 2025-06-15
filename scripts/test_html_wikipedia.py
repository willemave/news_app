#!/usr/bin/env python3
"""
Test HtmlStrategy with a Wikipedia article.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.html_strategy import HtmlProcessorStrategy


async def test_wikipedia():
    """Test extraction with Wikipedia."""
    # Initialize strategy
    http_client = RobustHttpClient()
    strategy = HtmlProcessorStrategy(http_client)
    
    # Test with a Wikipedia article
    url = "https://en.wikipedia.org/wiki/Machine_learning"
    print(f"Testing extraction from: {url}\n")
    
    try:
        # Extract content
        print("Extracting content (this may take 10-30 seconds)...\n")
        result = strategy.extract_data("", url)
        
        print("Extraction Results:")
        print(f"- Success: {result.get('title') != 'Extraction Failed'}")
        print(f"- Title: {result.get('title', 'N/A')}")
        print(f"- Author: {result.get('author', 'N/A')}")
        print(f"- Source: {result.get('source', 'N/A')}")
        print(f"- Content Length: {len(result.get('text_content', '')):,} characters")
        
        content = result.get('text_content', '')
        if content:
            # Find first heading
            lines = content.split('\n')
            print(f"\nFirst few lines of content:")
            print("-" * 60)
            for i, line in enumerate(lines[:20]):
                if line.strip():
                    print(line)
            print("-" * 60)
            
            # Check if it extracted key sections
            key_sections = ['Definition', 'History', 'Types', 'Applications']
            print(f"\nKey sections found:")
            for section in key_sections:
                found = section.lower() in content.lower()
                print(f"- {section}: {'✓' if found else '✗'}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import os
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY not set!")
        sys.exit(1)
    
    asyncio.run(test_wikipedia())