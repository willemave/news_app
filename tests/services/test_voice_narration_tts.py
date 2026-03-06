"""Tests for one-shot digest narration TTS."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.voice import narration_tts


def test_digest_narration_tts_sets_speed_voice_setting(monkeypatch) -> None:
    """Digest TTS should forward the configured speed to ElevenLabs voice settings."""

    captured_kwargs: dict[str, object] = {}

    class FakeTextToSpeech:
        def convert(self, **kwargs):
            captured_kwargs.update(kwargs)
            return iter([b"chunk"])

    class FakeElevenLabs:
        def __init__(self, api_key: str | None) -> None:
            self.api_key = api_key
            self.text_to_speech = FakeTextToSpeech()

    class FakeVoiceSettings:
        def __init__(self, *, speed: float) -> None:
            self.speed = speed

    monkeypatch.setattr(narration_tts, "ElevenLabs", FakeElevenLabs)
    monkeypatch.setattr(narration_tts, "VoiceSettings", FakeVoiceSettings)
    monkeypatch.setattr(narration_tts, "find_spec", lambda _name: object())
    monkeypatch.setattr(
        narration_tts,
        "get_settings",
        lambda: SimpleNamespace(
            elevenlabs_api_key="test-key",
            elevenlabs_tts_voice_id="voice-id",
            elevenlabs_digest_tts_model="eleven_turbo_v2_5",
            elevenlabs_digest_tts_output_format="mp3_44100_128",
            elevenlabs_digest_tts_speed=1.0,
        ),
    )
    narration_tts._digest_narration_tts_service = None

    audio = narration_tts.get_digest_narration_tts_service().synthesize_mp3(text="Hello world")

    assert audio == b"chunk"
    voice_settings = captured_kwargs["voice_settings"]
    assert isinstance(voice_settings, FakeVoiceSettings)
    assert voice_settings.speed == 1.0
