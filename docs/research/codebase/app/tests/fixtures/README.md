## Purpose
Documents and holds the JSON fixtures injected everywhere via `app/tests/conftest.py`.

## Test Coverage Focus
The README/USAGE guides explain how to load content samples for unit, integration, and pipeline tests, while `content_samples.json` stores five canonical records spanning articles, podcasts, and unprocessed items.

## Key Fixtures/Helpers
- `content_samples.json` with long-form article, short article, completed podcast, unprocessed article, and raw podcast entries.
- README and `USAGE_GUIDE.md` describing how tests should interact with each sample.
- Conventions for injecting `create_sample_content` + derived sample aliases in tests.

## Gaps or Brittleness
No automation ensures the docs stay in sync with new fixture keys, so manual updates are required when the pipeline schema evolves.

## Refactor Opportunities
Consider generating the README sections from the JSON schema or gating fixture additions with a validator so the guide never diverges.

Reviewed files: 3
