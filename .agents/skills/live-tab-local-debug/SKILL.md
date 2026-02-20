---
name: live-tab-local-debug
description: Debug the iOS Live tab end-to-end on localhost, including ElevenLabs voice checks and simulator UI validation via axe.
---

# Live Tab Local Debug

## Purpose
Use this skill to debug the iOS Live tab end-to-end on localhost with:
- ElevenLabs STT/TTS-backed backend checks
- tool usage checks (`SearchKnowledge`, `SearchWeb`)
- simulator UI validation through `axe`

## Prerequisites
- API server running on `http://127.0.0.1:8000`
- iOS simulator booted
- `axe` CLI installed and available in `PATH`
- ElevenLabs env configured in server shell:
  - `ELEVENLABS_API_KEY`
  - `ELEVENLABS_VOICE_ID` (optional override)
  - `ELEVENLABS_TTS_MODEL` (optional override)
- Python env available via `uv`

## Fast Path
Run:

```bash
.agents/live-tab-local-debug/scripts/run_live_tab_debug.sh
```

Artifacts are written to `/tmp/live_tab_debug_<timestamp>/`:
- `voice_tools_e2e.txt`
- `axe_smoke.txt`
- `axe/*` (screenshots, UI trees, sim logs)

## What This Validates
1. `scripts/voice_tools_e2e.py`
   - Creates a test session
   - Generates prompt mp3s via ElevenLabs
   - Streams turns over `/api/voice/ws`
   - Verifies both `search_knowledge` and `search_web` traces
2. `scripts/axe_simulator_smoke.sh`
   - Launches app
   - Navigates to Knowledge -> Live
   - Taps Connect
   - Captures screenshots/UI/logs

## Manual Checks After Script
1. Open the latest `axe/03_connected.png` and confirm Live connected state.
2. Inspect `voice_tools_e2e.txt` for `RESULT=PASS`.
3. If greeting is missing, check:
   - `voice_tools_e2e.txt` for intro/turn events
   - server logs for `operation=create_session` with `pending_intro=true`
   - simulator logs for websocket errors

## Useful Commands
Check backend health:

```bash
curl -sS http://127.0.0.1:8000/health
```

Force first-time greeting for a user (local SQLite):

```bash
uv run python - <<'PY'
import sqlite3
conn = sqlite3.connect("news_app.db")
conn.execute("update users set has_completed_live_voice_onboarding = 0 where id = 1")
conn.commit()
print("reset complete")
PY
```

Run just voice e2e:

```bash
uv run python scripts/voice_tools_e2e.py
```

Run just simulator smoke:

```bash
scripts/axe_simulator_smoke.sh --capture-logs
```
