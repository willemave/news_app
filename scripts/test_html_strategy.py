#!/usr/bin/env python3
"""
Test script for HtmlStrategy with various URLs to verify crawl4ai integration.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import get_logger
from app.http_client.robust_http_client import RobustHttpClient
from app.processing_strategies.html_strategy import HtmlProcessorStrategy

logger = get_logger(__name__)

# Test URLs covering different sources
TEST_URLS = [
    # General web content
    {
        "url": "https://www.theverge.com/2024/1/1/example-article",
        "description": "Tech news article",
        "expected_source": "web"
    },
    # PubMed URL (should transform to PMC)
    {
        "url": "https://pubmed.ncbi.nlm.nih.gov/38709852/",
        "description": "PubMed article (should transform to PMC)",
        "expected_source": "PubMed"
    },
    # ArXiv URL (should transform to PDF)
    {
        "url": "https://arxiv.org/abs/2401.00001",
        "description": "ArXiv abstract (should transform to PDF)",
        "expected_source": "Arxiv"
    },
    # Direct PMC URL
    {
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11195837/",
        "description": "Direct PMC article",
        "expected_source": "PubMed"
    },
    # Wikipedia article
    {
        "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "description": "Wikipedia article",
        "expected_source": "web"
    },
    # GitHub page
    {
        "url": "https://github.com/anthropics/anthropic-sdk-python",
        "description": "GitHub repository page",
        "expected_source": "web"
    }
]


def print_separator():
    """Print a visual separator."""
    print("\n" + "=" * 80 + "\n")


def print_result(url_info: dict, result: dict):
    """Print formatted extraction result."""
    print(f"URL: {url_info['url']}")
    print(f"Description: {url_info['description']}")
    print(f"Expected Source: {url_info['expected_source']}")
    print(f"Actual Source: {result.get('source', 'N/A')}")
    print(f"Final URL: {result.get('final_url_after_redirects', 'N/A')}")
    print(f"Title: {result.get('title', 'N/A')}")
    print(f"Author: {result.get('author', 'N/A')}")
    print(f"Publication Date: {result.get('publication_date', 'N/A')}")
    print(f"Content Type: {result.get('content_type', 'N/A')}")
    
    # Show content preview
    content = result.get('text_content', '')
    if content:
        preview_length = 500
        content_preview = content[:preview_length]
        if len(content) > preview_length:
            content_preview += "..."
        print(f"\nContent Preview:\n{content_preview}")
        print(f"\nTotal Content Length: {len(content)} characters")
    else:
        print("\nNo content extracted")


async def test_url(strategy: HtmlProcessorStrategy, url_info: dict):
    """Test a single URL with the HtmlStrategy."""
    try:
        print_separator()
        print(f"Testing: {url_info['description']}")
        print(f"Original URL: {url_info['url']}")
        
        # Test URL preprocessing
        processed_url = strategy.preprocess_url(url_info['url'])
        if processed_url != url_info['url']:
            print(f"Preprocessed URL: {processed_url}")
        
        # Test if strategy can handle the URL
        can_handle = strategy.can_handle_url(url_info['url'])
        print(f"Can Handle: {can_handle}")
        
        if can_handle:
            # Extract data
            print("\nExtracting content...")
            result = strategy.extract_data("", processed_url)
            
            # Print results
            print("\nExtraction Results:")
            print_result(url_info, result)
            
            # Test LLM preparation
            if result.get('text_content'):
                llm_data = strategy.prepare_for_llm(result)
                print(f"\nLLM Preparation:")
                print(f"  - Is PDF: {llm_data.get('is_pdf', False)}")
                print(f"  - Content ready for filtering: {'Yes' if llm_data.get('content_to_filter') else 'No'}")
                print(f"  - Content ready for summarization: {'Yes' if llm_data.get('content_to_summarize') else 'No'}")
        else:
            print("Strategy cannot handle this URL")
            
    except Exception as e:
        print(f"\nError testing URL: {str(e)}")
        logger.error(f"Error testing {url_info['url']}: {str(e)}", exc_info=True)


async def main():
    """Main test function."""
    print("HTML Strategy Test Script")
    print("=" * 80)
    
    # Initialize HTTP client and strategy
    http_client = RobustHttpClient()
    strategy = HtmlProcessorStrategy(http_client)
    
    # Test each URL
    for url_info in TEST_URLS:
        await test_url(strategy, url_info)
    
    print_separator()
    print("Test completed!")


if __name__ == "__main__":
    # Note: This script requires the GOOGLE_API_KEY environment variable to be set
    # for the LLM content filtering to work properly
    try:
        import os
        if not os.getenv("GOOGLE_API_KEY"):
            print("\nWarning: GOOGLE_API_KEY environment variable not set.")
            print("The LLM content filtering may not work properly.")
            print("Set it with: export GOOGLE_API_KEY='your-api-key'\n")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                sys.exit(1)
        
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)