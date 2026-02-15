"""End-to-end voice integration check for SearchKnowledge and SearchWeb.

This script:
1. Ensures a test user and one known favorite article.
2. Generates short prompt audio files with ElevenLabs TTS.
3. Streams audio prompts to `/api/voice/ws`.
4. Validates tool calls by scanning structured logs for `voice_agent` operations.

Usage:
    python scripts/voice_tools_e2e.py
"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import base64
import glob
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import websockets
from elevenlabs.client import ElevenLabs

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.db import get_db
from app.core.security import create_access_token
from app.core.settings import get_settings
from app.models.schema import Content, ContentFavorites
from app.models.user import User

API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
OUT_DIR = Path("/tmp/newsly_voice_samples")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS: list[tuple[str, str]] = [
    (
        "knowledge_tool_test.mp3",
        "What is the exact title of my favorited Anthropic article?",
    ),
    (
        "web_tool_test.mp3",
        "What is one recent Rust project and who built it?",
    ),
]


def mp3_to_pcm16(path: Path) -> bytes:
    """Convert MP3 to PCM16 mono 16kHz bytes.

    Args:
        path: Source MP3 path.

    Returns:
        Raw PCM bytes.
    """

    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-",
    ]
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def ensure_user_and_favorite() -> tuple[int, str]:
    """Create test user/favorite row and return auth token.

    Returns:
        Tuple of `(user_id, access_token)`.
    """

    with get_db() as db:
        user = db.query(User).filter(User.email == "voice_smoke@example.com").first()
        if user is None:
            user = User(
                apple_id="voice_smoke_user",
                email="voice_smoke@example.com",
                full_name="Voice Smoke",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        content = (
            db.query(Content)
            .filter(Content.url == "https://www.latent.space/p/ainews-anthropic-launches-the-mcp")
            .first()
        )
        if content is None:
            content = Content(
                content_type="article",
                url="https://www.latent.space/p/ainews-anthropic-launches-the-mcp",
                source="AINews",
                title="Anthropic launches the MCP Apps open spec, in Claude.ai",
                status="completed",
                content_metadata={
                    "summary": {
                        "overview": (
                            "Anthropic launched MCP Apps for rich tool outputs in chat interfaces."
                        )
                    }
                },
            )
            db.add(content)
            db.commit()
            db.refresh(content)

        existing_favorite = (
            db.query(ContentFavorites)
            .filter(
                ContentFavorites.user_id == user.id,
                ContentFavorites.content_id == content.id,
            )
            .first()
        )
        if existing_favorite is None:
            db.add(ContentFavorites(user_id=user.id, content_id=content.id))
            db.commit()

        return int(user.id), create_access_token(int(user.id))


def generate_prompt_mp3s() -> list[Path]:
    """Generate prompt audio using ElevenLabs TTS.

    Returns:
        Paths of generated MP3 files.
    """

    settings = get_settings()
    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    paths: list[Path] = []
    for filename, text in PROMPTS:
        path = OUT_DIR / filename
        chunks = client.text_to_speech.convert(
            voice_id=settings.elevenlabs_tts_voice_id,
            text=text,
            model_id=settings.elevenlabs_tts_model,
            output_format="mp3_44100_128",
        )
        with path.open("wb") as f:
            for chunk in chunks:
                if chunk:
                    f.write(chunk)
        paths.append(path)
    return paths


async def run_turn(ws: websockets.ClientConnection, pcm: bytes, label: str) -> dict[str, Any]:
    """Run one audio turn over websocket and collect response summary.

    Args:
        ws: Open websocket connection.
        pcm: PCM16 bytes to stream.
        label: Human-readable label for output.

    Returns:
        Summary with event types, transcript, assistant text, and optional error.
    """

    chunk_size = 3200  # 100ms @ 16kHz mono s16le
    seq = 0
    for offset in range(0, len(pcm), chunk_size):
        chunk = pcm[offset : offset + chunk_size]
        await ws.send(
            json.dumps(
                {
                    "type": "audio.frame",
                    "seq": seq,
                    "pcm16_b64": base64.b64encode(chunk).decode("ascii"),
                    "sample_rate_hz": 16000,
                    "channels": 1,
                }
            )
        )
        seq += 1
        await asyncio.sleep(0.1)

    await asyncio.sleep(0.35)
    await ws.send(json.dumps({"type": "audio.commit", "seq": seq}))

    events: list[str] = []
    transcript: str | None = None
    assistant_text: str | None = None
    error: dict[str, Any] | None = None

    started = time.monotonic()
    while time.monotonic() - started < 120:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=3)
        except TimeoutError:
            continue

        payload = json.loads(raw)
        event_type = payload.get("type")
        if isinstance(event_type, str):
            events.append(event_type)

        if event_type == "transcript.final":
            transcript = payload.get("text")
        if event_type == "assistant.text.final":
            assistant_text = payload.get("text")
        if event_type == "error":
            error = payload
            break
        if event_type == "turn.completed":
            break

    return {
        "label": label,
        "events": events,
        "transcript": transcript,
        "assistant": assistant_text,
        "error": error,
    }


def parse_tool_logs(start_time: datetime) -> list[dict[str, Any]]:
    """Parse structured logs for tool operations since `start_time`.

    Args:
        start_time: Lower bound timestamp.

    Returns:
        List of matching tool log payload summaries.
    """

    matches: list[dict[str, Any]] = []
    for path in glob.glob("logs/structured/*.jsonl"):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ts_raw = payload.get("timestamp")
                    if not isinstance(ts_raw, str):
                        continue

                    try:
                        ts = datetime.fromisoformat(ts_raw)
                    except ValueError:
                        continue

                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=UTC)
                    if ts < start_time:
                        continue

                    if payload.get("component") != "voice_agent":
                        continue
                    if payload.get("operation") not in {"search_knowledge", "search_web"}:
                        continue

                    matches.append(
                        {
                            "timestamp": payload.get("timestamp"),
                            "operation": payload.get("operation"),
                            "context_data": payload.get("context_data"),
                        }
                    )
        except FileNotFoundError:
            continue

    matches.sort(key=lambda item: item["timestamp"])
    return matches


async def run_e2e() -> int:
    """Run the complete voice + tool e2e check.

    Returns:
        Exit code (`0` on success, `1` on failure).
    """

    start_time = datetime.now(UTC)
    user_id, token = ensure_user_and_favorite()
    print(f"user_id={user_id}")

    mp3_paths = generate_prompt_mp3s()
    pcm_inputs = [mp3_to_pcm16(path) for path in mp3_paths]

    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=20) as client:
        response = client.post(
            f"{API_BASE}/api/voice/sessions",
            headers=headers,
            json={"sample_rate_hz": 16000},
        )
        response.raise_for_status()
        session = response.json()

    print(f"session_id={session['session_id']}")
    ws_url = f"{WS_BASE}{session['websocket_path']}"
    results: list[dict[str, Any]] = []
    async with websockets.connect(ws_url, additional_headers=headers, open_timeout=10) as ws:
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"ready={ready}")
        await ws.send(json.dumps({"type": "session.start", "session_id": session["session_id"]}))

        for (filename, _), pcm in zip(PROMPTS, pcm_inputs, strict=True):
            result = await run_turn(ws, pcm, filename)
            results.append(result)
            await asyncio.sleep(0.5)

    for result in results:
        print(f"\nTURN {result['label']}")
        print(f"events={result['events']}")
        print(f"transcript={result['transcript']}")
        if result["assistant"]:
            print(f"assistant={str(result['assistant'])[:260]}")
        if result["error"]:
            print(f"error={result['error']}")

    tool_logs = parse_tool_logs(start_time)
    print("\nTOOL_LOGS")
    for entry in tool_logs:
        print(entry)

    operations = {entry["operation"] for entry in tool_logs}
    success = "search_knowledge" in operations and "search_web" in operations
    if not success:
        print("\nRESULT=FAIL (missing one or both tool operations)")
        return 1

    print("\nRESULT=PASS")
    return 0


def main() -> None:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description="Voice tool e2e integration test")
    _ = parser.parse_args()
    raise SystemExit(asyncio.run(run_e2e()))


if __name__ == "__main__":
    main()
