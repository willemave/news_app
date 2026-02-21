## Purpose
Verifies base assertions on the `Content` ORM model itself (default metadata, status transitions, checkout fields, processing task links).

## Test Coverage Focus
Tests cover article/podcast/news creation, metadata JSON storage, status transitions, checkout assignments, and relational fields like `ProcessingTask`.

## Key Fixtures/Helpers
- `Content` builder with metadata variations.
- `ProcessingTask` to prove tasks reference contents.
- `datetime` to validate transitions/`processed_at` assignments.

## Gaps or Brittleness
No database commit, so constraints (e.g., unique URLs) are not tested.
Refactor: Group repeated metadata dictionaries into helpers for readability.

## Refactor Opportunities
Create data fixtures for each content type to avoid repeating inline metadata dicts.

Reviewed files: 2
