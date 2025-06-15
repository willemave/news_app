#!/usr/bin/env python3
"""
Simple test script for HtmlStrategy to see crawl4ai in action.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.html_strategy import HtmlProcessorStrategy


async def test_single_url(url: str):
    """Test a single URL and show the extraction process."""
    print(f"\n{'='*60}")
    print(f"Testing URL: {url}")
    print(f"{'='*60}\n")
    
    # Initialize strategy
    http_client = RobustHttpClient()
    strategy = HtmlProcessorStrategy(http_client)
    
    # Check URL preprocessing
    processed_url = strategy.preprocess_url(url)
    print(f"1. URL Preprocessing:")
    print(f"   Original:  {url}")
    print(f"   Processed: {processed_url}")
    
    # Detect source
    source = strategy._detect_source(processed_url)
    print(f"\n2. Source Detection: {source}")
    
    # Extract content
    print(f"\n3. Extracting content with crawl4ai...")
    print("   (This may take a few seconds as it uses a headless browser)\n")
    
    try:
        result = strategy.extract_data("", processed_url)
        
        print(f"4. Extraction Results:")
        print(f"   - Title: {result.get('title', 'N/A')}")
        print(f"   - Author: {result.get('author', 'N/A')}")
        print(f"   - Source: {result.get('source', 'N/A')}")
        print(f"   - Content Length: {len(result.get('text_content', ''))} characters")
        
        # Show content preview
        content = result.get('text_content', '')
        if content:
            print(f"\n5. Content Preview (first 300 chars):")
            print("-" * 40)
            print(content[:300] + "..." if len(content) > 300 else content)
            print("-" * 40)
        else:
            print("\n5. No content extracted!")
            
    except Exception as e:
        print(f"\nError during extraction: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    print("\nSimple HTML Strategy Test")
    print("This script demonstrates the crawl4ai extraction process")
    
    # Test URLs
    test_urls = [
        # A simple blog post
        "https://example.com",
        
        # A PubMed article (will be transformed to PMC)
        "https://pubmed.ncbi.nlm.nih.gov/38709852/",
        
        # An ArXiv paper (will be transformed to PDF)
        "https://arxiv.org/abs/2312.02121"
    ]
    
    for url in test_urls:
        await test_single_url(url)
        
    print(f"\n{'='*60}")
    print("Test completed!")


if __name__ == "__main__":
    import os
    
    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("\n⚠️  Warning: GOOGLE_API_KEY not found in environment variables!")
        print("The LLM content filtering requires this API key to work.")
        print("\nTo set it, run:")
        print("export GOOGLE_API_KEY='your-gemini-api-key'")
        print("\nOr add it to your .env file")
        sys.exit(1)
    
    # Run the test
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted!")
        sys.exit(0)