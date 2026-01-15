from __future__ import annotations

from contextlib import contextmanager

from app.models.metadata import ContentType
from app.models.schema import Content
from app.pipeline.podcast_workers import PodcastDownloadWorker
from app.services.apple_podcasts import ApplePodcastResolution
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

    worker.queue_service.enqueue.assert_called_once_with(TaskType.TRANSCRIBE, content_id=content.id)


def test_apple_podcasts_resolution_fills_audio_url(db_session, mocker, tmp_path):
    apple_url = (
        "https://podcasts.apple.com/us/podcast/chatgpt-5-5-coming-soon/id1680633614?i=1000745224972"
    )
    content = Content(
        content_type=ContentType.PODCAST.value,
        url=apple_url,
        title=None,
        platform="apple_podcasts",
        content_metadata={"platform": "apple_podcasts"},
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
    mocker.patch(
        "app.pipeline.podcast_workers.resolve_apple_podcast_episode",
        return_value=ApplePodcastResolution(
            feed_url="https://example.com/feed.xml",
            episode_title="Episode Title",
            audio_url="https://example.com/audio.mp3",
        ),
    )

    def _fake_download(audio_url, file_path):  # noqa: ANN001
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"audio-bytes")

    mocker.patch.object(worker, "_download_with_retry", side_effect=_fake_download)

    assert worker.process_download_task(content.id) is True

    db_session.refresh(content)
    metadata = content.content_metadata
    assert metadata.get("audio_url") == "https://example.com/audio.mp3"
    assert metadata.get("feed_url") == "https://example.com/feed.xml"
    assert metadata.get("episode_title") == "Episode Title"

    worker.queue_service.enqueue.assert_called_once_with(TaskType.TRANSCRIBE, content_id=content.id)
