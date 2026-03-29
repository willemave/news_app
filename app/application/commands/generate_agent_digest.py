"""Application command for news-native agent digest generation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.contracts import TaskType
from app.routers.api.models import AgentDigestRequest, AgentDigestResponse
from app.services.gateways.task_queue_gateway import get_task_queue_gateway


def execute(
    db: Session,
    *,
    user_id: int,
    payload: AgentDigestRequest,
) -> AgentDigestResponse:
    """Queue a news-native digest generation task."""
    del db, payload
    queue = get_task_queue_gateway()
    job_id = queue.enqueue(
        TaskType.GENERATE_NEWS_DIGEST,
        payload={
            "user_id": user_id,
            "trigger_reason": "agent",
            "force": True,
        },
    )
    return AgentDigestResponse(job_id=job_id)
