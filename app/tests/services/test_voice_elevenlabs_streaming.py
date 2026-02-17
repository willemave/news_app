"""Tests for ElevenLabs voice streaming helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.voice import elevenlabs_streaming as streaming


@pytest.mark.asyncio
async def test_open_realtime_stt_connection_reads_text_payload(monkeypatch) -> None:
    """Realtime STT callback should accept payloads using the ``text`` key."""

    callbacks_seen: dict[str, str] = {}

    class FakeConnection:
        def __init__(self) -> None:
            self.handlers = {}

        def on(self, event, callback):
            self.handlers[event] = callback

    fake_connection = FakeConnection()

    class FakeRealtime:
        async def connect(self, _options):
            return fake_connection

    class FakeSpeechToText:
        realtime = FakeRealtime()

    class FakeElevenLabs:
        def __init__(self, api_key: str | None) -> None:
            self.api_key = api_key
            self.speech_to_text = FakeSpeechToText()

    monkeypatch.setattr(streaming, "_ensure_elevenlabs_ready", lambda: None)
    monkeypatch.setattr(streaming, "ElevenLabs", FakeElevenLabs)

    connection = await streaming.open_realtime_stt_connection(
        callbacks=streaming.ElevenLabsSttCallbacks(
            on_partial=lambda value: callbacks_seen.setdefault("partial", value),
            on_final=lambda value: callbacks_seen.setdefault("final", value),
            on_error=lambda value: callbacks_seen.setdefault("error", value),
        )
    )

    assert connection is fake_connection
    fake_connection.handlers[streaming.RealtimeEvents.PARTIAL_TRANSCRIPT]({"text": "hello"})
    fake_connection.handlers[streaming.RealtimeEvents.COMMITTED_TRANSCRIPT]({"text": "world"})
    fake_connection.handlers[streaming.RealtimeEvents.ERROR]({"error": "boom"})

    assert callbacks_seen["partial"] == "hello"
    assert callbacks_seen["final"] == "world"
    assert callbacks_seen["error"] == "boom"


def test_build_realtime_tts_stream_sets_voice_settings_none(monkeypatch) -> None:
    """Realtime TTS should pass ``voice_settings=None`` to avoid SDK default bugs."""

    captured_kwargs: dict[str, object] = {}

    class FakeTextToSpeech:
        def convert_realtime(self, **kwargs):
            captured_kwargs.update(kwargs)
            return iter([b"chunk"])

    class FakeElevenLabs:
        def __init__(self, api_key: str | None) -> None:
            self.api_key = api_key
            self.text_to_speech = FakeTextToSpeech()

    monkeypatch.setattr(streaming, "_ensure_elevenlabs_ready", lambda: None)
    monkeypatch.setattr(streaming, "ElevenLabs", FakeElevenLabs)

    audio_iter = streaming.build_realtime_tts_stream(iter(["hello"]))
    assert hasattr(audio_iter, "__iter__")
    assert captured_kwargs["voice_settings"] is None


@pytest.mark.asyncio
async def test_open_realtime_stt_connection_omits_blank_language_code(monkeypatch) -> None:
    """Blank STT language config should not be forwarded as ``language_code``."""

    captured_options: dict[str, object] = {}

    class FakeConnection:
        def on(self, _event, _callback) -> None:
            return

    fake_connection = FakeConnection()

    class FakeRealtime:
        async def connect(self, options):
            captured_options.update(options)
            return fake_connection

    class FakeSpeechToText:
        realtime = FakeRealtime()

    class FakeElevenLabs:
        def __init__(self, api_key: str | None) -> None:
            self.api_key = api_key
            self.speech_to_text = FakeSpeechToText()

    monkeypatch.setattr(streaming, "_ensure_elevenlabs_ready", lambda: None)
    monkeypatch.setattr(streaming, "ElevenLabs", FakeElevenLabs)
    monkeypatch.setattr(
        streaming,
        "get_settings",
        lambda: SimpleNamespace(
            elevenlabs_api_key="test-key",
            elevenlabs_stt_model_id="scribe_v2_realtime",
            elevenlabs_stt_language="   ",
            voice_trace_logging=False,
        ),
    )

    connection = await streaming.open_realtime_stt_connection(
        callbacks=streaming.ElevenLabsSttCallbacks(
            on_partial=lambda _value: None,
            on_final=lambda _value: None,
            on_error=lambda _value: None,
        )
    )

    assert connection is fake_connection
    assert captured_options["model_id"] == "scribe_v2_realtime"
    assert "language_code" not in captured_options
