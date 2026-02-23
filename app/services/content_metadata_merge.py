"""Helpers for safe content metadata writes under concurrent task updates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.models.schema import Content


def compute_metadata_patch(
    base_metadata: Mapping[str, Any] | None,
    updated_metadata: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], set[str]]:
    """Compute changed and removed keys between metadata snapshots.

    Args:
        base_metadata: Metadata snapshot taken before local mutations.
        updated_metadata: Metadata after local mutations.

    Returns:
        Tuple of:
            - updates: keys whose values changed or were newly added.
            - removed_keys: keys removed by local mutations.
    """
    base = _coerce_metadata(base_metadata)
    updated = _coerce_metadata(updated_metadata)

    updates = {
        key: value
        for key, value in updated.items()
        if key not in base or base.get(key) != value
    }
    removed_keys = {key for key in base if key not in updated}
    return updates, removed_keys


def refresh_merge_content_metadata(
    db: Session,
    content_id: int | None,
    *,
    base_metadata: Mapping[str, Any] | None,
    updated_metadata: Mapping[str, Any] | None,
    latest_metadata: Mapping[str, Any] | None = None,
    preserve_latest_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Merge metadata changes into the latest persisted metadata snapshot.

    This applies a patch (diff between ``base_metadata`` and ``updated_metadata``)
    on top of the latest metadata from the database, reducing accidental
    overwrite of unrelated concurrent updates.

    Args:
        db: Active SQLAlchemy session.
        content_id: Content identifier to refresh from DB.
        base_metadata: Metadata snapshot before local mutations.
        updated_metadata: Metadata after local mutations.
        latest_metadata: Optional already-loaded latest metadata snapshot.
        preserve_latest_keys: Keys that should always keep the latest DB values.

    Returns:
        Merged metadata dictionary ready to persist.
    """
    latest_metadata_resolved = (
        _coerce_metadata(latest_metadata)
        if latest_metadata is not None
        else _load_latest_content_metadata(db, content_id, fallback=updated_metadata)
    )
    updates, removed_keys = compute_metadata_patch(base_metadata, updated_metadata)

    merged = dict(latest_metadata_resolved)
    for key in removed_keys:
        merged.pop(key, None)
    merged.update(updates)

    if preserve_latest_keys:
        for key in preserve_latest_keys:
            if key in latest_metadata_resolved:
                merged[key] = latest_metadata_resolved[key]
            else:
                merged.pop(key, None)

    return merged


def _load_latest_content_metadata(
    db: Session,
    content_id: int | None,
    *,
    fallback: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return latest content metadata from DB (or fallback when unavailable)."""
    if not content_id:
        return _coerce_metadata(fallback)

    row = (
        db.query(Content.content_metadata)
        .filter(Content.id == int(content_id))
        .first()
    )
    if row is None:
        return _coerce_metadata(fallback)
    if isinstance(row, (tuple, list)):
        if not row:
            return _coerce_metadata(fallback)
        return _coerce_metadata(row[0])
    if hasattr(row, "content_metadata"):
        return _coerce_metadata(row.content_metadata)
    return _coerce_metadata(row)


def _coerce_metadata(raw_metadata: Mapping[str, Any] | None | Any) -> dict[str, Any]:
    """Return a plain dictionary for metadata payloads."""
    if isinstance(raw_metadata, dict):
        return dict(raw_metadata)
    return {}
