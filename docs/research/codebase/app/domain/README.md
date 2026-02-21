## Purpose
Acts as the translator between the SQLAlchemy models (`app.models.schema`) and the domain `ContentData` shape used across services, ensuring metadata normalization before summarization or queueing.

## Key Files
- `app/domain/converters.py` – contains `content_to_domain`, `domain_to_content`, and `_normalize_summary_metadata`, plus helper logic that resolves a canonical HTTP URL for the domain layer.
- `app/domain/__init__.py` – package marker.

## Main Types/Interfaces
- `content_to_domain(db_content)` returns `ContentData` with platform/source defaults, cached metadata, and summary kind inference.
- `domain_to_content(content_data, existing)` updates or creates `app.models.schema.Content` while syncing summary metadata, classification, and retry/failure fields.

## Dependencies & Coupling
Depends on `app.models.schema`, `app.models.metadata`, and `app.utils.*` utilities for summary inference and URL normalization; this module is the primary bridge used by workers and presenters to keep the domain view in sync with the persistence layer.

## Refactor Opportunities
Embed more of the metadata merging logic into reusable helpers (e.g., summary inference) to make `domain_to_content` less imperative, and consider extracting the URL-resolution heuristics so they can be unit tested independently.

Reviewed files: 2
