"""Chat agent service using pydantic-ai for deep-dive conversations."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.schema import ChatMessage, ChatSession, Content
from app.services.exa_client import exa_search, get_exa_client

logger = get_logger(__name__)


class ChatModelProvider(str, Enum):
    """Supported LLM providers for chat."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


# Default model specifications per provider
PROVIDER_DEFAULTS: dict[ChatModelProvider, str] = {
    ChatModelProvider.OPENAI: "openai:gpt-5.1",
    ChatModelProvider.ANTHROPIC: "claude-sonnet-4-5-20250929",
    ChatModelProvider.GOOGLE: "google-gla:gemini-3-pro-preview",
}

DEFAULT_MODEL = "openai:gpt-5.1"


def resolve_model(
    provider: ChatModelProvider | None,
    model_hint: str | None,
) -> tuple[str, str]:
    """Resolve provider and model hint to a pydantic-ai model string.

    Args:
        provider: LLM provider enum or None for default.
        model_hint: Optional specific model name or full spec.

    Returns:
        Tuple of (provider_name, full_model_spec).
    """
    # If model_hint looks like a full spec (contains colon), use it directly
    if model_hint and ":" in model_hint:
        # Extract provider from the spec
        provider_name = model_hint.split(":")[0]
        return provider_name, model_hint

    # Use provider default or global default
    if provider is None:
        provider = ChatModelProvider.OPENAI

    if model_hint:
        # Combine provider with model hint
        return provider.value, f"{provider.value}:{model_hint}"
    else:
        # Use provider's default model
        return provider.value, PROVIDER_DEFAULTS.get(provider, DEFAULT_MODEL)


@dataclass
class ChatDeps:
    """Dependencies passed to the chat agent."""

    session: ChatSession
    content: Content | None
    article_context: str | None  # Pre-built context string from article


class ExaSearchResultModel(BaseModel):
    """Exa search result for agent tool return."""

    title: str
    url: str
    snippet: str | None = None


# Agent cache - one per model spec
_agents: dict[str, Agent[ChatDeps, str]] = {}


def _build_model(model_spec: str) -> str | Model:
    """Build a model instance with explicit API keys from settings.

    Args:
        model_spec: Full pydantic-ai model specification (e.g., "google-gla:gemini-2.0-flash").

    Returns:
        Either the original model_spec string (for models that auto-detect keys)
        or a configured Model instance with explicit API key.
    """
    settings = get_settings()

    # Handle Google models - they need explicit API key from settings
    if model_spec.startswith("google-gla:"):
        model_name = model_spec.split(":", 1)[1]
        if not settings.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY not configured in settings. "
                "Set it in .env or environment variables."
            )
        return GoogleModel(model_name, provider=GoogleProvider(api_key=settings.google_api_key))

    # Handle Anthropic models (claude-* format)
    if model_spec.startswith("claude-"):
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured in settings. "
                "Set it in .env or environment variables."
            )
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)
        return AnthropicModel(model_spec, provider=provider)

    # Other providers (OpenAI) auto-detect from env vars
    return model_spec


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
        "**IMPORTANT - Use Web Search Proactively:**\n"
        "- Use the exa_web_search tool to research topics, verify claims, and find context\n"
        "- Search for background info, author credentials, developments, or counterarguments\n"
        "- Don't hesitate to search multiple times if exploring different angles\n"
        "- Synthesize search results naturally into your responses"
        "\n\n"
        "**Response Format:**\n"
        "- Use markdown formatting: **bold** for emphasis, bullet points for lists\n"
        "- Cite sources with titles or URLs when referencing external information\n"
        "- Keep responses focused and scannable"
    )

    # Build model with explicit API key if needed
    model = _build_model(model_spec)

    agent: Agent[ChatDeps, str] = Agent(
        model,
        deps_type=ChatDeps,
        output_type=str,
        system_prompt=system_prompt_text,
    )

    @agent.system_prompt
    async def add_article_context(ctx: RunContext[ChatDeps]) -> str:
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
    async def exa_web_search(
        ctx: RunContext[ChatDeps],
        query: str,
        num_results: int = 5,
    ) -> list[ExaSearchResultModel]:
        """Search the web using Exa for additional context.

        Use this tool when you need more information beyond what's in the article,
        or when the user asks about related topics, recent developments, or wants
        to verify claims.

        Args:
            query: Search query string describing what you're looking for.
            num_results: Number of results to return (1-10).

        Returns:
            List of search results with title, URL, and snippet.
        """
        session_id = ctx.deps.session.id
        logger.info(
            f"[Tool:exa_web_search] Called | session_id={session_id} "
            f"query='{query[:100]}' num_results={num_results}"
        )

        # Check if Exa is available
        if get_exa_client() is None:
            logger.warning(f"[Tool:exa_web_search] Exa unavailable | sid={session_id}")
            return []

        # Clamp num_results
        num_results = max(1, min(10, num_results))

        # Execute search
        try:
            results = exa_search(query, num_results=num_results)
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
            return []

        return [
            ExaSearchResultModel(
                title=r.title,
                url=r.url,
                snippet=r.snippet,
            )
            for r in results
        ]

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
        if overview := summary.get("overview"):
            parts.append(f"Overview: {overview}")

        if bullet_points := summary.get("bullet_points"):
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
) -> None:
    """Save new messages to the database.

    Args:
        db: Database session.
        session_id: Chat session ID.
        messages: List of ModelMessage objects to save.
    """
    if not messages:
        return

    try:
        # Serialize messages to JSON
        message_json = ModelMessagesTypeAdapter.dump_json(messages).decode("utf-8")

        # Create new ChatMessage record
        db_message = ChatMessage(
            session_id=session_id,
            message_list=message_json,
            created_at=datetime.utcnow(),
        )
        db.add(db_message)
        db.commit()
        logger.debug(f"Saved {len(messages)} messages for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to save messages: {e}")
        db.rollback()
        raise


async def run_chat_stream(
    db: Session,
    session: ChatSession,
    user_prompt: str,
) -> AsyncIterator[str]:
    """Run a chat turn with streaming output.

    Args:
        db: Database session.
        session: Chat session record.
        user_prompt: User's message.

    Yields:
        Partial text chunks as they're generated.

    Note:
        This function updates session.last_message_at and persists new messages.
    """
    logger.info(
        f"[Stream] run_chat_stream started | session_id={session.id} "
        f"model={session.llm_model} prompt_len={len(user_prompt)}"
    )

    # Load associated content if any
    content: Content | None = None
    if session.content_id:
        content = db.query(Content).filter(Content.id == session.content_id).first()
        logger.debug(f"[Stream] Content loaded | sid={session.id} cid={session.content_id}")

    # Build article context
    article_context = build_article_context(content) if content else None
    if article_context:
        logger.debug(f"[Stream] Context built | sid={session.id} len={len(article_context)}")

    # Build dependencies
    deps = ChatDeps(
        session=session,
        content=content,
        article_context=article_context,
    )

    # Load message history
    history = load_message_history(db, session.id)
    logger.info(f"[Stream] Loaded history | session_id={session.id} history_count={len(history)}")

    # Get agent for this session's model
    agent = get_chat_agent(session.llm_model)

    # Run with streaming
    collected_text = ""
    chunk_count = 0
    try:
        logger.info(f"[Stream] Starting agent stream | session_id={session.id}")
        async with agent.run_stream(
            user_prompt,
            deps=deps,
            message_history=history,
        ) as result:
            # Stream text chunks
            async for text in result.stream_text(debounce_by=0.01):
                # Yield only the new part
                new_text = text[len(collected_text) :]
                if new_text:
                    chunk_count += 1
                    yield new_text
                    collected_text = text
                    if chunk_count % 50 == 0:  # Log progress every 50 chunks
                        logger.debug(
                            f"[Stream] Progress | session_id={session.id} "
                            f"chunks={chunk_count} total_len={len(collected_text)}"
                        )

        logger.info(
            f"[Stream] Stream completed | session_id={session.id} "
            f"total_chunks={chunk_count} final_len={len(collected_text)}"
        )

        # After completion, save new messages
        new_messages = result.new_messages()
        save_messages(db, session.id, new_messages)
        logger.debug(f"[Stream] Saved | sid={session.id} msgs={len(new_messages)}")

        # Update session timestamps
        session.last_message_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"[Stream] Session updated | session_id={session.id}")

    except Exception as e:
        logger.error(f"Chat stream error for session {session.id}: {e}")
        db.rollback()
        raise


async def run_chat_sync(
    db: Session,
    session: ChatSession,
    user_prompt: str,
) -> str:
    """Run a chat turn synchronously (non-streaming).

    Args:
        db: Database session.
        session: Chat session record.
        user_prompt: User's message.

    Returns:
        Complete assistant response.
    """
    # Load associated content if any
    content: Content | None = None
    if session.content_id:
        content = db.query(Content).filter(Content.id == session.content_id).first()

    # Build article context
    article_context = build_article_context(content) if content else None

    # Build dependencies
    deps = ChatDeps(
        session=session,
        content=content,
        article_context=article_context,
    )

    # Load message history
    history = load_message_history(db, session.id)

    # Get agent for this session's model
    agent = get_chat_agent(session.llm_model)

    # Run synchronously
    try:
        result = await agent.run(
            user_prompt,
            deps=deps,
            message_history=history,
        )

        # Save new messages
        new_messages = result.new_messages()
        save_messages(db, session.id, new_messages)

        # Update session timestamps
        session.last_message_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        db.commit()

        return result.output

    except Exception as e:
        logger.error(f"Chat error for session {session.id}: {e}")
        db.rollback()
        raise


# Prompt for generating initial follow-up question suggestions
INITIAL_QUESTIONS_PROMPT = """Based on this article, suggest 3-5 thought-provoking follow-up \
questions the reader might want to explore.

Format your response as a brief welcome message followed by the questions. Use markdown:
- Start with a short sentence like "Here are some directions we could explore:"
- List each question as a bullet point
- Questions should be specific to the article content, not generic
- Mix different types: clarifying, implications, counterarguments, practical applications

Keep it concise - this is meant to spark conversation, not overwhelm."""


async def generate_initial_suggestions(
    db: Session,
    session: ChatSession,
) -> AsyncIterator[str]:
    """Generate initial follow-up question suggestions for an article-based session.

    This is called when a new session is created with a content_id to provide
    immediate value and guide the user on what they can explore.

    Args:
        db: Database session.
        session: Chat session record (must have content_id).

    Yields:
        Partial text chunks as they're generated.
    """
    logger.info(
        f"[InitialSuggestions] Started | session_id={session.id} "
        f"content_id={session.content_id} model={session.llm_model}"
    )

    if not session.content_id:
        logger.warning(f"[InitialSuggestions] No content_id | session_id={session.id}")
        return

    # Load associated content
    content: Content | None = db.query(Content).filter(Content.id == session.content_id).first()
    if not content:
        logger.warning(f"[InitialSuggestions] Content not found | sid={session.id}")
        return

    title_preview = content.title[:50] if content.title else "N/A"
    logger.debug(f"[InitialSuggestions] Content loaded | sid={session.id} title='{title_preview}'")

    # Build article context
    article_context = build_article_context(content)
    if article_context:
        ctx_len = len(article_context)
        logger.debug(f"[InitialSuggestions] Context built | sid={session.id} len={ctx_len}")

    # Build dependencies
    deps = ChatDeps(
        session=session,
        content=content,
        article_context=article_context,
    )

    # Get agent for this session's model
    agent = get_chat_agent(session.llm_model)

    # Run with streaming - use the initial questions prompt
    collected_text = ""
    chunk_count = 0
    try:
        logger.info(f"[InitialSuggestions] Starting agent stream | session_id={session.id}")
        async with agent.run_stream(
            INITIAL_QUESTIONS_PROMPT,
            deps=deps,
            message_history=[],  # Empty history for initial message
        ) as result:
            # Stream text chunks
            async for text in result.stream_text(debounce_by=0.01):
                new_text = text[len(collected_text) :]
                if new_text:
                    chunk_count += 1
                    yield new_text
                    collected_text = text
                    if chunk_count % 50 == 0:
                        logger.debug(
                            f"[InitialSuggestions] Progress | session_id={session.id} "
                            f"chunks={chunk_count} total_len={len(collected_text)}"
                        )

        logger.info(
            f"[InitialSuggestions] Stream completed | session_id={session.id} "
            f"total_chunks={chunk_count} final_len={len(collected_text)}"
        )

        # After completion, save new messages
        new_messages = result.new_messages()
        save_messages(db, session.id, new_messages)
        logger.debug(f"[InitialSuggestions] Saved | sid={session.id} msgs={len(new_messages)}")

        # Update session timestamps
        session.last_message_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"[InitialSuggestions] Completed | session_id={session.id}")

    except Exception as e:
        logger.error(f"[InitialSuggestions] Error | session_id={session.id} error={e}")
        db.rollback()
        raise
