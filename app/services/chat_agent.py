"""Chat agent service using pydantic-ai for deep-dive conversations."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
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


# Provider prefixes and default model specifications (keyed by canonical provider name)
PROVIDER_PREFIXES: dict[str, str] = {
    ChatModelProvider.OPENAI.value: "openai",
    ChatModelProvider.ANTHROPIC.value: "anthropic",
    ChatModelProvider.GOOGLE.value: "google-gla",
}

PROVIDER_DEFAULTS: dict[str, str] = {
    ChatModelProvider.OPENAI.value: "openai:gpt-5.1",
    ChatModelProvider.ANTHROPIC.value: "anthropic:claude-sonnet-4-5-20250929",
    ChatModelProvider.GOOGLE.value: "google-gla:gemini-3-pro-preview",
}

DEFAULT_PROVIDER = ChatModelProvider.GOOGLE.value
DEFAULT_MODEL = PROVIDER_DEFAULTS[DEFAULT_PROVIDER]
PREFIX_TO_PROVIDER: dict[str, str] = {
    prefix: provider for provider, prefix in PROVIDER_PREFIXES.items()
}


def resolve_model(
    provider: ChatModelProvider | str | None,
    model_hint: str | None,
) -> tuple[str, str]:
    """Resolve provider and model hint to a pydantic-ai model string.

    Args:
        provider: LLM provider enum/string or None for default.
        model_hint: Optional specific model name or full spec.

    Returns:
        Tuple of (canonical_provider_name, full_model_spec).
    """

    def _normalize_provider_name(provider_value: ChatModelProvider | str | None) -> str:
        """Convert provider input (enum/str) to canonical provider name."""
        if provider_value is None:
            return DEFAULT_PROVIDER

        raw = provider_value.value if isinstance(provider_value, Enum) else str(provider_value)
        return PREFIX_TO_PROVIDER.get(raw, raw)

    # Normalize provider to canonical string (openai/anthropic/google)
    provider_name = _normalize_provider_name(provider)

    # If model_hint looks like a full spec (contains colon), use it directly
    if model_hint and ":" in model_hint:
        provider_prefix = model_hint.split(":", 1)[0]
        hinted_provider = PREFIX_TO_PROVIDER.get(provider_prefix, provider_prefix)
        canonical_provider = (
            hinted_provider if hinted_provider in PROVIDER_DEFAULTS else provider_name
        )
        return canonical_provider, model_hint

    # Use provider default or global default
    model_prefix = PROVIDER_PREFIXES.get(provider_name, provider_name)

    if model_hint:
        # Combine provider prefix with model hint
        return provider_name, f"{model_prefix}:{model_hint}"

    # Use provider's default model
    return provider_name, PROVIDER_DEFAULTS.get(provider_name, DEFAULT_MODEL)


@dataclass
class ChatDeps:
    """Dependencies passed to the chat agent."""

    session: ChatSession
    content: Content | None
    article_context: str | None  # Pre-built context string from article


# Agent cache - one per model spec
_agents: dict[str, Agent[ChatDeps, str]] = {}


def _build_model(model_spec: str) -> tuple[str | Model, GoogleModelSettings | None]:
    """Build a model instance with explicit API keys from settings.

    Args:
        model_spec: Full pydantic-ai model specification (e.g., "google-gla:gemini-2.0-flash").

    Returns:
        Tuple of (model, model_settings) where model is either the original model_spec string
        (for models that auto-detect keys) or a configured Model instance with explicit API key.
        model_settings is GoogleModelSettings for Google models (to hide thinking traces),
        None otherwise.
    """
    settings = get_settings()

    provider_prefix = None
    model_name = model_spec
    if ":" in model_spec:
        provider_prefix, model_name = model_spec.split(":", 1)

    # Handle Google models - they need explicit API key from settings
    if provider_prefix in {"google-gla", "google"} or model_spec.startswith("google-gla:"):
        model_name = model_name if provider_prefix else model_spec.split(":", 1)[1]
        if not settings.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY not configured in settings. "
                "Set it in .env or environment variables."
            )
        model = GoogleModel(model_name, provider=GoogleProvider(api_key=settings.google_api_key))
        # Hide reasoning/thinking traces from output
        model_settings = GoogleModelSettings(google_thinking_config={"include_thoughts": False})
        return model, model_settings

    # Handle Anthropic models (prefixed or claude-* format)
    if provider_prefix == "anthropic" or model_spec.startswith("claude-"):
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured in settings. "
                "Set it in .env or environment variables."
            )
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)
        model_to_use = model_name if provider_prefix == "anthropic" else model_spec
        return AnthropicModel(model_to_use, provider=provider), None

    # Handle OpenAI models (openai:* format)
    if provider_prefix == "openai" or model_spec.startswith("openai:"):
        model_name = model_name if provider_prefix else model_spec.split(":", 1)[1]
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY not configured in settings. "
                "Set it in .env or environment variables."
            )
        return OpenAIModel(
            model_name, provider=OpenAIProvider(api_key=settings.openai_api_key)
        ), None

    # Fallback - return model_spec string for other providers
    return model_spec, None


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
    model, model_settings = _build_model(model_spec)

    agent: Agent[ChatDeps, str] = Agent(
        model,
        deps_type=ChatDeps,
        output_type=str,
        system_prompt=system_prompt_text,
        model_settings=model_settings,
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
    # Log user prompt at INFO with safe truncation to avoid needing DEBUG
    trimmed_prompt = user_prompt.replace("\n", " ")[:500]
    if len(user_prompt) > 500:
        trimmed_prompt = f"{trimmed_prompt}... [truncated]"
    logger.info(
        f"[Stream] run_chat_stream started | session_id={session.id} "
        f"model={session.llm_model} prompt_len={len(user_prompt)} "
        f"user_prompt='{trimmed_prompt}'"
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

    except asyncio.CancelledError:
        logger.warning(
            f"[Stream] Cancelled | session_id={session.id} "
            f"collected_len={len(collected_text)} chunks={chunk_count}"
        )
        db.rollback()
        raise
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
    trimmed_prompt = user_prompt.replace("\n", " ")[:500]
    if len(user_prompt) > 500:
        trimmed_prompt = f"{trimmed_prompt}... [truncated]"
    logger.info(
        f"[Sync] run_chat_sync started | session_id={session.id} "
        f"model={session.llm_model} prompt_len={len(user_prompt)} "
        f"user_prompt='{trimmed_prompt}'"
    )

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
