"""Helpers for transitioning metadata from flat blobs to structured state.

Migration strategy:
    Phase 1 (current): dual-write — top-level keys are preserved alongside
    ``domain``/``processing`` namespaces so legacy readers keep working.
    Phase 2: migrate all readers to ``merge_runtime_metadata()`` or direct
    namespace access, then stop writing top-level duplicates.
    Phase 3: one-off migration script to strip top-level duplicates from DB.
"""

from __future__ import annotations

from typing import Any

DOMAIN_KEY = "domain"
PROCESSING_KEY = "processing"

# Runtime/operational keys that should live under `processing`.
PROCESSING_FIELD_NAMES: set[str] = {
    "subscribe_to_feed",
    "feed_subscription",
    "detected_feed",
    "all_detected_feeds",
    "share_and_chat_user_ids",
    "submitted_by_user_id",
    "submitted_via",
    "platform_hint",
    "content_to_summarize",
    "processing_errors",
    "canonical_content_id",
    "tweet_enrichment",
    "tweet_only",
}


def normalize_metadata_shape(raw_metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Return metadata with explicit `domain` and `processing` namespaces.

    This helper is backward-compatible: existing top-level fields remain untouched,
    while nested `domain`/`processing` mirrors are materialized for new code paths.

    Args:
        raw_metadata: Existing metadata payload.

    Returns:
        Normalized metadata dictionary with both namespaces present.
    """
    metadata = dict(raw_metadata or {})

    domain = metadata.get(DOMAIN_KEY)
    if not isinstance(domain, dict):
        domain = {}

    processing = metadata.get(PROCESSING_KEY)
    if not isinstance(processing, dict):
        processing = {}

    for key, value in metadata.items():
        if key in {DOMAIN_KEY, PROCESSING_KEY}:
            continue
        if key in PROCESSING_FIELD_NAMES:
            processing.setdefault(key, value)
        else:
            domain.setdefault(key, value)

    metadata[DOMAIN_KEY] = domain
    metadata[PROCESSING_KEY] = processing
    return metadata


def merge_runtime_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Return a flat compatibility view of metadata.

    Args:
        metadata: Structured or legacy metadata payload.

    Returns:
        Flat metadata with `domain` values overlaid by `processing` values.
    """
    normalized = normalize_metadata_shape(metadata)
    merged: dict[str, Any] = {}
    merged.update(normalized.get(DOMAIN_KEY, {}))
    merged.update(normalized.get(PROCESSING_KEY, {}))
    return merged


def update_processing_state(
    metadata: dict[str, Any] | None,
    **processing_fields: Any,
) -> dict[str, Any]:
    """Set processing fields in metadata while preserving compatibility.

    Args:
        metadata: Existing metadata.
        **processing_fields: Processing fields to set.

    Returns:
        Updated metadata containing the new processing values both in
        `processing` namespace and at top-level for legacy readers.
    """
    normalized = normalize_metadata_shape(metadata)
    processing = dict(normalized.get(PROCESSING_KEY, {}))
    processing.update(processing_fields)
    normalized[PROCESSING_KEY] = processing

    for key, value in processing_fields.items():
        normalized[key] = value
    return normalized

