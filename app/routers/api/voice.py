"""Realtime voice conversation endpoints."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Annotated, Any
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.db import get_db, get_db_session, get_readonly_db_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.core.security import verify_token
from app.core.settings import get_settings
from app.models.user import User
from app.routers.api.voice_models import (
    VOICE_CLIENT_EVENT_ADAPTER,
    CreateVoiceSessionRequest,
    CreateVoiceSessionResponse,
    VoiceHealthResponse,
)
from app.services.voice.elevenlabs_streaming import build_voice_health_flags
from app.services.voice.orchestrator import VoiceConversationOrchestrator
from app.services.voice.persistence import (
    build_live_intro_text,
    format_voice_content_context,
    load_voice_content_context,
    mark_live_voice_onboarding_complete,
    resolve_or_create_voice_chat_session,
)
from app.services.voice.session_manager import (
    configure_voice_session,
    create_voice_session,
    get_voice_session,
    prune_voice_sessions,
    set_voice_session_intro_pending,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

TURN_SCOPED_EVENT_TYPES = {
    "turn.started",
    "transcript.partial",
    "transcript.final",
    "assistant.text.delta",
    "assistant.text.final",
    "assistant.audio.chunk",
    "assistant.audio.final",
    "turn.completed",
    "turn.cancelled",
}
MAX_INTERRUPTED_CARRYOVER_CHARS = 400


def _truncate_carryover_text(
    raw_text: str,
    *,
    max_chars: int = MAX_INTERRUPTED_CARRYOVER_CHARS,
) -> str:
    """Bound interrupted assistant carryover text length."""

    trimmed = raw_text.strip()
    if not trimmed:
        return ""
    if len(trimmed) <= max_chars:
        return trimmed
    return trimmed[-max_chars:].lstrip()


def _extract_websocket_bearer_token(websocket: WebSocket) -> str | None:
    """Extract bearer token from websocket headers or query param."""

    authorization = websocket.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            return token

    query_token = websocket.query_params.get("token", "").strip()
    if query_token:
        return query_token
    return None


def _authenticate_websocket_user(websocket: WebSocket, db: Session) -> User | None:
    """Authenticate websocket user via JWT bearer token."""

    token = _extract_websocket_bearer_token(websocket)
    if not token:
        return None

    try:
        payload = verify_token(token)
    except jwt.InvalidTokenError:
        return None

    user_id = payload.get("sub")
    token_type = payload.get("type")
    if not user_id or token_type != "access":
        return None

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        return None
    return user


async def _send_ws_event(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    payload: dict[str, Any],
) -> bool:
    """Send one websocket event payload safely."""

    try:
        async with send_lock:
            await websocket.send_json(payload)
        return True
    except Exception:
        return False


async def _cancel_task(task: asyncio.Task[Any] | None) -> None:
    """Cancel task and wait for shutdown."""

    if task is None:
        return
    if task.done():
        with suppress(asyncio.CancelledError, Exception):
            task.result()
        return
    task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await task


@router.post("/sessions", response_model=CreateVoiceSessionResponse)
async def create_or_resume_voice_session(
    payload: CreateVoiceSessionRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CreateVoiceSessionResponse:
    """Create or resume an authenticated voice session."""

    try:
        state = create_voice_session(user_id=current_user.id, session_id=payload.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    settings = get_settings()
    context = load_voice_content_context(
        db,
        user_id=current_user.id,
        content_id=payload.content_id,
        include_summary_narration=payload.launch_mode == "dictate_summary",
    )
    content_context = format_voice_content_context(context)
    chat_session = resolve_or_create_voice_chat_session(
        db,
        user_id=current_user.id,
        existing_chat_session_id=payload.chat_session_id or state.chat_session_id,
        context=context,
        launch_mode=payload.launch_mode,
        model_spec=settings.voice_haiku_model,
    )
    pending_intro = bool(payload.request_intro)
    is_onboarding_intro = bool(
        pending_intro and not current_user.has_completed_live_voice_onboarding
    )
    logger.info(
        "Voice session configured",
        extra={
            "component": "voice_api",
            "operation": "create_session",
            "item_id": current_user.id,
            "context_data": {
                "session_id": state.session_id,
                "launch_mode": payload.launch_mode,
                "request_intro": payload.request_intro,
                "pending_intro": pending_intro,
                "is_onboarding_intro": is_onboarding_intro,
                "has_completed_live_voice_onboarding": bool(
                    current_user.has_completed_live_voice_onboarding
                ),
            },
        },
    )
    configured_state = configure_voice_session(
        session_id=state.session_id,
        user_id=current_user.id,
        chat_session_id=chat_session.id,
        content_id=context.content_id if context is not None else None,
        launch_mode=payload.launch_mode,
        source_surface=payload.source_surface,
        pending_intro=pending_intro,
        is_onboarding_intro=is_onboarding_intro,
        content_context=content_context,
        content_title=context.title if context is not None else None,
        summary_narration=context.summary_narration if context is not None else None,
    )
    if configured_state is None:
        raise HTTPException(status_code=404, detail="Voice session not found")

    return CreateVoiceSessionResponse(
        session_id=configured_state.session_id,
        websocket_path=f"/api/voice/ws/{configured_state.session_id}",
        sample_rate_hz=payload.sample_rate_hz,
        tts_output_format=settings.elevenlabs_tts_output_format or "pcm_16000",
        max_input_seconds=max(1, int(settings.voice_max_input_seconds)),
        chat_session_id=chat_session.id,
        launch_mode=payload.launch_mode,
        content_context_attached=context is not None,
    )


@router.get("/health", response_model=VoiceHealthResponse)
async def voice_health(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> VoiceHealthResponse:
    """Return dependency readiness for voice APIs."""

    return VoiceHealthResponse(**build_voice_health_flags())


@router.websocket("/ws/{session_id}")
async def voice_websocket(
    websocket: WebSocket,
    session_id: str,
    db: Annotated[Session, Depends(get_readonly_db_session)],
) -> None:
    """Handle authenticated realtime voice websocket session."""

    prune_voice_sessions()
    user = _authenticate_websocket_user(websocket, db)
    if user is None:
        await websocket.close(code=4401)
        return

    state = get_voice_session(session_id=session_id, user_id=user.id)
    if state is None:
        await websocket.close(code=4404)
        return

    settings = get_settings()
    voice_trace_logging = bool(settings.voice_trace_logging)

    def log_ws_trace(operation: str, context_data: dict[str, Any]) -> None:
        if not voice_trace_logging:
            return
        logger.info(
            "Voice websocket trace",
            extra={
                "component": "voice_ws",
                "operation": operation,
                "item_id": user.id,
                "context_data": {"session_id": session_id, **context_data},
            },
        )

    await websocket.accept()
    logger.info(
        "Voice websocket connected",
        extra={
            "component": "voice_ws",
            "operation": "connect",
            "item_id": user.id,
            "context_data": {
                "session_id": session_id,
                "launch_mode": state.launch_mode,
                "chat_session_id": state.chat_session_id,
                "has_content_context": bool(state.content_context),
            },
        },
    )
    send_lock = asyncio.Lock()
    orchestrator: VoiceConversationOrchestrator | None = None
    orchestrator_started = False
    active_turn_task: asyncio.Task[Any] | None = None
    active_turn_id: str | None = None
    active_turn_index: int | None = None
    active_turn_is_intro = False
    active_stream_epoch = 0
    next_turn_index = 0
    last_completed_turn_index = 0
    turn_index_by_id: dict[str, int] = {}
    turn_epoch_by_id: dict[str, int] = {}
    turn_event_index_by_id: dict[str, int] = {}
    assistant_text_by_turn: dict[str, list[str]] = {}
    pending_assistant_carryover = ""
    suppress_turn_events_for_turn_id: str | None = None
    allow_cancelled_event_for_suppressed_turn = False
    auto_summary_requested = bool(
        state.launch_mode == "dictate_summary"
        and state.summary_narration
        and not state.message_history
    )
    auto_summary_text = (state.summary_narration or "").strip()
    read_only_summary_mode = state.launch_mode == "dictate_summary"
    auto_summary_started = False
    receive_task: asyncio.Task[Any] = asyncio.create_task(websocket.receive_json())

    async def emit(payload: dict[str, Any]) -> bool:
        nonlocal last_completed_turn_index

        event_type = str(payload.get("type", ""))
        event_payload = dict(payload)
        turn_id = event_payload.get("turn_id")
        if isinstance(turn_id, str) and turn_id:
            turn_index = turn_index_by_id.get(turn_id)
            turn_epoch = turn_epoch_by_id.get(turn_id)
            if turn_index is not None:
                event_payload.setdefault("turn_index", turn_index)
            if turn_epoch is not None:
                event_payload.setdefault("stream_epoch", turn_epoch)

            if (
                suppress_turn_events_for_turn_id == turn_id
                and not (
                    event_type == "turn.cancelled"
                    and allow_cancelled_event_for_suppressed_turn
                )
            ):
                log_ws_trace(
                    "turn_event_suppressed",
                    {
                        "turn_id": turn_id,
                        "event_type": event_type,
                    },
                )
                return True

            if event_type in TURN_SCOPED_EVENT_TYPES:
                is_stale = (
                    turn_epoch is None
                    or active_turn_id is None
                    or turn_id != active_turn_id
                    or turn_epoch != active_stream_epoch
                    or (active_turn_index is not None and turn_index != active_turn_index)
                )
                if is_stale:
                    log_ws_trace(
                        "stale_turn_event_dropped",
                        {
                            "turn_id": turn_id,
                            "turn_index": turn_index,
                            "turn_epoch": turn_epoch,
                            "active_turn_id": active_turn_id,
                            "active_turn_index": active_turn_index,
                            "active_stream_epoch": active_stream_epoch,
                            "event_type": event_type,
                        },
                    )
                    return True

                next_event_index = turn_event_index_by_id.get(turn_id, 0)
                event_payload["event_index"] = next_event_index
                turn_event_index_by_id[turn_id] = next_event_index + 1

                if event_type == "assistant.text.delta":
                    text_delta = str(event_payload.get("text") or "")
                    if text_delta:
                        assistant_text_by_turn.setdefault(turn_id, []).append(text_delta)
                elif event_type == "assistant.text.final":
                    final_text = str(event_payload.get("text") or "").strip()
                    if final_text and not assistant_text_by_turn.get(turn_id):
                        assistant_text_by_turn[turn_id] = [final_text]
                elif event_type == "turn.completed" and turn_index is not None:
                    last_completed_turn_index = max(last_completed_turn_index, turn_index)
                    assistant_text_by_turn.pop(turn_id, None)

        return await _send_ws_event(websocket, send_lock, event_payload)

    def activate_turn(turn_id: str, *, is_intro: bool) -> None:
        nonlocal active_stream_epoch, next_turn_index, active_turn_id, active_turn_index
        nonlocal active_turn_is_intro

        active_stream_epoch += 1
        next_turn_index += 1
        turn_index_by_id[turn_id] = next_turn_index
        turn_epoch_by_id[turn_id] = active_stream_epoch
        turn_event_index_by_id[turn_id] = 0
        assistant_text_by_turn[turn_id] = []
        active_turn_id = turn_id
        active_turn_index = next_turn_index
        active_turn_is_intro = is_intro

    def collect_turn_carryover(turn_id: str | None) -> str:
        if not turn_id:
            return ""
        text = "".join(assistant_text_by_turn.pop(turn_id, [])).strip()
        return _truncate_carryover_text(text)

    async def start_auto_summary_turn() -> None:
        nonlocal orchestrator, active_turn_task, auto_summary_started
        nonlocal suppress_turn_events_for_turn_id
        nonlocal allow_cancelled_event_for_suppressed_turn

        if not auto_summary_requested or auto_summary_started:
            return

        if orchestrator is None:
            orchestrator = VoiceConversationOrchestrator(
                session_id=session_id,
                user_id=user.id,
                emit_event=emit,
                chat_session_id=state.chat_session_id,
                launch_mode=state.launch_mode,
                content_context=state.content_context,
            )

        suppress_turn_events_for_turn_id = active_turn_id
        allow_cancelled_event_for_suppressed_turn = False
        await _cancel_task(active_turn_task)
        suppress_turn_events_for_turn_id = None
        allow_cancelled_event_for_suppressed_turn = False
        turn_id = f"turn_{uuid4().hex}"
        activate_turn(turn_id, is_intro=False)
        auto_summary_started = True
        log_ws_trace("auto_summary_started", {"turn_id": turn_id})
        active_turn_task = asyncio.create_task(
            orchestrator.process_scripted_turn(
                turn_id,
                auto_summary_text,
                model="system:summary_narration",
            )
        )

    await emit(
        {
            "type": "session.ready",
            "session_id": session_id,
            "user_id": user.id,
            "chat_session_id": state.chat_session_id,
            "launch_mode": state.launch_mode,
        }
    )

    try:
        while True:
            wait_targets: set[asyncio.Task[Any]] = {receive_task}
            if active_turn_task is not None:
                wait_targets.add(active_turn_task)

            done, _ = await asyncio.wait(wait_targets, return_when=asyncio.FIRST_COMPLETED)

            if receive_task in done:
                try:
                    raw_payload = receive_task.result()
                except WebSocketDisconnect as exc:
                    logger.info(
                        "Voice websocket disconnected by client",
                        extra={
                            "component": "voice_ws",
                            "operation": "disconnect",
                            "item_id": user.id,
                            "context_data": {
                                "session_id": session_id,
                                "code": getattr(exc, "code", None),
                            },
                        },
                    )
                    return
                except Exception:
                    is_open = await emit(
                        {
                            "type": "error",
                            "code": "invalid_payload",
                            "message": "Expected JSON websocket message.",
                            "retryable": True,
                        }
                    )
                    if not is_open:
                        return
                    receive_task = asyncio.create_task(websocket.receive_json())
                    continue

                receive_task = asyncio.create_task(websocket.receive_json())
                try:
                    event = VOICE_CLIENT_EVENT_ADAPTER.validate_python(raw_payload)
                except ValidationError as exc:
                    is_open = await emit(
                        {
                            "type": "error",
                            "code": "validation_error",
                            "message": exc.errors()[0]["msg"] if exc.errors() else "Invalid event.",
                            "retryable": True,
                        }
                    )
                    if not is_open:
                        return
                    continue

                event_type = event.type
                if event_type != "audio.frame":
                    log_ws_trace("client_event", {"event_type": event_type})

                if event_type == "session.start":
                    if event.session_id != session_id:
                        is_open = await emit(
                            {
                                "type": "error",
                                "code": "session_mismatch",
                                "message": "session_id does not match websocket path.",
                                "retryable": False,
                            }
                        )
                        if not is_open:
                            return
                        continue
                    if state.pending_intro:
                        if orchestrator is None:
                            orchestrator = VoiceConversationOrchestrator(
                                session_id=session_id,
                                user_id=user.id,
                                emit_event=emit,
                                chat_session_id=state.chat_session_id,
                                launch_mode=state.launch_mode,
                                content_context=state.content_context,
                            )

                        suppress_turn_events_for_turn_id = active_turn_id
                        allow_cancelled_event_for_suppressed_turn = False
                        await _cancel_task(active_turn_task)
                        suppress_turn_events_for_turn_id = None
                        allow_cancelled_event_for_suppressed_turn = False
                        intro_turn_id = f"turn_{uuid4().hex}"
                        activate_turn(intro_turn_id, is_intro=True)
                        intro_text = build_live_intro_text(
                            launch_mode=state.launch_mode,
                            context_title=state.content_title,
                            is_onboarding=state.is_onboarding_intro,
                        )
                        log_ws_trace(
                            "intro_turn_started",
                            {
                                "turn_id": intro_turn_id,
                                "intro_chars": len(intro_text),
                                "is_onboarding": state.is_onboarding_intro,
                            },
                        )
                        active_turn_task = asyncio.create_task(
                            orchestrator.process_intro_turn(
                                intro_turn_id,
                                intro_text,
                                is_onboarding=state.is_onboarding_intro,
                            )
                        )
                        set_voice_session_intro_pending(
                            session_id=session_id,
                            user_id=user.id,
                            pending_intro=False,
                        )
                    elif auto_summary_requested:
                        await start_auto_summary_turn()
                    elif read_only_summary_mode:
                        is_open = await emit(
                            {
                                "type": "error",
                                "code": "summary_unavailable",
                                "message": "No processed summary is available to narrate yet.",
                                "retryable": False,
                            }
                        )
                        if not is_open:
                            return
                    continue

                if event_type == "session.end":
                    log_ws_trace("session_end_requested", {})
                    await websocket.close(code=1000)
                    return

                if event_type == "intro.ack":
                    completed = False
                    with get_db() as write_db:
                        completed = mark_live_voice_onboarding_complete(write_db, user_id=user.id)
                    set_voice_session_intro_pending(
                        session_id=session_id,
                        user_id=user.id,
                        pending_intro=False,
                    )
                    is_open = await emit(
                        {
                            "type": "intro.acknowledged",
                            "completed": completed,
                        }
                    )
                    if not is_open:
                        return
                    if auto_summary_requested:
                        await start_auto_summary_turn()
                    elif read_only_summary_mode:
                        is_open = await emit(
                            {
                                "type": "error",
                                "code": "summary_unavailable",
                                "message": "No processed summary is available to narrate yet.",
                                "retryable": False,
                            }
                        )
                        if not is_open:
                            return
                    continue

                if event_type == "response.cancel":
                    log_ws_trace("response_cancel_requested", {})
                    has_active_turn = active_turn_task is not None and not active_turn_task.done()
                    turn_id = active_turn_id if has_active_turn else None
                    turn_index = active_turn_index if has_active_turn else None
                    suppress_turn_events_for_turn_id = turn_id if has_active_turn else None
                    allow_cancelled_event_for_suppressed_turn = has_active_turn
                    await _cancel_task(active_turn_task)
                    suppress_turn_events_for_turn_id = None
                    allow_cancelled_event_for_suppressed_turn = False
                    if has_active_turn:
                        pending_assistant_carryover = ""
                        if (
                            turn_id
                            and turn_index is not None
                            and turn_index > last_completed_turn_index
                        ):
                            pending_assistant_carryover = collect_turn_carryover(turn_id)
                    if has_active_turn:
                        active_stream_epoch += 1
                    active_turn_task = None
                    active_turn_id = None
                    active_turn_index = None
                    active_turn_is_intro = False
                    is_open = await emit(
                        {
                            "type": "response.cancelled",
                            "turn_id": turn_id,
                            "reason": "client_request" if has_active_turn else "already_completed",
                            "rollback_turn_index": last_completed_turn_index,
                            "continuation_hint_chars": len(pending_assistant_carryover),
                            "stream_epoch": active_stream_epoch,
                        }
                    )
                    if not is_open:
                        return
                    continue

                if event_type == "audio.frame":
                    if read_only_summary_mode:
                        is_open = await emit(
                            {
                                "type": "error",
                                "code": "read_only_mode",
                                "message": "Microphone input is disabled during summary narration.",
                                "retryable": False,
                            }
                        )
                        if not is_open:
                            return
                        continue

                    if orchestrator is None:
                        orchestrator = VoiceConversationOrchestrator(
                            session_id=session_id,
                            user_id=user.id,
                            emit_event=emit,
                            chat_session_id=state.chat_session_id,
                            launch_mode=state.launch_mode,
                            content_context=state.content_context,
                            sample_rate_hz=event.sample_rate_hz,
                        )
                    if not orchestrator_started:
                        try:
                            await orchestrator.start()
                        except Exception as exc:
                            logger.exception(
                                "Voice websocket failed to start audio stream",
                                extra={
                                    "component": "voice_ws",
                                    "operation": "audio_stream_start",
                                    "item_id": user.id,
                                    "context_data": {"session_id": session_id},
                                },
                            )
                            is_open = await emit(
                                {
                                    "type": "error",
                                    "code": "voice_stream_unavailable",
                                    "message": str(exc),
                                    "retryable": False,
                                }
                            )
                            if not is_open:
                                return
                            continue
                        orchestrator_started = True
                        log_ws_trace(
                            "audio_stream_started",
                            {"sample_rate_hz": event.sample_rate_hz},
                        )

                    try:
                        await orchestrator.handle_audio_frame(event.pcm16_b64)
                    except Exception as exc:
                        logger.exception(
                            "Voice websocket failed to forward audio frame",
                            extra={
                                "component": "voice_ws",
                                "operation": "audio_frame_forward",
                                "item_id": user.id,
                                "context_data": {"session_id": session_id},
                            },
                        )
                        orchestrator_started = False
                        if orchestrator is not None:
                            with suppress(Exception):
                                await orchestrator.close()
                            orchestrator = None
                        is_open = await emit(
                            {
                                "type": "error",
                                "code": "audio_frame_rejected",
                                "message": str(exc),
                                "retryable": True,
                            }
                        )
                        if not is_open:
                            return
                    continue

                if event_type == "audio.commit":
                    if read_only_summary_mode:
                        is_open = await emit(
                            {
                                "type": "error",
                                "code": "read_only_mode",
                                "message": "Microphone input is disabled during summary narration.",
                                "retryable": False,
                            }
                        )
                        if not is_open:
                            return
                        continue

                    if orchestrator is None:
                        is_open = await emit(
                            {
                                "type": "error",
                                "code": "no_audio_buffered",
                                "message": "Send at least one audio.frame before audio.commit.",
                                "retryable": True,
                            }
                        )
                        if not is_open:
                            return
                        continue

                    previous_turn_id = active_turn_id
                    previous_turn_index = active_turn_index
                    suppress_turn_events_for_turn_id = previous_turn_id
                    allow_cancelled_event_for_suppressed_turn = False
                    await _cancel_task(active_turn_task)
                    suppress_turn_events_for_turn_id = None
                    allow_cancelled_event_for_suppressed_turn = False
                    if previous_turn_id and previous_turn_index is not None:
                        pending_assistant_carryover = ""
                        if previous_turn_index > last_completed_turn_index:
                            pending_assistant_carryover = collect_turn_carryover(previous_turn_id)
                    turn_id = f"turn_{uuid4().hex}"
                    activate_turn(turn_id, is_intro=False)
                    if pending_assistant_carryover:
                        orchestrator.set_next_turn_carryover(pending_assistant_carryover)
                        log_ws_trace(
                            "assistant_carryover_attached",
                            {
                                "turn_id": turn_id,
                                "carryover_chars": len(pending_assistant_carryover),
                            },
                        )
                        pending_assistant_carryover = ""
                    log_ws_trace("audio_commit_received", {"turn_id": turn_id})
                    active_turn_task = asyncio.create_task(orchestrator.process_turn(turn_id))
                    continue

            if active_turn_task is not None and active_turn_task in done:
                completed_intro_turn = active_turn_is_intro
                completed_turn_id = active_turn_id
                task_completed_successfully = False
                try:
                    await active_turn_task
                    task_completed_successfully = True
                    log_ws_trace("turn_task_completed", {})
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.exception(
                        "Voice websocket turn task failed",
                        extra={
                            "component": "voice_ws",
                            "operation": "turn_task",
                            "item_id": user.id,
                            "context_data": {"session_id": session_id},
                        },
                    )
                    is_open = await emit(
                        {
                            "type": "error",
                            "code": "turn_task_failed",
                            "message": str(exc),
                            "retryable": True,
                        }
                    )
                    if not is_open:
                        return
                finally:
                    active_turn_task = None
                    active_turn_id = None
                    active_turn_index = None
                    active_turn_is_intro = False
                    if completed_turn_id:
                        assistant_text_by_turn.pop(completed_turn_id, None)

                if (
                    completed_intro_turn
                    and task_completed_successfully
                    and auto_summary_requested
                    and not auto_summary_started
                    and not state.is_onboarding_intro
                ):
                    await start_auto_summary_turn()
    finally:
        logger.info(
            "Voice websocket closing",
            extra={
                "component": "voice_ws",
                "operation": "close",
                "item_id": user.id,
                "context_data": {"session_id": session_id},
            },
        )
        await _cancel_task(receive_task)
        await _cancel_task(active_turn_task)
        if orchestrator is not None:
            with suppress(Exception):
                await orchestrator.close()
