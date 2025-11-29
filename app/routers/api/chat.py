"""Chat session endpoints for deep-dive conversations."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.schema import ChatMessage, ChatSession, Content
from app.models.user import User
from app.routers.api.chat_models import (
    ChatMessageDto,
    ChatMessageRole,
    ChatSessionDetailDto,
    ChatSessionSummaryDto,
    CreateChatSessionResponse,
    SendMessageResponse,
)
from app.routers.api.models import CreateChatSessionRequest, SendChatMessageRequest
from app.services.chat_agent import generate_initial_suggestions, resolve_model, run_chat_turn
from app.services.event_logger import log_event

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _session_to_summary(
    session: ChatSession,
    article_title: str | None = None,
) -> ChatSessionSummaryDto:
    """Convert database ChatSession to API response."""
    return ChatSessionSummaryDto(
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
        is_archived=session.is_archived,
    )


def _extract_messages_for_display(
    db: Session,
    session_id: int,
) -> list[ChatMessageDto]:
    """Load messages from DB and convert to display format.

    Extracts user and assistant text messages from the ModelMessage format
    stored in the database.
    """
    from pydantic_ai.messages import (
        ModelMessagesTypeAdapter,
        ModelRequest,
        ModelResponse,
    )

    messages: list[ChatMessageDto] = []
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
                                ChatMessageDto(
                                    id=msg_counter,
                                    session_id=session_id,
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
                                ChatMessageDto(
                                    id=msg_counter,
                                    session_id=session_id,
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
    response_model=list[ChatSessionSummaryDto],
    summary="List chat sessions",
    description="List all chat sessions for the current user, ordered by most recent activity.",
)
async def list_sessions(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    content_id: Annotated[int | None, Query(description="Filter by content ID")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum sessions to return")] = 50,
) -> list[ChatSessionSummaryDto]:
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
    response_model=ChatSessionDetailDto,
    summary="Get chat session details",
    description="Get a chat session with its message history.",
)
async def get_session(
    session_id: Annotated[int, Path(..., description="Chat session ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatSessionDetailDto:
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

    session_summary = _session_to_summary(session, article_title)
    return ChatSessionDetailDto(session=session_summary, messages=messages)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    summary="Send message",
    description="Send a message in a chat session and receive the assistant reply.",
)
async def send_message(
    session_id: Annotated[int, Path(..., description="Chat session ID", gt=0)],
    request: SendChatMessageRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SendMessageResponse:
    """Send a message and return the assistant response."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this session")

    log_event(
        event_type="chat",
        event_name="message_sent",
        status="started",
        user_id=current_user.id,
        session_id=session_id,
        model=session.llm_model,
    )

    result = await run_chat_turn(db, session, request.message)
    messages = _extract_messages_for_display(db, session_id)
    assistant_message = next(
        (msg for msg in reversed(messages) if msg.role == ChatMessageRole.ASSISTANT),
        None,
    )

    if assistant_message is None:
        raise HTTPException(status_code=500, detail="Assistant response missing")

    log_event(
        event_type="chat",
        event_name="message_sent",
        status="completed",
        user_id=current_user.id,
        session_id=session_id,
        model=session.llm_model,
    )

    return SendMessageResponse(session_id=session.id, assistant_message=assistant_message)


@router.post(
    "/sessions/{session_id}/initial-suggestions",
    response_model=ChatMessageDto,
    summary="Get initial suggestions",
    description=(
        "Generate initial follow-up question suggestions for an article-based session. "
        "Only works for sessions with a content_id (article-based sessions)."
    ),
)
async def get_initial_suggestions(
    session_id: Annotated[int, Path(..., description="Chat session ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatMessageDto:
    """Get initial follow-up question suggestions for an article-based session."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this session")

    if not session.content_id:
        raise HTTPException(
            status_code=400,
            detail="Initial suggestions only available for article-based sessions",
        )

    log_event(
        event_type="chat",
        event_name="initial_suggestions",
        status="started",
        user_id=current_user.id,
        session_id=session_id,
        model=session.llm_model,
    )

    result = await generate_initial_suggestions(db, session)
    if result is None:
        raise HTTPException(status_code=500, detail="Unable to generate suggestions")

    messages = _extract_messages_for_display(db, session_id)
    assistant_message = next(
        (msg for msg in reversed(messages) if msg.role == ChatMessageRole.ASSISTANT),
        None,
    )
    if assistant_message is None:
        raise HTTPException(status_code=500, detail="Assistant response missing")

    log_event(
        event_type="chat",
        event_name="initial_suggestions",
        status="completed",
        user_id=current_user.id,
        session_id=session_id,
        model=session.llm_model,
    )

    return assistant_message
