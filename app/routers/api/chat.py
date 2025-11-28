"""Chat session endpoints for deep-dive conversations."""

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.schema import ChatMessage, ChatSession, Content
from app.models.user import User
from app.routers.api.models import (
    ChatMessageResponse,
    ChatMessageRole,
    ChatSessionDetailResponse,
    ChatSessionSummaryResponse,
    CreateChatSessionRequest,
    CreateChatSessionResponse,
    SendChatMessageRequest,
)
from app.services.chat_agent import (
    resolve_model,
    run_chat_stream,
)
from app.services.event_logger import log_event

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _session_to_summary(
    session: ChatSession,
    article_title: str | None = None,
) -> ChatSessionSummaryResponse:
    """Convert database ChatSession to API response."""
    return ChatSessionSummaryResponse(
        id=session.id,
        content_id=session.content_id,
        title=session.title,
        session_type=session.session_type,
        topic=session.topic,
        llm_provider=session.llm_provider,
        llm_model=session.llm_model,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_message_at=session.last_message_at,
        article_title=article_title,
    )


def _extract_messages_for_display(
    db: Session,
    session_id: int,
) -> list[ChatMessageResponse]:
    """Load messages from DB and convert to display format.

    Extracts user and assistant text messages from the ModelMessage format
    stored in the database.
    """
    from pydantic_ai.messages import (
        ModelMessagesTypeAdapter,
        ModelRequest,
        ModelResponse,
    )

    messages: list[ChatMessageResponse] = []
    msg_counter = 0

    # Query chat_messages ordered by created_at
    db_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )

    for db_msg in db_messages:
        try:
            # Deserialize JSON to list of ModelMessage
            msg_list = ModelMessagesTypeAdapter.validate_json(db_msg.message_list)

            for model_msg in msg_list:
                if isinstance(model_msg, ModelRequest):
                    # Extract user messages from request parts
                    for part in model_msg.parts:
                        if hasattr(part, "content") and isinstance(part.content, str):
                            # UserPromptPart or similar
                            msg_counter += 1
                            messages.append(
                                ChatMessageResponse(
                                    id=msg_counter,
                                    role=ChatMessageRole.USER,
                                    timestamp=db_msg.created_at,
                                    content=part.content,
                                )
                            )
                elif isinstance(model_msg, ModelResponse):
                    # Extract assistant messages from response parts
                    for part in model_msg.parts:
                        if hasattr(part, "content") and isinstance(part.content, str):
                            # TextPart
                            msg_counter += 1
                            messages.append(
                                ChatMessageResponse(
                                    id=msg_counter,
                                    role=ChatMessageRole.ASSISTANT,
                                    timestamp=db_msg.created_at,
                                    content=part.content,
                                )
                            )
        except Exception as e:
            logger.warning(f"Failed to deserialize message {db_msg.id}: {e}")
            continue

    return messages


@router.get(
    "/sessions",
    response_model=list[ChatSessionSummaryResponse],
    summary="List chat sessions",
    description="List all chat sessions for the current user, ordered by most recent activity.",
)
async def list_sessions(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    content_id: Annotated[int | None, Query(description="Filter by content ID")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum sessions to return")] = 50,
) -> list[ChatSessionSummaryResponse]:
    """List chat sessions for the current user.

    Returns sessions ordered by last_message_at (most recent first),
    falling back to created_at for sessions without messages.
    """
    query = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id,
        ChatSession.is_archived == False,  # noqa: E712
    )

    if content_id is not None:
        query = query.filter(ChatSession.content_id == content_id)

    # Order by most recent activity
    sessions = (
        query.order_by(
            ChatSession.last_message_at.desc().nullslast(),
            ChatSession.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    # Build response with article titles
    result = []
    for session in sessions:
        article_title = None
        if session.content_id:
            content = db.query(Content).filter(Content.id == session.content_id).first()
            if content:
                article_title = content.title

        result.append(_session_to_summary(session, article_title))

    return result


@router.post(
    "/sessions",
    response_model=CreateChatSessionResponse,
    summary="Create chat session",
    description="Create a new chat session, optionally associated with an article.",
)
async def create_session(
    request: CreateChatSessionRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CreateChatSessionResponse:
    """Create a new chat session.

    If content_id is provided, the session will be associated with that article
    and the article's context will be available to the chat agent.
    """
    # Resolve model
    provider, model_spec = resolve_model(request.llm_provider, request.llm_model_hint)

    # Determine session type
    if request.topic:
        session_type = "topic"
    elif request.content_id:
        session_type = "article_brain"
    else:
        session_type = "ad_hoc"

    # Get article title if content_id provided
    article_title = None
    if request.content_id:
        content = db.query(Content).filter(Content.id == request.content_id).first()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        article_title = content.title

    # Build session title
    if request.topic and article_title:
        title = f"{article_title} - {request.topic}"
    elif article_title:
        title = article_title
    elif request.topic:
        title = request.topic
    elif request.initial_message:
        title = request.initial_message[:80]
    else:
        title = "New Chat"

    # Create session
    session = ChatSession(
        user_id=current_user.id,
        content_id=request.content_id,
        title=title,
        session_type=session_type,
        topic=request.topic,
        llm_model=model_spec,
        llm_provider=provider,
        created_at=datetime.utcnow(),
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    # Log event
    log_event(
        event_type="chat",
        event_name="session_created",
        status="completed",
        user_id=current_user.id,
        session_id=session.id,
        content_id=request.content_id,
        model=model_spec,
    )

    return CreateChatSessionResponse(session=_session_to_summary(session, article_title))


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    summary="Get chat session details",
    description="Get a chat session with its message history.",
)
async def get_session(
    session_id: Annotated[int, Path(..., description="Chat session ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatSessionDetailResponse:
    """Get chat session details with message history."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this session")

    # Get article title
    article_title = None
    if session.content_id:
        content = db.query(Content).filter(Content.id == session.content_id).first()
        if content:
            article_title = content.title

    # Load messages
    messages = _extract_messages_for_display(db, session_id)

    return ChatSessionDetailResponse(
        session=_session_to_summary(session, article_title),
        messages=messages,
    )


@router.post(
    "/sessions/{session_id}/messages",
    summary="Send message (streaming)",
    description=(
        "Send a message in a chat session and receive streaming response. "
        "Returns newline-delimited JSON (NDJSON) with ChatMessageResponse objects."
    ),
    responses={
        200: {
            "description": "Streaming response with NDJSON",
            "content": {"application/x-ndjson": {}},
        },
        404: {"description": "Session not found"},
        403: {"description": "Not authorized"},
    },
)
async def send_message(
    session_id: Annotated[int, Path(..., description="Chat session ID", gt=0)],
    request: SendChatMessageRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """Send a message and stream the response.

    Returns newline-delimited JSON (NDJSON) where each line is a
    ChatMessageResponse object. The first message is the user's input,
    followed by streaming assistant response chunks.
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this session")

    async def generate():
        msg_id = 0

        # First, yield the user message
        msg_id += 1
        user_msg = ChatMessageResponse(
            id=msg_id,
            role=ChatMessageRole.USER,
            timestamp=datetime.utcnow(),
            content=request.message,
        )
        yield json.dumps(user_msg.model_dump(mode="json")) + "\n"

        # Then stream the assistant response
        msg_id += 1
        accumulated_text = ""
        timestamp = datetime.utcnow()

        try:
            async for chunk in run_chat_stream(db, session, request.message):
                accumulated_text += chunk
                # Yield partial response
                partial_msg = ChatMessageResponse(
                    id=msg_id,
                    role=ChatMessageRole.ASSISTANT,
                    timestamp=timestamp,
                    content=accumulated_text,
                )
                yield json.dumps(partial_msg.model_dump(mode="json")) + "\n"

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            # Yield error as final message
            error_msg = ChatMessageResponse(
                id=msg_id,
                role=ChatMessageRole.ASSISTANT,
                timestamp=datetime.utcnow(),
                content=f"Error: {str(e)}",
            )
            yield json.dumps(error_msg.model_dump(mode="json")) + "\n"

    # Log event
    log_event(
        event_type="chat",
        event_name="message_sent",
        status="started",
        user_id=current_user.id,
        session_id=session_id,
        model=session.llm_model,
    )

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
    )
