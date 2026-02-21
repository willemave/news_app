## Purpose
Validates the edge cases of the various processing strategies before content reaches the pipeline.

## Test Coverage Focus
Covers arXiv URL normalization, HTML access-gate detection/overrides, strategy output contracts, and YouTube skip/normal flows, so domain-specific heuristics stay stable.

## Key Fixtures/Helpers
- `DummyStrategy`/`FakeClient` helpers for `pdf_strategy`/`youtube_strategy`.
- Monkeypatched `genai`/`yt_dlp` clients to avoid hitting external APIs.
- Additional `hogwash` detection using `HtmlProcessorStrategy._detect_access_gate` helpers.

## Gaps or Brittleness
Still lacks integration with the real HTTP crawler/extraction modules and does not run actual `yt_dlp` downloads, so regressions in those dependencies could slip in.

## Refactor Opportunities
Share the repeated monkeypatch scaffolding for `genai.Client`/custom extractor responses so new strategies only add unique assertions.

Reviewed files: 5
