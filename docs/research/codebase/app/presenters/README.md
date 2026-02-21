## Purpose
Transforms domain `ContentData` plus database state into the API DTOs consumed by the iOS/web clients, handling image URL resolution, classification, and detected feed data.

## Key Files
- `app/presenters/content_presenter.py` – helper functions that compute image/thumbnail URLs, news-specific fields, and build `ContentSummaryResponse`/`ContentDetailResponse` payloads.

## Main Types/Interfaces
- `resolve_image_urls(domain_content)` chooses generated or stored URLs.
- `build_content_summary_response` and `build_content_detail_response` convert domain models into `app.routers.api.models` responses while respecting read/favorite flags.

## Dependencies & Coupling
Tightly depends on `app.domain.converters`, `app.models.schema.Content`, and the response Pydantic models under `app.routers.api.models`, plus utility builders from `app.utils.image_urls`.

## Refactor Opportunities
Image URL resolution and news-field logic could be split into smaller helpers or a dedicated presenter class so the file stays readable as the response shape evolves (e.g., this module mixes news vs. article logic in one function).

Reviewed files: 1
