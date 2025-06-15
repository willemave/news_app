#!/usr/bin/env python3
"""
Quick test to verify HtmlStrategy setup and imports.
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing HtmlStrategy setup...\n")

# Test imports
try:
    from app.http_client.robust_http_client import RobustHttpClient
    print("✓ RobustHttpClient imported successfully")
except ImportError as e:
    print(f"✗ Failed to import RobustHttpClient: {e}")
    sys.exit(1)

try:
    from app.processing_strategies.html_strategy import HtmlProcessorStrategy
    print("✓ HtmlProcessorStrategy imported successfully")
except ImportError as e:
    print(f"✗ Failed to import HtmlProcessorStrategy: {e}")
    sys.exit(1)

try:
    from crawl4ai import AsyncWebCrawler, LLMConfig, LLMContentFilter
    print("✓ crawl4ai components imported successfully")
except ImportError as e:
    print(f"✗ Failed to import crawl4ai: {e}")
    sys.exit(1)

# Test strategy initialization
try:
    http_client = RobustHttpClient()
    strategy = HtmlProcessorStrategy(http_client)
    print("✓ HtmlProcessorStrategy initialized successfully")
except Exception as e:
    print(f"✗ Failed to initialize HtmlProcessorStrategy: {e}")
    sys.exit(1)

# Test URL detection methods
print("\nTesting URL detection methods:")

test_cases = [
    ("https://pubmed.ncbi.nlm.nih.gov/12345", "PubMed"),
    ("https://pmc.ncbi.nlm.nih.gov/articles/PMC12345", "PubMed"),
    ("https://arxiv.org/abs/1234.5678", "Arxiv"),
    ("https://example.com", "web"),
]

for url, expected_source in test_cases:
    detected_source = strategy._detect_source(url)
    status = "✓" if detected_source == expected_source else "✗"
    print(f"  {status} {url} -> {detected_source} (expected: {expected_source})")

# Test URL preprocessing
print("\nTesting URL preprocessing:")

preprocess_cases = [
    ("https://pubmed.ncbi.nlm.nih.gov/12345", "https://pmc.ncbi.nlm.nih.gov/articles/pmid/12345/"),
    ("https://arxiv.org/abs/1234.5678", "https://arxiv.org/pdf/1234.5678"),
    ("https://example.com", "https://example.com"),
]

for original, expected in preprocess_cases:
    processed = strategy.preprocess_url(original)
    status = "✓" if processed == expected else "✗"
    print(f"  {status} {original}")
    print(f"     -> {processed}")

# Check environment
print("\nEnvironment check:")
import os

if os.getenv("GOOGLE_API_KEY"):
    print("✓ GOOGLE_API_KEY is set")
else:
    print("✗ GOOGLE_API_KEY is not set (required for LLM content filtering)")

print("\nSetup verification complete!")
print("\nTo run actual extraction tests:")
print("  python scripts/test_html_simple.py")
print("  python scripts/test_html_strategy.py")