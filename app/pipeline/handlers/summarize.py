"""Summarization task handler."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.models.metadata import ContentStatus, ContentType, NewsSummary
from app.models.schema import Content
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.services.dig_deeper import enqueue_dig_deeper_task
from app.services.queue import TaskType

logger = get_logger(__name__)


def _extract_share_and_chat_user_ids(metadata: dict[str, Any]) -> list[int]:
    """Extract share-and-chat user IDs from metadata if present."""
    raw_users = metadata.get("share_and_chat_user_ids")
    user_ids: list[int] = []

    if isinstance(raw_users, list):
        for value in raw_users:
            try:
                user_ids.append(int(value))
            except (TypeError, ValueError):
                continue
    elif raw_users is not None:
        try:
            user_ids.append(int(raw_users))
        except (TypeError, ValueError):
            user_ids = []

    return [user_id for user_id in user_ids if user_id > 0]


def _build_news_context(metadata: dict[str, Any]) -> str:
    """Build aggregator context string for news items."""
    article = metadata.get("article", {})
    aggregator = metadata.get("aggregator", {})
    lines: list[str] = []

    article_title = article.get("title") or ""
    article_url = article.get("url") or ""

    if article_title:
        lines.append(f"Article Title: {article_title}")
    if article_url:
        lines.append(f"Article URL: {article_url}")

    if aggregator:
        name = aggregator.get("name") or metadata.get("platform")
        agg_title = aggregator.get("title")
        agg_url = metadata.get("discussion_url") or aggregator.get("url")
        author = aggregator.get("author")

        context_bits = []
        if name:
            context_bits.append(name)
        if author:
            context_bits.append(f"by {author}")
        if agg_title and agg_title != article_title:
            lines.append(f"Aggregator Headline: {agg_title}")
        if context_bits:
            lines.append("Aggregator Context: " + ", ".join(context_bits))
        if agg_url:
            lines.append(f"Discussion URL: {agg_url}")

        extra = aggregator.get("metadata") or {}
        highlights = []
        for field in ["score", "comments_count", "likes", "retweets", "replies"]:
            value = extra.get(field)
            if value is not None:
                highlights.append(f"{field}={value}")
        if highlights:
            lines.append("Signals: " + ", ".join(highlights))

    summary_payload = metadata.get("summary") if isinstance(metadata, dict) else {}
    excerpt = metadata.get("excerpt")
    if not excerpt and isinstance(summary_payload, dict):
        excerpt = (
            summary_payload.get("overview")
            or summary_payload.get("summary")
            or summary_payload.get("hook")
            or summary_payload.get("takeaway")
        )
    if excerpt:
        lines.append(f"Aggregator Summary: {excerpt}")

    return "\n".join(lines)


class SummarizeHandler:
    """Handle content summarization tasks."""

    task_type = TaskType.SUMMARIZE

    def handle(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        """Generate summaries and queue follow-up tasks."""
        try:
            content_id = task.content_id or task.payload.get("content_id")

            if not content_id:
                logger.error(
                    "SUMMARIZE_TASK_ERROR: No content_id provided. Task data: %s",
                    task.model_dump(),
                )
                return TaskResult.fail("No content_id provided")

            logger.info("Processing summarize task for content %s", content_id)

            with context.db_factory() as db:
                content = db.query(Content).filter(Content.id == content_id).first()
                if not content:
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: Content %s not found in database",
                        content_id,
                    )
                    return TaskResult.fail("Content not found")

                title_preview = "No title"
                if content.title and isinstance(content.title, str):
                    title_preview = content.title[:50]
                logger.info(
                    "Summarizing content %s: type=%s, title=%s, url=%s, status=%s",
                    content_id,
                    content.content_type,
                    title_preview,
                    content.url,
                    content.status,
                )

                def _persist_failure(reason: str) -> None:
                    metadata = dict(content.content_metadata or {})
                    metadata.pop("summary", None)
                    existing_errors = metadata.get("processing_errors")
                    processing_errors = (
                        existing_errors.copy() if isinstance(existing_errors, list) else []
                    )
                    processing_errors.append(
                        {
                            "stage": "summarization",
                            "reason": reason,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                    metadata["processing_errors"] = processing_errors

                    content.content_metadata = metadata
                    content.status = ContentStatus.FAILED.value
                    content.error_message = reason[:500]
                    content.processed_at = datetime.utcnow()
                    db.commit()

                metadata = content.content_metadata or {}
                if content.content_type == "article":
                    text_to_summarize = metadata.get("content", "")
                elif content.content_type == "news":
                    text_to_summarize = metadata.get("content", "")
                    aggregator_context = _build_news_context(metadata)
                    if aggregator_context and text_to_summarize:
                        text_to_summarize = (
                            f"Context:\n{aggregator_context}\n\n"
                            f"Article Content:\n{text_to_summarize}"
                        )
                elif content.content_type == "podcast":
                    text_to_summarize = metadata.get("transcript", "")
                else:
                    reason = f"Unknown content type for summarization: {content.content_type}"
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: %s. Content %s, URL: %s",
                        reason,
                        content_id,
                        content.url,
                        extra={
                            "component": "summarization",
                            "operation": "summarize_task",
                            "item_id": content_id,
                            "context_data": {
                                "content_type": content.content_type,
                                "url": str(content.url),
                                "title": content.title,
                            },
                        },
                    )
                    _persist_failure(reason)
                    return TaskResult.fail(reason)

                if not text_to_summarize:
                    expected_field = (
                        "transcript" if content.content_type == "podcast" else "content"
                    )
                    reason = f"No text to summarize for content {content_id}"
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: %s. Type: %s, expected field: %s, "
                        "metadata keys: %s, URL: %s",
                        reason,
                        content.content_type,
                        expected_field,
                        list(metadata.keys()),
                        content.url,
                        extra={
                            "component": "summarization",
                            "operation": "summarize_task",
                            "item_id": content_id,
                            "context_data": {
                                "content_type": content.content_type,
                                "expected_field": expected_field,
                                "metadata_keys": list(metadata.keys()),
                                "url": str(content.url),
                                "title": content.title,
                            },
                        },
                    )
                    _persist_failure(reason)
                    return TaskResult.fail(reason)

                logger.debug(
                    "Content %s has %d characters to summarize",
                    content_id,
                    len(text_to_summarize),
                )

                summarization_type = content.content_type
                provider_override = None
                max_bullet_points = 6
                max_quotes = 8

                if content.content_type == "news":
                    summarization_type = "news_digest"
                    provider_override = "openai"
                    max_bullet_points = 4
                    max_quotes = 0
                elif content.content_type in ("article", "podcast"):
                    summarization_type = "interleaved"

                logger.info(
                    "Calling LLM for content %s: provider=%s, type=%s, "
                    "text_length=%d, max_bullets=%d",
                    content_id,
                    provider_override or "default",
                    summarization_type,
                    len(text_to_summarize),
                    max_bullet_points,
                )

                try:
                    summary = context.llm_service.summarize_content(
                        text_to_summarize,
                        content_type=summarization_type,
                        content_id=content.id,
                        max_bullet_points=max_bullet_points,
                        max_quotes=max_quotes,
                        provider_override=provider_override,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "SUMMARIZE_TASK_ERROR: LLM call failed for content %s (%s). "
                        "Error: %s, URL: %s, text_length: %d",
                        content_id,
                        content.content_type,
                        str(exc),
                        content.url,
                        len(text_to_summarize),
                        extra={
                            "component": "summarization",
                            "operation": "llm_summarization",
                            "item_id": content_id,
                            "context_data": {
                                "content_type": content.content_type,
                                "summarization_type": summarization_type,
                                "provider": provider_override or "default",
                                "text_length": len(text_to_summarize),
                                "url": str(content.url),
                                "title": content.title,
                            },
                        },
                    )
                    _persist_failure(f"Summarization error: {exc}")
                    return TaskResult.fail(str(exc))

                if summary is not None:
                    metadata = dict(content.content_metadata or {})
                    share_and_chat_user_ids = _extract_share_and_chat_user_ids(metadata)
                    summary_dict = (
                        summary.model_dump(mode="json", by_alias=True)
                        if hasattr(summary, "model_dump")
                        else summary
                    )

                    if isinstance(summary, NewsSummary):
                        summary_dict.setdefault("classification", summary.classification)
                        metadata["summary"] = summary_dict

                        article_section = metadata.get("article", {})
                        article_section.setdefault(
                            "url",
                            summary_dict.get("final_url_after_redirects")
                            or summary_dict.get("article", {}).get("url"),
                        )
                        if summary.title and not article_section.get("title"):
                            article_section["title"] = summary.title
                        metadata["article"] = article_section

                        if summary.title:
                            content.title = summary.title

                        logger.info(
                            "Generated news digest summary for content %s",
                            content_id,
                        )
                    else:
                        metadata["summary"] = summary_dict
                        if summary_dict.get("title") and not content.title:
                            content.title = summary_dict["title"]
                        logger.info("Generated summary for content %s", content_id)

                    metadata["summarization_date"] = datetime.utcnow().isoformat()
                    if share_and_chat_user_ids:
                        metadata.pop("share_and_chat_user_ids", None)

                    content.content_metadata = metadata
                    content.status = ContentStatus.COMPLETED.value
                    content.processed_at = datetime.utcnow()
                    db.commit()

                    if share_and_chat_user_ids:
                        for user_id in share_and_chat_user_ids:
                            enqueue_dig_deeper_task(db, content_id, user_id)
                        logger.info(
                            "Enqueued dig-deeper tasks for content %s (users=%s)",
                            content_id,
                            share_and_chat_user_ids,
                        )

                    if content.content_type == ContentType.NEWS.value:
                        context.queue_service.enqueue(
                            task_type=TaskType.GENERATE_THUMBNAIL,
                            content_id=content_id,
                        )
                        logger.info(
                            "Enqueued thumbnail generation for news content %s",
                            content_id,
                        )
                    else:
                        context.queue_service.enqueue(
                            task_type=TaskType.GENERATE_IMAGE,
                            content_id=content_id,
                        )
                        logger.info("Enqueued image generation for content %s", content_id)

                    return TaskResult.ok()

                reason = "LLM summarization returned None"
                logger.error(
                    "MISSING_SUMMARY: Content %s (%s) - %s. Title: %s, Text length: %s, URL: %s",
                    content_id,
                    content.content_type,
                    reason,
                    content.title,
                    len(text_to_summarize) if text_to_summarize else 0,
                    content.url,
                    extra={
                        "component": "summarization",
                        "operation": "llm_summarization",
                        "item_id": content_id,
                        "context_data": {
                            "content_type": content.content_type,
                            "summarization_type": summarization_type,
                            "provider": provider_override or "default",
                            "text_length": len(text_to_summarize) if text_to_summarize else 0,
                            "url": str(content.url),
                            "title": content.title,
                        },
                    },
                )
                _persist_failure(reason)
                return TaskResult.fail(reason)

        except Exception as exc:  # noqa: BLE001
            logger.error("Summarization error: %s", exc, exc_info=True)
            return TaskResult.fail(str(exc))
