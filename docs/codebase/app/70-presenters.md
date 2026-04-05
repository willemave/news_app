# Content responses

Source files: `app/routers/api/content_responses.py`, `app/models/content_display.py`

## Purpose
Shape normalized content into API DTOs while keeping reusable display rules outside the router layer.

## Runtime behavior
- Builds list/detail response DTOs from `ContentData` inside the API transport layer.
- Resolves public image/thumbnail URLs, list-readiness checks, and feed-subscription affordances from reusable model helpers.

## Inventory scope
- Direct file inventory for the response-building helpers that replaced `app/presenters`.

## Modules and files
| File | Key symbols | Notes |
|---|---|---|
| `app/routers/api/content_responses.py` | `build_content_summary_response`, `build_fallback_content_summary_response`, `build_content_detail_response` | API-layer builders for content list/detail response DTOs. |
| `app/models/content_display.py` | `resolve_image_urls`, `is_ready_for_list`, `can_subscribe_for_feed` | Reusable display and readiness rules shared by application queries and services. |
