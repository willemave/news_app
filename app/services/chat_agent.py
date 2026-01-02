"""Chat agent service using pydantic-ai for deep-dive conversations."""

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

from fastapi.concurrency import run_in_threadpool
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.schema import ChatMessage, ChatSession, Content, MessageProcessingStatus
from app.services.exa_client import exa_search, get_exa_client
from app.services.llm_models import (  # noqa: F401 (re-export for API schemas)
    LLMProvider as ChatModelProvider,
)
from app.services.llm_models import (
    build_pydantic_model,
)

logger = get_logger(__name__)


@dataclass
class ChatDeps:
    """Dependencies passed to the chat agent."""

    session: ChatSession
    content: Content | None
    article_context: str | None  # Pre-built context string from article


# Agent cache - one per model spec
_agents: dict[str, Agent[ChatDeps, str]] = {}


def get_chat_agent(model_spec: str) -> Agent[ChatDeps, str]:
    """Get or create a chat agent for the given model spec.

    Args:
        model_spec: Full pydantic-ai model specification.

    Returns:
        Configured Agent instance.
    """
    if model_spec in _agents:
        return _agents[model_spec]

    system_prompt_text = (
        "You are a deep-dive assistant helping users explore articles, news, and topics. "
        "Be concise but thorough. Help users understand, critique, and apply what they read."
        "\n\n"
        "**CRITICAL - How to Use Web Search:**\n"
        "- Use exa_web_search to research topics, verify claims, and find context\n"
        "- AFTER searching, you MUST synthesize the results into your response:\n"
        "  1. Summarize key findings from the search results\n"
        "  2. Quote or paraphrase specific insights from the sources\n"
        "  3. Include clickable markdown links: [Source Title](url)\n"
        "  4. Compare/contrast what different sources say\n"
        "- If search returns relevant content, NEVER give a generic response - use the content!\n"
        "- Search multiple times if exploring different angles"
        "\n\n"
        "**Response Format:**\n"
        "- Use markdown: **bold** for emphasis, bullet points for lists\n"
        "- Always cite sources with markdown links when referencing search results\n"
        "- Structure responses: brief intro → key findings → sources section\n"
        "- Keep responses focused and scannable"
    )

    # Build model with explicit API key if needed
    model, model_settings = build_pydantic_model(model_spec)

    agent: Agent[ChatDeps, str] = Agent(
        model,
        deps_type=ChatDeps,
        output_type=str,
        system_prompt=system_prompt_text,
        model_settings=model_settings,
    )

    @agent.system_prompt
    def add_article_context(ctx: RunContext[ChatDeps]) -> str:
        """Add article context to the system prompt."""
        parts = []

        if ctx.deps.content:
            parts.append(f"Article Title: {ctx.deps.content.title or 'Untitled'}")
            parts.append(f"Source: {ctx.deps.content.source or 'Unknown'}")
            parts.append(f"URL: {ctx.deps.content.url}")

        if ctx.deps.session.topic:
            parts.append(f"\nFocus Topic: {ctx.deps.session.topic}")

        if ctx.deps.article_context:
            parts.append(f"\nArticle Context:\n{ctx.deps.article_context}")

        if parts:
            return "\n".join(parts)
        return ""

    @agent.tool
    def exa_web_search(
        ctx: RunContext[ChatDeps],
        query: str,
        num_results: int = 8,
        category: str | None = None,
    ) -> str:
        """Search the web using Exa for additional context and research.

        Use this tool proactively when you need more information beyond what's
        in the article, or when the user asks about related topics, recent
        developments, or wants to verify claims.

        Args:
            query: Natural language search query. Be specific and descriptive.
                   Good: "MIT study AI productivity enterprise workers 2024"
                   Bad: "AI productivity"
            num_results: Number of results to return (1-10). Default 8.
            category: Optional filter to focus results. Options:
                      - "news" - Recent news articles
                      - "research paper" - Academic papers
                      - "company" - Company websites and info
                      - "pdf" - PDF documents
                      - "github" - GitHub repos and docs
                      - None - All content types (default)

        Returns:
            Formatted search results with content to synthesize into your response.
            You MUST use this content - summarize findings, quote key insights,
            and include source links in your response.
        """
        session_id = ctx.deps.session.id
        logger.info(
            f"[Tool:exa_web_search] Called | session_id={session_id} "
            f"query='{query[:100]}' num_results={num_results} category={category}"
        )

        # Check if Exa is available
        if get_exa_client() is None:
            logger.warning(f"[Tool:exa_web_search] Exa unavailable | sid={session_id}")
            return "Web search unavailable. Please answer based on your knowledge."

        # Clamp num_results
        num_results = max(1, min(10, num_results))

        # Execute search with enhanced options
        tool_start = perf_counter()
        try:
            results = exa_search(
                query,
                num_results=num_results,
                category=category,
            )
            logger.info(
                f"[Tool:exa_web_search] Success | session_id={session_id} "
                f"results_count={len(results)}"
            )
            for i, r in enumerate(results):
                logger.debug(
                    f"[Tool:exa_web_search] Result {i + 1} | "
                    f"title='{r.title[:50] if r.title else 'N/A'}' url={r.url}"
                )
        except Exception as e:
            logger.error(f"[Tool:exa_web_search] Error | session_id={session_id} error={e}")
            return "Search failed. Please answer based on your knowledge."

        if not results:
            return "No relevant results found. Please answer based on your knowledge."

        duration_ms = (perf_counter() - tool_start) * 1000
        logger.info(
            "[Tool:exa_web_search] Completed | sid=%s ms=%.1f results=%d",
            session_id,
            duration_ms,
            len(results),
        )

        # Format results as structured text for the LLM to synthesize
        output_parts = [
            f"Found {len(results)} relevant sources. "
            "Synthesize these into your response with citations:\n"
        ]

        for i, r in enumerate(results, 1):
            output_parts.append(f"\n---\n**Source {i}: [{r.title}]({r.url})**\n")
            if r.snippet:
                # Truncate very long snippets
                snippet = r.snippet[:1500] if len(r.snippet) > 1500 else r.snippet
                output_parts.append(f"{snippet}\n")

        output_parts.append(
            "\n---\n"
            "INSTRUCTION: Use the above sources to provide a comprehensive response. "
            "Include specific facts, quotes, and [linked citations](url) from the sources."
        )

        return "".join(output_parts)

    _agents[model_spec] = agent
    logger.info(f"Created chat agent for model: {model_spec}")
    return agent


def build_article_context(content: Content) -> str | None:
    """Build context string from article content and metadata.

    Args:
        content: Content database record.

    Returns:
        Formatted context string or None if no content available.
    """
    if not content.content_metadata:
        return None

    metadata = content.content_metadata
    parts = []

    # Add structured summary if available
    summary = metadata.get("summary", {})
    if summary:
        overview = summary.get("overview") or summary.get("hook") or summary.get("takeaway")
        if overview:
            parts.append(f"Overview: {overview}")

        bullet_points = summary.get("bullet_points")
        if not bullet_points:
            bullet_points = summary.get("insights", [])
            points = [
                ins.get("insight", "")
                for ins in bullet_points
                if isinstance(ins, dict) and ins.get("insight")
            ]
        else:
            points = [bp.get("text", "") for bp in bullet_points if isinstance(bp, dict)]
        if points:
            parts.append("Key Points:")
            for point in points[:10]:  # Limit to 10 points
                parts.append(f"  - {point}")

        if topics := summary.get("topics"):
            parts.append(f"Topics: {', '.join(topics[:10])}")

    # Add full content if available (truncated)
    if content_text := metadata.get("content"):
        # Truncate to ~4000 chars to leave room for conversation
        if len(content_text) > 4000:
            content_text = content_text[:4000] + "..."
        parts.append(f"\nFull Content:\n{content_text}")

    return "\n".join(parts) if parts else None


def load_message_history(db: Session, session_id: int) -> list[ModelMessage]:
    """Load all messages for a chat session from the database.

    Args:
        db: Database session.
        session_id: Chat session ID.

    Returns:
        List of ModelMessage objects in chronological order.
    """
    messages: list[ModelMessage] = []

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
            messages.extend(msg_list)
        except Exception as e:
            logger.warning(f"Failed to deserialize message {db_msg.id}: {e}")
            continue

    return messages


def save_messages(
    db: Session,
    session_id: int,
    messages: list[ModelMessage],
    status: MessageProcessingStatus = MessageProcessingStatus.COMPLETED,
) -> ChatMessage:
    """Save new messages to the database.

    Args:
        db: Database session.
        session_id: Chat session ID.
        messages: List of ModelMessage objects to save.
        status: Processing status for the message.

    Returns:
        The created ChatMessage record.
    """
    try:
        # Serialize messages to JSON (empty list if no messages)
        message_json = ModelMessagesTypeAdapter.dump_json(messages).decode("utf-8")

        # Create new ChatMessage record
        db_message = ChatMessage(
            session_id=session_id,
            message_list=message_json,
            created_at=datetime.utcnow(),
            status=status.value,
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        logger.debug(f"Saved {len(messages)} messages for session {session_id}")
        return db_message
    except Exception as e:
        logger.error(f"Failed to save messages: {e}")
        db.rollback()
        raise


def create_processing_message(
    db: Session,
    session_id: int,
    user_prompt: str,
) -> ChatMessage:
    """Create a placeholder message record with processing status.

    This is called immediately when a user sends a message, before LLM processing.
    The user_prompt is stored as a UserPromptPart so it can be displayed immediately.

    Args:
        db: Database session.
        session_id: Chat session ID.
        user_prompt: The user's message text.

    Returns:
        The created ChatMessage record with status=processing.
    """
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    # Create a ModelRequest with just the user prompt
    user_message = ModelRequest(parts=[UserPromptPart(content=user_prompt)])
    return save_messages(db, session_id, [user_message], status=MessageProcessingStatus.PROCESSING)


def update_message_completed(
    db: Session,
    message_id: int,
    messages: list[ModelMessage],
) -> ChatMessage:
    """Update a processing message with the completed result.

    Args:
        db: Database session.
        message_id: ChatMessage ID to update.
        messages: Full list of messages (user + assistant).

    Returns:
        The updated ChatMessage record.
    """
    db_message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not db_message:
        raise ValueError(f"Message {message_id} not found")

    message_json = ModelMessagesTypeAdapter.dump_json(messages).decode("utf-8")
    db_message.message_list = message_json
    db_message.status = MessageProcessingStatus.COMPLETED.value
    db.commit()
    db.refresh(db_message)
    logger.debug(f"Updated message {message_id} to completed")
    return db_message


def update_message_failed(
    db: Session,
    message_id: int,
    error: str,
) -> ChatMessage:
    """Mark a processing message as failed.

    Args:
        db: Database session.
        message_id: ChatMessage ID to update.
        error: Error message describing the failure.

    Returns:
        The updated ChatMessage record.
    """
    db_message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not db_message:
        raise ValueError(f"Message {message_id} not found")

    db_message.status = MessageProcessingStatus.FAILED.value
    db_message.error = error
    db.commit()
    db.refresh(db_message)
    logger.warning(f"Message {message_id} failed: {error}")
    return db_message


@dataclass
class ChatRunResult:
    """Result of a chat turn."""

    output_text: str
    new_messages: list[ModelMessage]
    all_messages: list[ModelMessage]
    tool_calls: list[object]


def _build_chat_deps(db: Session, session: ChatSession) -> ChatDeps:
    """Construct chat dependencies (content + context) for a session."""
    content: Content | None = None
    article_context: str | None = None

    if session.content_id:
        content = db.query(Content).filter(Content.id == session.content_id).first()
        article_context = build_article_context(content) if content else None

    return ChatDeps(session=session, content=content, article_context=article_context)


def _run_agent_sync(
    model_spec: str,
    user_prompt: str,
    deps: ChatDeps,
    history: list[ModelMessage],
):
    """Run the chat agent synchronously in a worker thread."""
    agent = get_chat_agent(model_spec)
    return agent.run_sync(user_prompt, deps=deps, message_history=history)


async def run_chat_turn(
    db: Session,
    session: ChatSession,
    user_prompt: str,
) -> ChatRunResult:
    """Run a chat turn synchronously and persist messages."""
    trimmed_prompt = user_prompt.replace("\n", " ")[:500]
    if len(user_prompt) > 500:
        trimmed_prompt = f"{trimmed_prompt}... [truncated]"
    total_start = perf_counter()
    logger.info(
        "[ChatTurn] started | session_id=%s model=%s prompt_len=%s prompt='%s'",
        session.id,
        session.llm_model,
        len(user_prompt),
        trimmed_prompt,
    )

    deps_start = perf_counter()
    deps = _build_chat_deps(db, session)
    deps_ms = (perf_counter() - deps_start) * 1000

    history_start = perf_counter()
    history = load_message_history(db, session.id)
    history_ms = (perf_counter() - history_start) * 1000

    try:
        agent_start = perf_counter()
        result = await run_in_threadpool(
            _run_agent_sync, session.llm_model, user_prompt, deps, history
        )
        agent_ms = (perf_counter() - agent_start) * 1000
        new_messages = result.new_messages()
        save_messages(db, session.id, new_messages)

        session.last_message_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        db.commit()

        total_ms = (perf_counter() - total_start) * 1000
        tool_calls = getattr(result, "tool_calls", []) or []
        tool_names = [
            getattr(tc, "name", None)
            or getattr(tc, "function_name", None)
            or getattr(tc, "tool_name", None)
            for tc in tool_calls
        ]
        logger.info(
            "[ChatTurn] sid=%s model=%s total=%.1f deps=%.1f hist=%.1f agent=%.1f tools=%s",
            session.id,
            session.llm_model,
            total_ms,
            deps_ms,
            history_ms,
            agent_ms,
            tool_names,
        )

        return ChatRunResult(
            output_text=result.output,
            new_messages=new_messages,
            all_messages=result.all_messages,
            tool_calls=getattr(result, "tool_calls", []),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Chat error for session %s: %s", session.id, exc)
        db.rollback()
        raise


async def process_message_async(
    session_id: int,
    message_id: int,
    user_prompt: str,
) -> None:
    """Process a chat message asynchronously in the background.

    This function runs independently after the endpoint returns.
    It gets a fresh DB session, processes the LLM call, and updates
    the message record with the result.

    Args:
        session_id: Chat session ID.
        message_id: ChatMessage ID to update on completion.
        user_prompt: The user's message text.
    """
    from app.core.db import get_session_factory
    from app.services.event_logger import log_event

    total_start = perf_counter()
    trimmed_prompt = user_prompt.replace("\n", " ")[:100]
    if len(user_prompt) > 100:
        trimmed_prompt = f"{trimmed_prompt}..."

    logger.info(
        "[AsyncChat:START] sid=%s mid=%s prompt='%s'",
        session_id,
        message_id,
        trimmed_prompt,
    )

    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            logger.error("[AsyncChat:ERROR] Session %s not found", session_id)
            return

        logger.info(
            "[AsyncChat:SESSION] sid=%s model=%s content_id=%s topic=%s",
            session_id,
            session.llm_model,
            session.content_id,
            session.topic,
        )

        # Build dependencies
        deps_start = perf_counter()
        deps = _build_chat_deps(db, session)
        deps_ms = (perf_counter() - deps_start) * 1000
        context_len = len(deps.article_context) if deps.article_context else 0
        logger.info(
            "[AsyncChat:DEPS] sid=%s deps_ms=%.1f context_chars=%d has_content=%s",
            session_id,
            deps_ms,
            context_len,
            deps.content is not None,
        )

        # Load history (excluding the processing message we just created)
        history_start = perf_counter()
        history = load_message_history(db, session.id)
        history_ms = (perf_counter() - history_start) * 1000
        logger.info(
            "[AsyncChat:HISTORY] sid=%s history_ms=%.1f message_count=%d",
            session_id,
            history_ms,
            len(history),
        )

        # Run the agent
        logger.info(
            "[AsyncChat:LLM_START] sid=%s model=%s history_len=%d",
            session_id,
            session.llm_model,
            len(history),
        )
        agent_start = perf_counter()
        result = await run_in_threadpool(
            _run_agent_sync, session.llm_model, user_prompt, deps, history
        )
        agent_ms = (perf_counter() - agent_start) * 1000

        # Extract tool calls info
        tool_calls = getattr(result, "tool_calls", []) or []
        tool_names = [
            getattr(tc, "name", None)
            or getattr(tc, "function_name", None)
            or getattr(tc, "tool_name", None)
            for tc in tool_calls
        ]
        output_len = len(result.output) if result.output else 0
        logger.info(
            "[AsyncChat:LLM_DONE] sid=%s agent_ms=%.1f output_chars=%d tools=%s",
            session_id,
            agent_ms,
            output_len,
            tool_names if tool_names else "none",
        )

        # Update the message with the complete result
        save_start = perf_counter()
        new_messages = result.new_messages()
        update_message_completed(db, message_id, new_messages)
        save_ms = (perf_counter() - save_start) * 1000

        # Update session timestamps
        session.last_message_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        db.commit()

        total_ms = (perf_counter() - total_start) * 1000
        logger.info(
            "[AsyncChat:DONE] sid=%s mid=%s total=%.0f deps=%.0f hist=%.0f llm=%.0f save=%.0f ms",
            session_id,
            message_id,
            total_ms,
            deps_ms,
            history_ms,
            agent_ms,
            save_ms,
        )

        log_event(
            event_type="chat",
            event_name="message_sent",
            status="completed",
            user_id=session.user_id,
            session_id=session_id,
            model=session.llm_model,
        )

    except Exception as exc:
        total_ms = (perf_counter() - total_start) * 1000
        logger.error(
            "[AsyncChat:FAILED] sid=%s mid=%s total_ms=%.1f error=%s",
            session_id,
            message_id,
            total_ms,
            exc,
        )
        try:
            update_message_failed(db, message_id, str(exc))
        except Exception as update_exc:
            logger.error("[AsyncChat:UPDATE_FAILED] mid=%s error=%s", message_id, update_exc)
    finally:
        db.close()


INITIAL_QUESTIONS_PROMPT = """
You are starting a new conversation about the article described in your context.

Write a short welcome message (1-2 sentences) that:
- Briefly states what help you can provide (explain, critique, brainstorm, apply ideas).
- Sounds friendly and concise.

After the welcome, propose 2-4 concrete directions the user could take next:
- Use bullet points.
- Mix question types: clarification, implications, counterpoints, practical applications.
- Make them specific to this article, not generic.

Do not mention tools, system prompts, or implementation details. Just write what the user sees.
""".strip()


async def generate_initial_suggestions(
    db: Session,
    session: ChatSession,
) -> ChatRunResult | None:
    """Generate the initial assistant message for article-based sessions."""
    total_start = perf_counter()
    logger.info(
        "[InitialSuggestions] started | session_id=%s content_id=%s model=%s",
        session.id,
        session.content_id,
        session.llm_model,
    )

    if not session.content_id:
        logger.warning("[InitialSuggestions] No content_id | session_id=%s", session.id)
        return None

    deps = _build_chat_deps(db, session)

    try:
        agent_start = perf_counter()
        result = await run_in_threadpool(
            _run_agent_sync,
            session.llm_model,
            INITIAL_QUESTIONS_PROMPT,
            deps,
            [],
        )
        agent_ms = (perf_counter() - agent_start) * 1000
        new_messages = result.new_messages()
        save_start = perf_counter()
        save_messages(db, session.id, new_messages)
        save_ms = (perf_counter() - save_start) * 1000

        session.last_message_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        db.commit()

        total_ms = (perf_counter() - total_start) * 1000
        tool_calls = getattr(result, "tool_calls", []) or []
        tool_names = [
            getattr(tc, "name", None)
            or getattr(tc, "function_name", None)
            or getattr(tc, "tool_name", None)
            for tc in tool_calls
        ]
        logger.info(
            "[InitialSuggestions] sid=%s total=%.1f agent=%.1f save=%.1f tools=%s",
            session.id,
            total_ms,
            agent_ms,
            save_ms,
            tool_names,
        )

        return ChatRunResult(
            output_text=result.output,
            new_messages=new_messages,
            all_messages=result.all_messages,
            tool_calls=getattr(result, "tool_calls", []),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[InitialSuggestions] Error | session_id=%s error=%s", session.id, exc)
        db.rollback()
        raise
