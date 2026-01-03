from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from app.models.metadata import ContentType
from app.models.schema import Content
from app.pipeline.podcast_workers import PodcastDownloadWorker
from app.services.queue import TaskType


def test_youtube_audio_download_queues_transcribe(db_session, mocker, tmp_path):
    youtube_url = "https://www.youtube.com/watch?v=abc123xyz"
    content = Content(
        content_type=ContentType.PODCAST.value,
        url=youtube_url,
        content_metadata={"audio_url": youtube_url},
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)

    worker = PodcastDownloadWorker()
    worker.base_dir = tmp_path / "podcasts"
    worker.queue_service = mocker.Mock()

    @contextmanager
    def _get_db():
        yield db_session

    mocker.patch("app.pipeline.podcast_workers.get_db", _get_db)

    audio_path = worker.base_dir / "youtube" / "test-audio.webm"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"audio-bytes")

    mocker.patch.object(worker, "_download_youtube_audio", return_value=audio_path)

    assert worker.process_download_task(content.id) is True

    db_session.refresh(content)
    metadata = content.content_metadata

    assert metadata["youtube_video"] is True
    assert metadata["file_path"] == str(audio_path)
    assert metadata["file_size"] == audio_path.stat().st_size
    assert "download_skipped" not in metadata

    worker.queue_service.enqueue.assert_called_once_with(
        TaskType.TRANSCRIBE, content_id=content.id
    )
