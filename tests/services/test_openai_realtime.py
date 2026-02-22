from __future__ import annotations

from app.services import openai_realtime


def test_build_transcription_session_config_defaults():
    config = openai_realtime.build_transcription_session_config()

    assert config["input_audio_format"] == "pcm16"
    assert config["turn_detection"]["type"] == "server_vad"
    assert config["input_audio_transcription"]["model"] == openai_realtime.REALTIME_TRANSCRIPTION_MODEL


def test_build_transcription_session_config_with_locale():
    config = openai_realtime.build_transcription_session_config(locale="en")

    assert config["input_audio_transcription"]["language"] == "en"
