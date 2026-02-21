## Purpose
A parallel set of strategy tests that cover detection, extraction, and fallback heuristics before content enters the pipeline.

## Test Coverage Focus
`test_arxiv_strategy` ensures URL normalization, `test_hackernews_strategy` tests fetching/formatting HN data, `test_html_strategy`/`event_loop` cover crawl4ai integration with fallback handling, `test_image_strategy`/`test_pdf_strategy` ensure skip decisions, and `test_pubmed_strategy` handles delegation.

## Key Fixtures/Helpers
- `mock_http_client` and `AsyncMock` crawlers.
- `MagicMock` results for crawler responses.
- Shared sample data (e.g., `SAMPLE_PUBMED_PAGE_HTML_*`).

## Gaps or Brittleness
No tests hit real HTTP/crawl4ai or `yt_dlp`, so downstream async tasks are assumed stable.
Refactor: Introduce helper builders for `AsyncWebCrawler` stubs and for the `MagicMock` results so repeated setups disappear.

## Refactor Opportunities
Make a reusable fixture that returns a crawler whose `arun` yields a provided payload instead of re-creating the patch for each test.

Reviewed files: 8
