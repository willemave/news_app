# Content mapping helpers

Source files: `app/models/content_mapper.py`, `app/models/content_form.py`

## Purpose
Translate SQLAlchemy content rows to the normalized `ContentData` model and keep small content-shape helpers close to the shared model layer.

## Runtime behavior
- Normalizes ORM data into a stable content object so application queries, services, and workers do not need to know raw column details.
- Concentrates `ContentData` conversion and content-form helpers under `app/models/` instead of a separate top-level domain package.

## Inventory scope
- Direct file inventory for the content-mapping helpers that replaced `app/domain`.

## Modules and files
| File | Key symbols | Notes |
|---|---|---|
| `app/models/content_mapper.py` | `content_to_domain`, `domain_to_content` | Converts between ORM `Content` rows and canonical `ContentData`. |
| `app/models/content_form.py` | `derive_content_form` | Derives canonical short/long form labels from content type. |
