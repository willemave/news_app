"""Deep research service using OpenAI's o4-mini-deep-research model.

This service uses the OpenAI Responses API to perform deep research queries.
Deep research runs as a background task with web search and code interpreter tools.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.schema import ChatMessage, ChatSession, Content, MessageProcessingStatus
from app.services.llm_models import DEEP_RESEARCH_MODEL

logger = get_logger(__name__)

# Deep research configuration
DEEP_RESEARCH_TIMEOUT = 600.0  # 10 minutes max
POLL_INTERVAL = 2.0  # Poll every 2 seconds
MAX_POLL_ATTEMPTS = 300  # 10 minutes at 2 second intervals


@dataclass
class DeepResearchResult:
    """Result from a deep research query."""

    response_id: str
    status: str
    output_text: str | None
    sources: list[dict] | None
    usage: dict | None
    error: str | None


class DeepResearchClient:
    """Client for OpenAI's deep research Responses API using official SDK."""

    def __init__(self) -> None:
        """Initialize the deep research client."""
        self._settings = get_settings()
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the OpenAI async client."""
        if self._client is None:
            if not self._settings.openai_api_key:
                logger.error("[DeepResearch:CLIENT] OPENAI_API_KEY not configured")
                raise ValueError("OPENAI_API_KEY not configured in settings")
            logger.debug("[DeepResearch:CLIENT] Creating new OpenAI async client")
            self._client = AsyncOpenAI(
                api_key=self._settings.openai_api_key,
                timeout=DEEP_RESEARCH_TIMEOUT,
            )
        return self._client

    async def close(self) -> None:
        """Close the OpenAI client."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.debug("[DeepResearch:CLIENT] Closed OpenAI client")

    async def start_research(
        self,
        query: str,
        context: str | None = None,
    ) -> str:
        """Start a deep research query in background mode.

        Args:
            query: The research query to execute.
            context: Optional context to include with the query.

        Returns:
            The response ID for polling.

        Raises:
            openai.APIError: If the request fails.
            ValueError: If the API key is not configured.
        """
        client = self._get_client()

        # Build the input with optional context
        full_input = query
        if context:
            full_input = f"Context:\n{context}\n\nResearch Query:\n{query}"
            logger.debug(
                "[DeepResearch:CONTEXT] Added context (len=%d) to query",
                len(context),
            )

        logger.info(
            "[DeepResearch:START] model=%s input_len=%d has_context=%s",
            DEEP_RESEARCH_MODEL,
            len(full_input),
            context is not None,
        )

        try:
            # Use the responses API with background mode
            response = await client.responses.create(
                model=DEEP_RESEARCH_MODEL,
                input=full_input,
                reasoning={"summary": "detailed"},
                background=True,
                tools=[
                    {"type": "web_search_preview"},
                    {"type": "code_interpreter", "container": {"type": "auto"}},
                ],
            )

            response_id = response.id
            logger.info(
                "[DeepResearch:QUEUED] response_id=%s status=%s",
                response_id,
                response.status,
            )
            return response_id

        except RateLimitError as e:
            logger.error(
                "[DeepResearch:RATE_LIMIT] Rate limit exceeded: %s",
                str(e),
            )
            raise
        except APIConnectionError as e:
            logger.error(
                "[DeepResearch:CONNECTION_ERROR] Connection failed: %s",
                str(e),
            )
            raise
        except APIError as e:
            logger.error(
                "[DeepResearch:API_ERROR] API error status=%s message=%s",
                e.status_code,
                str(e),
            )
            raise

    async def poll_result(self, response_id: str) -> DeepResearchResult:
        """Poll for the result of a deep research query.

        Args:
            response_id: The response ID from start_research.

        Returns:
            DeepResearchResult with current status and any available output.
        """
        client = self._get_client()

        try:
            response = await client.responses.retrieve(response_id)
        except APIError as e:
            logger.error(
                "[DeepResearch:POLL_ERROR] GET /responses/%s failed status=%s",
                response_id,
                e.status_code,
            )
            raise

        status = response.status or "unknown"

        logger.debug(
            "[DeepResearch:POLL] response_id=%s status=%s",
            response_id,
            status,
        )

        # Extract output text from the response
        output_text = None
        sources = None

        if status in ("succeeded", "completed"):
            # Try to get output_text directly first
            if hasattr(response, "output_text") and response.output_text:
                output_text = response.output_text
            elif hasattr(response, "output") and response.output:
                # Parse output items for message content
                for item in response.output:
                    if hasattr(item, "type") and item.type == "message":
                        if hasattr(item, "content"):
                            for c in item.content:
                                if hasattr(c, "type") and c.type == "output_text":
                                    output_text = getattr(c, "text", "")
                                    break
                        if output_text:
                            break

            # Log token usage if available
            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                logger.info(
                    "[DeepResearch:USAGE] response_id=%s input_tokens=%s output_tokens=%s total=%s",
                    response_id,
                    getattr(usage, "input_tokens", None),
                    getattr(usage, "output_tokens", None),
                    getattr(usage, "total_tokens", None),
                )

        # Build usage dict from response
        usage_dict = None
        if hasattr(response, "usage") and response.usage:
            usage_dict = {
                "input_tokens": getattr(response.usage, "input_tokens", None),
                "output_tokens": getattr(response.usage, "output_tokens", None),
                "total_tokens": getattr(response.usage, "total_tokens", None),
            }

        return DeepResearchResult(
            response_id=response_id,
            status=status,
            output_text=output_text,
            sources=sources,
            usage=usage_dict,
            error=getattr(response, "error", None),
        )

    async def wait_for_completion(
        self,
        response_id: str,
        poll_interval: float = POLL_INTERVAL,
        max_attempts: int = MAX_POLL_ATTEMPTS,
    ) -> DeepResearchResult:
        """Wait for a deep research query to complete.

        Args:
            response_id: The response ID to wait for.
            poll_interval: Seconds between polls.
            max_attempts: Maximum number of poll attempts.

        Returns:
            DeepResearchResult with final status and output.
        """
        start_time = perf_counter()

        for attempt in range(max_attempts):
            result = await self.poll_result(response_id)

            if result.status in ("succeeded", "completed"):
                duration = perf_counter() - start_time
                logger.info(
                    "[DeepResearch:COMPLETE] id=%s dur=%.1fs attempts=%d len=%d",
                    response_id,
                    duration,
                    attempt + 1,
                    len(result.output_text) if result.output_text else 0,
                )
                return result

            if result.status == "failed":
                duration = perf_counter() - start_time
                logger.error(
                    "[DeepResearch:FAILED] response_id=%s duration=%.1fs error=%s",
                    response_id,
                    duration,
                    result.error,
                )
                return result

            # Still processing, wait and poll again
            if attempt % 10 == 0:  # Log every 10 attempts (~20 seconds)
                elapsed = perf_counter() - start_time
                logger.info(
                    "[DeepResearch:POLLING] response_id=%s status=%s attempt=%d elapsed=%.0fs",
                    response_id,
                    result.status,
                    attempt + 1,
                    elapsed,
                )

            await asyncio.sleep(poll_interval)

        # Timeout
        duration = perf_counter() - start_time
        logger.error(
            "[DeepResearch:TIMEOUT] response_id=%s duration=%.1fs max_attempts=%d",
            response_id,
            duration,
            max_attempts,
        )
        return DeepResearchResult(
            response_id=response_id,
            status="timeout",
            output_text=None,
            sources=None,
            usage=None,
            error=f"Research timed out after {duration:.1f} seconds",
        )


# Global client instance
_client: DeepResearchClient | None = None


def get_deep_research_client() -> DeepResearchClient:
    """Get the global deep research client."""
    global _client
    if _client is None:
        _client = DeepResearchClient()
    return _client


async def close_deep_research_client() -> None:
    """Close the global deep research client.

    Call this during application shutdown to release HTTP connections.
    """
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def process_deep_research_message(
    session_id: int,
    message_id: int,
    user_prompt: str,
) -> None:
    """Process a deep research message asynchronously.

    This function runs independently after the endpoint returns.
    It submits the research query, polls for completion, and updates
    the message record with the result.

    Args:
        session_id: Chat session ID.
        message_id: ChatMessage ID to update on completion.
        user_prompt: The user's research query.
    """
    from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

    from app.core.db import get_session_factory
    from app.services.event_logger import log_event

    total_start = perf_counter()
    trimmed_prompt = user_prompt.replace("\n", " ")[:100]
    if len(user_prompt) > 100:
        trimmed_prompt = f"{trimmed_prompt}..."

    logger.info(
        "[DeepResearch:PROCESS_START] sid=%s mid=%s prompt_len=%d prompt='%s'",
        session_id,
        message_id,
        len(user_prompt),
        trimmed_prompt,
    )

    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            logger.error("[DeepResearch:ERROR] Session %s not found", session_id)
            return

        logger.debug(
            "[DeepResearch:SESSION] sid=%s user_id=%s content_id=%s type=%s",
            session_id,
            session.user_id,
            session.content_id,
            session.session_type,
        )

        # Build context from article if available
        context = None
        if session.content_id:
            content = db.query(Content).filter(Content.id == session.content_id).first()
            if content:
                context = _build_research_context(content)
                logger.debug(
                    "[DeepResearch:CONTEXT] Built context from content_id=%s len=%d",
                    session.content_id,
                    len(context) if context else 0,
                )
            else:
                logger.warning(
                    "[DeepResearch:CONTEXT] Content not found content_id=%s",
                    session.content_id,
                )

        # Start the deep research
        client = get_deep_research_client()
        response_id = await client.start_research(user_prompt, context)

        logger.info(
            "[DeepResearch:SUBMITTED] sid=%s mid=%s response_id=%s user_id=%s",
            session_id,
            message_id,
            response_id,
            session.user_id,
        )

        # Wait for completion
        result = await client.wait_for_completion(response_id)

        if result.status in ("succeeded", "completed") and result.output_text:
            # Build the message list with user request and assistant response
            from pydantic_ai.messages import ModelMessagesTypeAdapter

            messages = [
                ModelRequest(parts=[UserPromptPart(content=user_prompt)]),
                ModelResponse(parts=[TextPart(content=result.output_text)]),
            ]

            message_json = ModelMessagesTypeAdapter.dump_json(messages).decode("utf-8")

            # Update the message with the result
            db_message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
            if db_message:
                db_message.message_list = message_json
                db_message.status = MessageProcessingStatus.COMPLETED.value

                # Update session timestamps
                session.last_message_at = datetime.utcnow()
                session.updated_at = datetime.utcnow()
                db.commit()

                total_ms = (perf_counter() - total_start) * 1000
                logger.info(
                    "[DeepResearch:DONE] sid=%s mid=%s user_id=%s total=%.0fms output_len=%d",
                    session_id,
                    message_id,
                    session.user_id,
                    total_ms,
                    len(result.output_text),
                )

                # Log event with usage metrics
                usage_data = {}
                if result.usage:
                    usage_data = {
                        "input_tokens": result.usage.get("input_tokens"),
                        "output_tokens": result.usage.get("output_tokens"),
                        "total_tokens": result.usage.get("total_tokens"),
                    }

                log_event(
                    event_type="chat",
                    event_name="deep_research_completed",
                    status="completed",
                    user_id=session.user_id,
                    session_id=session_id,
                    message_id=message_id,
                    response_id=response_id,
                    content_id=session.content_id,
                    duration_ms=total_ms,
                    output_len=len(result.output_text),
                    **usage_data,
                )
        else:
            # Research failed or timed out
            error_msg = result.error or f"Research failed with status: {result.status}"
            _update_message_failed(db, message_id, error_msg)

            total_ms = (perf_counter() - total_start) * 1000
            logger.error(
                "[DeepResearch:FAILED] sid=%s mid=%s user_id=%s total=%.0fms error=%s",
                session_id,
                message_id,
                session.user_id,
                total_ms,
                error_msg,
            )

            log_event(
                event_type="chat",
                event_name="deep_research_failed",
                status="failed",
                user_id=session.user_id,
                session_id=session_id,
                message_id=message_id,
                response_id=response_id,
                error=error_msg,
                duration_ms=total_ms,
            )

    except Exception as exc:
        total_ms = (perf_counter() - total_start) * 1000
        logger.exception(
            "[DeepResearch:EXCEPTION] sid=%s mid=%s total_ms=%.1f error=%s",
            session_id,
            message_id,
            total_ms,
            exc,
        )
        try:
            _update_message_failed(db, message_id, str(exc))
        except Exception as update_exc:
            logger.error(
                "[DeepResearch:UPDATE_FAILED] mid=%s error=%s",
                message_id,
                update_exc,
            )
    finally:
        db.close()


def _build_research_context(content: Content) -> str | None:
    """Build context string from content for research."""
    if not content:
        return None

    parts = []

    if content.title:
        parts.append(f"Article Title: {content.title}")

    if content.url:
        parts.append(f"URL: {content.url}")

    if content.source:
        parts.append(f"Source: {content.source}")

    if content.content_metadata:
        metadata = content.content_metadata
        summary = metadata.get("summary", {})

        overview = (
            summary.get("summary")
            or summary.get("overview")
            or summary.get("hook")
            or summary.get("takeaway")
        )
        if overview:
            parts.append(f"\nOverview: {overview}")

        bullet_points = summary.get("key_points") or summary.get("bullet_points")
        if bullet_points:
            points = [
                bp.get("text", "") if isinstance(bp, dict) else str(bp)
                for bp in bullet_points
                if isinstance(bp, (dict, str))
            ]
        else:
            bullet_points = summary.get("insights", [])
            points = [
                ins.get("insight", "")
                for ins in bullet_points
                if isinstance(ins, dict) and ins.get("insight")
            ]
        if points:
            parts.append("\nKey Points:")
            for point in points[:5]:
                parts.append(f"  - {point}")

    context = "\n".join(parts) if parts else None

    if context:
        logger.debug(
            "[DeepResearch:CONTEXT] Built context with %d parts, len=%d",
            len(parts),
            len(context),
        )

    return context


def _update_message_failed(db: Session, message_id: int, error: str) -> None:
    """Mark a message as failed."""
    db_message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if db_message:
        db_message.status = MessageProcessingStatus.FAILED.value
        db_message.error = error
        db.commit()
        logger.debug("[DeepResearch:DB] Updated message %s to failed", message_id)
