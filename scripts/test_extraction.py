import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.processing_strategies.html_strategy import HtmlProcessorStrategy
from app.http_client.robust_http_client import RobustHttpClient
import asyncio

http_client = RobustHttpClient()
strategy = HtmlProcessorStrategy(http_client=http_client)

# Test the URLs
urls = [
    'https://mad.science.blog/2020/02/20/junky-mind/',
    'https://seohong.me/blog/q-learning-is-not-yet-scalable/'
]

for url in urls:
    print(f'\nTesting: {url}')
    try:
        result = strategy.extract_data('', url)
        print(f'Title: {result.get("title")}')
        print(f'Content length: {len(result.get("text_content", ""))} chars')
        success = result.get("title") != "Extraction Failed"
        print(f'Success: {success}')
    except Exception as e:
        print(f'Error: {e}')