"""Chat session endpoints for deep-dive conversations."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.domain.converters import content_to_domain
from app.models.schema import (
    ChatMessage,
    ChatSession,
    Content,
    ContentFavorites,
    MessageProcessingStatus,
)
from app.models.user import User
from app.routers.api.chat_models import (
    ChatMessageDto,
    ChatMessageRole,
    ChatSessionDetailDto,
    ChatSessionSummaryDto,
    CreateChatSessionResponse,
    MessageStatusResponse,
    SendMessageResponse,
)
from app.routers.api.chat_models import (
    MessageProcessingStatus as MessageProcessingStatusDto,
)
from app.routers.api.models import (
    CreateChatSessionRequest,
    SendChatMessageRequest,
    UpdateChatSessionRequest,
)
from app.services.chat_agent import (
    create_processing_message,
    generate_initial_suggestions,
    process_message_async,
)
from app.services.event_logger import log_event
from app.services.llm_models import is_deep_research_provider, resolve_model

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _session_to_summary(
    session: ChatSession,
    article_title: str | None = None,
    article_url: str | None = None,
    article_summary: str | None = None,
    article_source: str | None = None,
    has_pending_message: bool = False,
    is_favorite: bool = False,
    has_messages: bool = True,
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
        article_url=article_url,
        article_summary=article_summary,
        article_source=article_source,
        is_archived=session.is_archived,
        has_pending_message=has_pending_message,
        is_favorite=is_favorite,
        has_messages=has_messages,
    )


def _resolve_article_title(content: Content) -> str | None:
    """Resolve a chat-friendly title from content, falling back to display_title."""
    if content.title:
        return content.title

    try:
        domain_content = content_to_domain(content)
        return domain_content.display_title
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Failed to resolve display title for content %s: %s", content.id, exc)
        return None


def _extract_short_summary(content: Content) -> str | None:
    """Extract short summary from content metadata."""
    return content.short_summary


def _extract_messages_for_display(
    db: Session,
    session_id: int,
) -> list[ChatMessageDto]:
    """Load messages from DB and convert to display format.

    Extracts user and assistant text messages from the ModelMessage format
    stored in the database. Includes status for async message processing.
    """
    from pydantic_ai.messages import (
        ModelMessagesTypeAdapter,
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    messages: list[ChatMessageDto] = []
    display_id = 0  # Unique ID for each display message (user/assistant parts)

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
            status = MessageProcessingStatusDto(db_msg.status)

            for model_msg in msg_list:
                if isinstance(model_msg, ModelRequest):
                    # Only show user-authored parts; hide tool-return/system parts
                    for part in model_msg.parts:
                        if isinstance(part, UserPromptPart) and part.content:
                            display_id += 1
                            messages.append(
                                ChatMessageDto(
                                    id=display_id,  # Unique display ID
                                    session_id=session_id,
                                    role=ChatMessageRole.USER,
                                    timestamp=db_msg.created_at,
                                    content=part.content,
                                    status=status,
                                    error=db_msg.error,
                                )
                            )
                elif isinstance(model_msg, ModelResponse):
                    # Only show assistant text parts; hide tool calls/returns
                    for part in model_msg.parts:
                        if isinstance(part, TextPart) and part.content:
                            display_id += 1
                            messages.append(
                                ChatMessageDto(
                                    id=display_id,  # Unique display ID
                                    session_id=session_id,
                                    role=ChatMessageRole.ASSISTANT,
                                    timestamp=db_msg.created_at,
                                    content=part.content,
                                    status=status,
                                    error=db_msg.error,
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

    # Order by most recent activity (coalesce with created_at for new sessions)
    sessions = (
        query.order_by(
            func.coalesce(ChatSession.last_message_at, ChatSession.created_at).desc(),
        )
        .limit(limit)
        .all()
    )

    # Get session IDs that have pending messages (for efficiency)
    session_ids = [s.id for s in sessions]
    pending_session_ids: set[int] = set()
    sessions_with_messages: set[int] = set()

    if session_ids:
        # Check for pending messages
        pending_messages = (
            db.query(ChatMessage.session_id)
            .filter(
                ChatMessage.session_id.in_(session_ids),
                ChatMessage.status == MessageProcessingStatus.PROCESSING.value,
            )
            .distinct()
            .all()
        )
        pending_session_ids = {m.session_id for m in pending_messages}

        # Check which sessions have any messages at all
        sessions_with_any_messages = (
            db.query(ChatMessage.session_id)
            .filter(ChatMessage.session_id.in_(session_ids))
            .distinct()
            .all()
        )
        sessions_with_messages = {m.session_id for m in sessions_with_any_messages}

    # Get favorite content IDs for this user
    content_ids = [s.content_id for s in sessions if s.content_id]
    favorite_content_ids: set[int] = set()
    if content_ids:
        favorites = (
            db.query(ContentFavorites.content_id)
            .filter(
                ContentFavorites.user_id == current_user.id,
                ContentFavorites.content_id.in_(content_ids),
            )
            .all()
        )
        favorite_content_ids = {f.content_id for f in favorites}

    # Build response with article titles, URLs, summaries, and sources
    result = []
    for session in sessions:
        article_title = None
        article_url = None
        article_summary = None
        article_source = None

        if session.content_id:
            content = db.query(Content).filter(Content.id == session.content_id).first()
            if content:
                article_title = _resolve_article_title(content)
                article_url = content.url
                article_summary = _extract_short_summary(content)
                article_source = content.source

        has_pending = session.id in pending_session_ids
        is_favorite = session.content_id in favorite_content_ids if session.content_id else False
        has_messages = session.id in sessions_with_messages

        result.append(
            _session_to_summary(
                session,
                article_title=article_title,
                article_url=article_url,
                article_summary=article_summary,
                article_source=article_source,
                has_pending_message=has_pending,
                is_favorite=is_favorite,
                has_messages=has_messages,
            )
        )

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
    if is_deep_research_provider(request.llm_provider):
        session_type = "deep_research"
    elif request.topic:
        session_type = "topic"
    elif request.content_id:
        session_type = "article_brain"
    else:
        session_type = "ad_hoc"

    # Get article title and URL if content_id provided
    article_title = None
    article_url = None
    if request.content_id:
        content = db.query(Content).filter(Content.id == request.content_id).first()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        article_title = _resolve_article_title(content)
        article_url = content.url

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

    session_summary = _session_to_summary(session, article_title, article_url)
    return CreateChatSessionResponse(session=session_summary)


@router.patch(
    "/sessions/{session_id}",
    response_model=ChatSessionSummaryDto,
    summary="Update chat session",
    description="Update a chat session's settings, such as the LLM provider.",
)
async def update_session(
    session_id: Annotated[int, Path(..., description="Chat session ID", gt=0)],
    request: UpdateChatSessionRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChatSessionSummaryDto:
    """Update a chat session's provider or other settings.

    Allows switching LLM provider mid-conversation while preserving chat history.
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this session")

    # Update provider if specified
    if request.llm_provider is not None:
        provider, model_spec = resolve_model(request.llm_provider, request.llm_model_hint)
        session.llm_provider = provider
        session.llm_model = model_spec
        session.updated_at = datetime.utcnow()

        log_event(
            event_type="chat",
            event_name="session_provider_changed",
            status="completed",
            user_id=current_user.id,
            session_id=session.id,
            model=model_spec,
        )

    db.commit()
    db.refresh(session)

    # Get article title and URL if content_id exists
    article_title = None
    article_url = None
    if session.content_id:
        content = db.query(Content).filter(Content.id == session.content_id).first()
        if content:
            article_title = _resolve_article_title(content)
            article_url = content.url

    return _session_to_summary(session, article_title, article_url)


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

    # Get article title and URL
    article_title = None
    article_url = None
    if session.content_id:
        content = db.query(Content).filter(Content.id == session.content_id).first()
        if content:
            article_title = content.title
            article_url = content.url

    # Load messages
    messages = _extract_messages_for_display(db, session_id)

    session_summary = _session_to_summary(session, article_title, article_url)
    return ChatSessionDetailDto(session=session_summary, messages=messages)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    summary="Send message (async)",
    description=(
        "Send a message in a chat session. Returns immediately with a message_id "
        "to poll for completion. The assistant response is processed in the background."
    ),
)
async def send_message(
    session_id: Annotated[int, Path(..., description="Chat session ID", gt=0)],
    request: SendChatMessageRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SendMessageResponse:
    """Send a message and start async processing.

    Returns immediately with the user message and a message_id.
    Poll GET /messages/{message_id}/status for completion.
    """
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

    # Create the processing message record immediately
    db_message = create_processing_message(db, session_id, request.message)

    trimmed_msg = request.message.replace("\n", " ")[:100]
    if len(request.message) > 100:
        trimmed_msg = f"{trimmed_msg}..."
    logger.info(
        "[Chat:SEND] sid=%s mid=%s user=%s prompt='%s'",
        session_id,
        db_message.id,
        current_user.id,
        trimmed_msg,
    )

    # Start async processing using BackgroundTasks (not asyncio.create_task which can be GC'd)
    # Route to deep research service for deep_research sessions
    if session.session_type == "deep_research":
        from app.services.deep_research import process_deep_research_message

        background_tasks.add_task(
            process_deep_research_message, session_id, db_message.id, request.message
        )
    else:
        background_tasks.add_task(process_message_async, session_id, db_message.id, request.message)

    # Build user message DTO for immediate response
    user_message = ChatMessageDto(
        id=db_message.id,
        session_id=session_id,
        role=ChatMessageRole.USER,
        content=request.message,
        timestamp=db_message.created_at,
        status=MessageProcessingStatusDto.PROCESSING,
    )

    return SendMessageResponse(
        session_id=session.id,
        user_message=user_message,
        message_id=db_message.id,
        status=MessageProcessingStatusDto.PROCESSING,
    )


@router.get(
    "/messages/{message_id}/status",
    response_model=MessageStatusResponse,
    summary="Poll message status",
    description=(
        "Poll for the status of an async message. Returns the assistant response when completed."
    ),
)
async def get_message_status(
    message_id: Annotated[int, Path(..., description="Message ID to poll", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageStatusResponse:
    """Poll for message completion status.

    Returns the current status and assistant message if completed.
    Poll every 500ms-1s until status is 'completed' or 'failed'.
    """
    from pydantic_ai.messages import (
        ModelMessagesTypeAdapter,
        ModelResponse,
        TextPart,
    )

    db_message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()

    if not db_message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify ownership via session
    session = db.query(ChatSession).filter(ChatSession.id == db_message.session_id).first()

    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this message")

    status = MessageProcessingStatusDto(db_message.status)

    # If still processing, return status only
    if status == MessageProcessingStatusDto.PROCESSING:
        return MessageStatusResponse(
            message_id=message_id,
            status=status,
            assistant_message=None,
            error=None,
        )

    # If failed, return status with error
    if status == MessageProcessingStatusDto.FAILED:
        return MessageStatusResponse(
            message_id=message_id,
            status=status,
            assistant_message=None,
            error=db_message.error,
        )

    # If completed, extract assistant message
    try:
        msg_list = ModelMessagesTypeAdapter.validate_json(db_message.message_list)

        # Find the last assistant text response
        assistant_content = None
        for model_msg in reversed(msg_list):
            if isinstance(model_msg, ModelResponse):
                for part in model_msg.parts:
                    if isinstance(part, TextPart) and part.content:
                        assistant_content = part.content
                        break
                if assistant_content:
                    break

        if not assistant_content:
            raise HTTPException(status_code=500, detail="Assistant response missing")

        assistant_message = ChatMessageDto(
            id=message_id,
            session_id=db_message.session_id,
            role=ChatMessageRole.ASSISTANT,
            content=assistant_content,
            timestamp=db_message.created_at,
            status=MessageProcessingStatusDto.COMPLETED,
        )

        return MessageStatusResponse(
            message_id=message_id,
            status=status,
            assistant_message=assistant_message,
            error=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extract assistant message: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse message") from None


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
