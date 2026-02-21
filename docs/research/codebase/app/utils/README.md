## Purpose
Utility helpers for dates, URLs, summaries, pagination tokens, image URL generation, and error reporting used pervasively across routers, services, and presenters.

## Key Files
- `dates.py` – timezone-aware helpers for parsing/formatting and `now()` hooks.
- `url_utils.py` – HTTP URL validation/normalization used by submissions and conversions.
- `summary_metadata.py` / `summary_utils.py` – functions that inspect metadata to infer summary kinds, extract short summaries, and sanitize bullet points.
- `image_paths.py`, `image_urls.py` – canonical filesystem/image URL builders for generated thumbnails.
- `pagination.py` – cursor data model and metadata helpers for paged APIs.
- `error_logger.py` – structured error helpers that call into `app.core.logging`.
- `json_repair.py` – attempts to heal broken JSON strings before parsing.

## Main Types/Interfaces
- Cursor helpers (`PaginationCursorData`, `PaginationMetadata`) plus serialization helpers.
- Summary inference (`infer_summary_kind_version`) that tells other layers whether data is `interleaved`, `structured`, or `news`.
- Image URL builders (`build_content_image_url`, `build_news_thumbnail_url`) for content presenters.

## Dependencies & Coupling
Lightweight wrappers on stdlib (`datetime`, `urllib`), Pydantic, and project constants; these modules are imported throughout routers/services/presenters and therefore should stay stable.

## Refactor Opportunities
Some summary helpers duplicate logic around default bullet counts and classification; consolidating them into one `summary_inspector` would make future summary formats easier to support. The image path helpers rely on settings indirectly and might belong near the services that actually write the files.

Reviewed files: 12
