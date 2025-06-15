#!/usr/bin/env python3
"""
Test HtmlStrategy with faster extraction (no LLM filtering).
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.html_strategy import HtmlProcessorStrategy


async def test_fast_extraction():
    """Test extraction without LLM filtering for speed."""
    print("Testing fast extraction (without LLM filtering)\n")
    
    test_urls = [
        ("https://example.com", "Simple example page"),
        ("https://en.wikipedia.org/wiki/Python_(programming_language)", "Wikipedia article"),
        ("https://news.ycombinator.com", "Hacker News homepage"),
    ]
    
    # Configure browser
    browser_config = BrowserConfig(
        headless=True,
        viewport_width=1280,
        viewport_height=720
    )
    
    # Configure crawler run WITHOUT LLM filtering
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_for="body",
        delay_before_return_html=1.0
    )
    
    for url, description in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {description}")
        print(f"URL: {url}")
        print(f"{'='*60}\n")
        
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                
                if result.success:
                    # Get content
                    content = ""
                    if hasattr(result, 'markdown') and result.markdown:
                        if hasattr(result.markdown, 'raw_markdown'):
                            content = result.markdown.raw_markdown
                        elif isinstance(result.markdown, str):
                            content = result.markdown
                        else:
                            content = str(result.markdown)
                    
                    title = result.metadata.get("title", "N/A") if result.metadata else "N/A"
                    
                    print(f"✓ Success!")
                    print(f"- Title: {title}")
                    print(f"- Content Length: {len(content):,} characters")
                    print(f"- URL: {result.url}")
                    
                    # Show preview
                    if content:
                        lines = content.split('\n')
                        non_empty_lines = [l for l in lines if l.strip()]
                        print(f"\nFirst 5 non-empty lines:")
                        print("-" * 40)
                        for line in non_empty_lines[:5]:
                            print(line[:80] + "..." if len(line) > 80 else line)
                        print("-" * 40)
                else:
                    print(f"✗ Failed: {result.error_message}")
                    
        except Exception as e:
            print(f"✗ Error: {str(e)}")


async def test_with_html_strategy():
    """Also test with the actual HtmlStrategy to compare."""
    print(f"\n\n{'='*60}")
    print("Testing with HtmlStrategy (includes preprocessing)")
    print(f"{'='*60}\n")
    
    # Initialize strategy
    http_client = RobustHttpClient()
    strategy = HtmlProcessorStrategy(http_client)
    
    # Test PubMed URL transformation
    pubmed_url = "https://pubmed.ncbi.nlm.nih.gov/12345"
    processed = strategy.preprocess_url(pubmed_url)
    print(f"PubMed URL preprocessing:")
    print(f"  Original: {pubmed_url}")
    print(f"  Processed: {processed}")
    print(f"  Source detected: {strategy._detect_source(processed)}")
    
    # Test ArXiv URL transformation  
    arxiv_url = "https://arxiv.org/abs/2312.02121"
    processed = strategy.preprocess_url(arxiv_url)
    print(f"\nArXiv URL preprocessing:")
    print(f"  Original: {arxiv_url}")
    print(f"  Processed: {processed}")
    print(f"  Source detected: {strategy._detect_source(processed)}")


if __name__ == "__main__":
    print("Fast HTML Extraction Test")
    print("This tests crawl4ai without LLM filtering for faster results\n")
    
    asyncio.run(test_fast_extraction())
    asyncio.run(test_with_html_strategy())