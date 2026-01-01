"""Tests for queue service error handling."""

from contextlib import contextmanager

from app.models.schema import ProcessingTask
from app.services.queue import QueueService, TaskStatus, TaskType


def test_complete_task_sets_default_error_message(db_session, monkeypatch):
    """QueueService fills a default error message when missing."""

    @contextmanager
    def _get_db_override():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr("app.services.queue.get_db", _get_db_override)

    task = ProcessingTask(
        task_type=TaskType.PROCESS_CONTENT.value,
        content_id=1,
        payload={},
        status=TaskStatus.PENDING.value,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    QueueService().complete_task(task.id, success=False, error_message=None)

    refreshed = db_session.query(ProcessingTask).filter(ProcessingTask.id == task.id).first()
    assert refreshed is not None
    assert refreshed.status == TaskStatus.FAILED.value
    assert refreshed.error_message == "Task failed without error details"
