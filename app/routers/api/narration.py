"""Unified narration endpoint for content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from sqlalchemy.orm import Session

from app.core.db import get_readonly_db_session
from app.core.deps import get_current_user
from app.models.schema import Content
from app.models.user import User
from app.presenters.content_presenter import build_domain_content
from app.routers.api.models import NarrationResponse
from app.services.voice.narration_tts import get_digest_narration_tts_service
from app.services.voice.persistence import build_summary_narration

router = APIRouter()

NarrationTargetType = Literal["content"]


@dataclass(frozen=True)
class NarrationPayload:
    """Resolved narration payload before formatting/encoding."""

    target_type: NarrationTargetType
    target_id: int
    title: str
    narration_text: str
    audio_filename: str


def _prefers_audio(request: Request) -> bool:
    """Return whether the client explicitly asked for audio bytes."""

    accept_header = request.headers.get("accept", "")
    return "audio/mpeg" in accept_header.lower()


def _resolve_content_narration_payload(
    *,
    db: Session,
    target_id: int,
) -> NarrationPayload:
    """Build narration payload for a regular content item."""

    content = db.query(Content).filter(Content.id == target_id).first()
    if content is None:
        raise HTTPException(status_code=404, detail="Content not found")

    try:
        title = build_domain_content(content).display_title
    except Exception:
        title = (content.title or "").strip() or f"Content {content.id}"

    narration_text = build_summary_narration(content, title=title)
    return NarrationPayload(
        target_type="content",
        target_id=content.id,
        title=title,
        narration_text=narration_text,
        audio_filename=f"content-{content.id}.mp3",
    )


def _resolve_narration_payload(
    *,
    target_type: NarrationTargetType,
    target_id: int,
    db: Session,
    current_user: User,
) -> NarrationPayload:
    """Resolve narration target into one normalized payload."""

    del current_user
    return _resolve_content_narration_payload(db=db, target_id=target_id)


@router.get(
    "/narration/{target_type}/{target_id}",
    response_model=NarrationResponse,
    summary="Get narration text or audio for a content target",
    responses={
        200: {
            "content": {
                "audio/mpeg": {},
            }
        }
    },
)
def get_narration(
    request: Request,
    target_type: Annotated[
        NarrationTargetType,
        Path(description="Narration target type"),
    ],
    target_id: Annotated[int, Path(..., gt=0, description="Target identifier")],
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NarrationResponse | Response:
    """Return narration text or MP3 audio for one target."""

    payload = _resolve_narration_payload(
        target_type=target_type,
        target_id=target_id,
        db=db,
        current_user=current_user,
    )

    if _prefers_audio(request):
        try:
            audio_bytes = get_digest_narration_tts_service().synthesize_mp3(
                text=payload.narration_text,
                item_id=payload.target_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'inline; filename="{payload.audio_filename}"',
            },
        )

    return NarrationResponse(
        target_type=payload.target_type,
        target_id=payload.target_id,
        title=payload.title,
        narration_text=payload.narration_text,
    )
