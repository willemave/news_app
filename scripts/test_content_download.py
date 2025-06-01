#!/usr/bin/env python3
"""
CLI script to test download_and_process_content function.
Useful for debugging scraper failures and content extraction issues.
"""
import sys
import json
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.processor import download_and_process_content
from app.config import logger


def format_content_output(content_data: dict) -> str:
    """Format the content data for CLI display."""
    if not content_data:
        return "❌ No content extracted"
    
    output = []
    output.append("=" * 80)
    output.append("📄 CONTENT EXTRACTION RESULTS")
    output.append("=" * 80)
    
    # Basic metadata
    output.append(f"🔗 URL: {content_data.get('url', 'N/A')}")
    output.append(f"📰 Title: {content_data.get('title', 'N/A')}")
    output.append(f"✍️  Author: {content_data.get('author', 'N/A')}")
    output.append(f"📅 Publication Date: {content_data.get('publication_date', 'N/A')}")
    output.append(f"📄 Is PDF: {content_data.get('is_pdf', False)}")
    
    # Content info
    content = content_data.get('content', '')
    if content:
        output.append(f"📏 Content Length: {len(content)} characters")
        output.append("")
        output.append("📝 CONTENT PREVIEW (first 500 chars):")
        output.append("-" * 50)
        preview = content[:500]
        if len(content) > 500:
            preview += "..."
        output.append(preview)
        output.append("-" * 50)
        
        if content_data.get('is_pdf'):
            output.append("📋 Note: PDF content is base64 encoded")
    else:
        output.append("⚠️  No content extracted")
    
    output.append("=" * 80)
    return "\n".join(output)


def main():
    """Main CLI function."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/test_content_download.py <URL>")
        print("Example: python scripts/test_content_download.py https://example.com/article")
        sys.exit(1)
    
    url = sys.argv[1]
    
    print(f"🚀 Testing content download for: {url}")
    print("⏳ Downloading and processing...")
    print()
    
    try:
        # Test the download_and_process_content function
        content_data = download_and_process_content(url)
        
        # Format and display results
        formatted_output = format_content_output(content_data)
        print(formatted_output)
        
        # Also save raw JSON for debugging
        if content_data:
            json_file = Path("debug_content_output.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                # Create a copy without the full content for JSON readability
                json_data = content_data.copy()
                if json_data.get('content') and len(json_data['content']) > 1000:
                    json_data['content_preview'] = json_data['content'][:1000] + "..."
                    json_data['content_length'] = len(content_data['content'])
                    del json_data['content']  # Remove full content from JSON
                
                json.dump(json_data, f, indent=2, default=str)
            
            print(f"💾 Raw data saved to: {json_file}")
            print("✅ Content extraction successful!")
        else:
            print("❌ Content extraction failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"💥 Error during content download: {e}")
        logger.error(f"CLI test error for {url}: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()