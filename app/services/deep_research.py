"""Deep research service using OpenAI's o4-mini-deep-research model.

This service uses the OpenAI Responses API to perform deep research queries.
Deep research runs as a background task with web search and code interpreter tools.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter

import httpx
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
    """Client for OpenAI's deep research Responses API."""

    def __init__(self) -> None:
        """Initialize the deep research client."""
        self._settings = get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            if not self._settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured in settings")
            self._client = httpx.AsyncClient(
                base_url="https://api.openai.com/v1",
                headers={
                    "Authorization": f"Bearer {self._settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(DEEP_RESEARCH_TIMEOUT),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

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
            httpx.HTTPError: If the request fails.
            ValueError: If the API key is not configured.
        """
        client = await self._get_client()

        # Build the input with optional context
        full_input = query
        if context:
            full_input = f"Context:\n{context}\n\nResearch Query:\n{query}"

        payload = {
            "model": DEEP_RESEARCH_MODEL,
            "input": full_input,
            "reasoning": {"summary": "detailed"},
            "background": True,
            "tools": [
                {"type": "web_search_preview"},
                {"type": "code_interpreter", "container": {"type": "auto"}},
            ],
        }

        logger.info(
            "[DeepResearch:START] Submitting query (len=%d) to background",
            len(full_input),
        )

        response = await client.post("/responses", json=payload)
        response.raise_for_status()

        data = response.json()
        response_id = data.get("id")

        logger.info(
            "[DeepResearch:QUEUED] response_id=%s status=%s",
            response_id,
            data.get("status"),
        )

        return response_id

    async def poll_result(self, response_id: str) -> DeepResearchResult:
        """Poll for the result of a deep research query.

        Args:
            response_id: The response ID from start_research.

        Returns:
            DeepResearchResult with current status and any available output.
        """
        client = await self._get_client()

        response = await client.get(f"/responses/{response_id}")
        response.raise_for_status()

        data = response.json()
        status = data.get("status", "unknown")

        # Extract output text from the response
        output_text = None
        sources = None

        if status in ("succeeded", "completed"):
            output_items = data.get("output", [])
            for item in output_items:
                if item.get("type") == "message":
                    content = item.get("content", [])
                    for c in content:
                        if c.get("type") == "output_text":
                            output_text = c.get("text", "")
                            break
                    if output_text:
                        break

            # If output_text not found in new format, try legacy format
            if not output_text:
                output_text = data.get("output_text")

        return DeepResearchResult(
            response_id=response_id,
            status=status,
            output_text=output_text,
            sources=sources,
            usage=data.get("usage"),
            error=data.get("error"),
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
                    "[DeepResearch:COMPLETE] response_id=%s duration=%.1fs attempts=%d",
                    response_id,
                    duration,
                    attempt + 1,
                )
                return result

            if result.status == "failed":
                logger.error(
                    "[DeepResearch:FAILED] response_id=%s error=%s",
                    response_id,
                    result.error,
                )
                return result

            # Still processing, wait and poll again
            if attempt % 10 == 0:  # Log every 10 attempts
                logger.info(
                    "[DeepResearch:POLLING] response_id=%s status=%s attempt=%d",
                    response_id,
                    result.status,
                    attempt + 1,
                )

            await asyncio.sleep(poll_interval)

        # Timeout
        duration = perf_counter() - start_time
        logger.error(
            "[DeepResearch:TIMEOUT] response_id=%s duration=%.1fs",
            response_id,
            duration,
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
        "[DeepResearch:PROCESS_START] sid=%s mid=%s prompt='%s'",
        session_id,
        message_id,
        trimmed_prompt,
    )

    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            logger.error("[DeepResearch:ERROR] Session %s not found", session_id)
            return

        # Build context from article if available
        context = None
        if session.content_id:
            content = db.query(Content).filter(Content.id == session.content_id).first()
            if content:
                context = _build_research_context(content)

        # Start the deep research
        client = get_deep_research_client()
        response_id = await client.start_research(user_prompt, context)

        logger.info(
            "[DeepResearch:SUBMITTED] sid=%s mid=%s response_id=%s",
            session_id,
            message_id,
            response_id,
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
                    "[DeepResearch:DONE] sid=%s mid=%s total=%.0fms output_len=%d",
                    session_id,
                    message_id,
                    total_ms,
                    len(result.output_text),
                )

                log_event(
                    event_type="chat",
                    event_name="deep_research_completed",
                    status="completed",
                    user_id=session.user_id,
                    session_id=session_id,
                    response_id=response_id,
                )
        else:
            # Research failed or timed out
            error_msg = result.error or f"Research failed with status: {result.status}"
            _update_message_failed(db, message_id, error_msg)

            logger.error(
                "[DeepResearch:FAILED] sid=%s mid=%s error=%s",
                session_id,
                message_id,
                error_msg,
            )

    except Exception as exc:
        total_ms = (perf_counter() - total_start) * 1000
        logger.error(
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

        if overview := summary.get("overview"):
            parts.append(f"\nOverview: {overview}")

        if bullet_points := summary.get("bullet_points"):
            points = [bp.get("text", "") for bp in bullet_points if isinstance(bp, dict)]
            if points:
                parts.append("\nKey Points:")
                for point in points[:5]:
                    parts.append(f"  - {point}")

    return "\n".join(parts) if parts else None


def _update_message_failed(db: Session, message_id: int, error: str) -> None:
    """Mark a message as failed."""
    db_message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if db_message:
        db_message.status = MessageProcessingStatus.FAILED.value
        db_message.error = error
        db.commit()
