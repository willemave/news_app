"""Daily news digest list and read-status endpoints."""

from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.db import get_db_session, get_readonly_db_session
from app.core.deps import get_current_user
from app.models.pagination import PaginationMetadata
from app.models.schema import DailyNewsDigest
from app.models.user import User
from app.routers.api.models import (
    DailyNewsDigestListResponse,
    DailyNewsDigestResponse,
    DailyNewsDigestVoiceSummaryResponse,
)
from app.services.daily_news_digest import MAX_DAILY_DIGEST_BULLETS

router = APIRouter()


def _isoformat_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    value = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _encode_cursor(*, last_id: int, last_local_date: date, read_filter: str) -> str:
    payload = {
        "last_id": last_id,
        "last_local_date": last_local_date.isoformat(),
        "read_filter": read_filter,
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid digest cursor") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid digest cursor")

    if not isinstance(payload.get("last_id"), int):
        raise ValueError("Invalid digest cursor")
    if not isinstance(payload.get("last_local_date"), str):
        raise ValueError("Invalid digest cursor")
    if payload.get("read_filter") not in {"all", "read", "unread"}:
        raise ValueError("Invalid digest cursor")

    try:
        payload["last_local_date"] = date.fromisoformat(payload["last_local_date"])
    except ValueError as exc:
        raise ValueError("Invalid digest cursor") from exc

    return payload


def _build_digest_response(digest: DailyNewsDigest) -> DailyNewsDigestResponse:
    key_points = digest.key_points if isinstance(digest.key_points, list) else []
    source_ids = digest.source_content_ids if isinstance(digest.source_content_ids, list) else []
    return DailyNewsDigestResponse(
        id=digest.id,
        local_date=digest.local_date.isoformat(),
        timezone=digest.timezone,
        title=digest.title,
        summary=digest.summary,
        key_points=[point for point in key_points if isinstance(point, str)],
        source_count=int(digest.source_count or 0),
        source_content_ids=[int(cid) for cid in source_ids if isinstance(cid, int)],
        is_read=digest.read_at is not None,
        read_at=_isoformat_utc(digest.read_at),
        generated_at=_isoformat_utc(digest.generated_at) or "",
    )


@router.get(
    "/daily-digests",
    response_model=DailyNewsDigestListResponse,
    summary="List daily news digest cards",
)
def list_daily_news_digests(
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    read_filter: Annotated[
        str,
        Query(
            description="Filter by read status (all/read/unread)",
            pattern="^(all|read|unread)$",
        ),
    ] = "unread",
    cursor: Annotated[str | None, Query(description="Pagination cursor for next page")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DailyNewsDigestListResponse:
    """List per-user daily digest rows."""
    last_id: int | None = None
    last_local_date: date | None = None
    if cursor:
        try:
            decoded = _decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if decoded["read_filter"] != read_filter:
            raise HTTPException(status_code=400, detail="Cursor invalid: filters changed.")
        last_id = decoded["last_id"]
        last_local_date = decoded["last_local_date"]

    query = db.query(DailyNewsDigest).filter(DailyNewsDigest.user_id == current_user.id)
    if read_filter == "read":
        query = query.filter(DailyNewsDigest.read_at.is_not(None))
    elif read_filter == "unread":
        query = query.filter(DailyNewsDigest.read_at.is_(None))

    if last_id is not None and last_local_date is not None:
        query = query.filter(
            or_(
                DailyNewsDigest.local_date < last_local_date,
                and_(DailyNewsDigest.local_date == last_local_date, DailyNewsDigest.id < last_id),
            )
        )

    rows = (
        query.order_by(DailyNewsDigest.local_date.desc(), DailyNewsDigest.id.desc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    next_cursor = None
    if has_more and rows:
        last_row = rows[-1]
        next_cursor = _encode_cursor(
            last_id=last_row.id,
            last_local_date=last_row.local_date,
            read_filter=read_filter,
        )

    return DailyNewsDigestListResponse(
        digests=[_build_digest_response(row) for row in rows],
        meta=PaginationMetadata(
            next_cursor=next_cursor,
            has_more=has_more,
            page_size=len(rows),
            total=len(rows),
        ),
    )


@router.post(
    "/daily-digests/{digest_id}/mark-read",
    summary="Mark one daily digest as read",
)
def mark_daily_digest_read(
    digest_id: Annotated[int, Path(..., gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Mark a single daily digest row as read."""
    digest = (
        db.query(DailyNewsDigest)
        .filter(DailyNewsDigest.id == digest_id, DailyNewsDigest.user_id == current_user.id)
        .first()
    )
    if digest is None:
        raise HTTPException(status_code=404, detail="Daily digest not found")

    digest.read_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return {
        "status": "success",
        "digest_id": digest.id,
        "is_read": True,
        "read_at": _isoformat_utc(digest.read_at),
    }


@router.delete(
    "/daily-digests/{digest_id}/mark-unread",
    summary="Mark one daily digest as unread",
)
def mark_daily_digest_unread(
    digest_id: Annotated[int, Path(..., gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Mark a single daily digest row as unread."""
    digest = (
        db.query(DailyNewsDigest)
        .filter(DailyNewsDigest.id == digest_id, DailyNewsDigest.user_id == current_user.id)
        .first()
    )
    if digest is None:
        raise HTTPException(status_code=404, detail="Daily digest not found")

    digest.read_at = None
    db.commit()
    return {
        "status": "success",
        "digest_id": digest.id,
        "is_read": False,
        "read_at": None,
    }


@router.get(
    "/daily-digests/{digest_id}/voice-summary",
    response_model=DailyNewsDigestVoiceSummaryResponse,
    summary="Get narration text for one daily digest",
)
def get_daily_digest_voice_summary(
    digest_id: Annotated[int, Path(..., gt=0)],
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DailyNewsDigestVoiceSummaryResponse:
    """Return narration script text for one digest."""
    digest = (
        db.query(DailyNewsDigest)
        .filter(DailyNewsDigest.id == digest_id, DailyNewsDigest.user_id == current_user.id)
        .first()
    )
    if digest is None:
        raise HTTPException(status_code=404, detail="Daily digest not found")

    points = digest.key_points if isinstance(digest.key_points, list) else []
    cleaned_points = [point.strip() for point in points if isinstance(point, str) and point.strip()]

    narration_parts = [f"Daily news roll-up for {digest.local_date.isoformat()}."]
    if cleaned_points:
        narration_parts.append("Key points:")
        narration_parts.extend(cleaned_points[:MAX_DAILY_DIGEST_BULLETS])
    elif digest.summary.strip():
        narration_parts.append(digest.summary.strip())

    narration_text = " ".join(part for part in narration_parts if part)
    return DailyNewsDigestVoiceSummaryResponse(
        digest_id=digest.id,
        title=digest.title,
        narration_text=narration_text,
    )
