## Purpose
Implements the real-time voice experience by streaming STT input, orchestrating LLM calls, and emitting ElevenLabs TTS audio back to clients.

## Key Files
- `agent_streaming.py` – wraps the conversational agent flow used in the live voice/chat experience.
- `elevenlabs_streaming.py` – ElevenLabs-specific helpers to open STT connections, stream chunks, and emit TTS payloads.
- `orchestrator.py` – `VoiceConversationOrchestrator` that buffers speech deltas, tracks latency, and persists turns.
- `persistence.py` and `session_manager.py` – store voice turn history and manage session/launch metadata.
- `__init__.py` – package marker.

## Main Types/Interfaces
- `VoiceConversationOrchestrator` with `stream_voice_agent_turn` integration to coordinate STT ↔ LLM ↔ TTS.
- `VoiceSessionManager` helpers for message history management plus persistence helpers.
- `ElevenLabsSttCallbacks` and streaming helper functions that break agent output into TTS-friendly chunks.

## Dependencies & Coupling
Talks to ElevenLabs SDK (`elevenlabs_streaming`), Langfuse tracing (via core logging), the database for persistence, and the LLM agent infrastructure under `app.services.admin_conversational_agent`/`llm_agents`. Voice is gated by settings such as `voice_trace_logging` and ElevenLabs keys.

## Refactor Opportunities
The orchestrator still retains a great deal of state (chunk buffers, queues, event emitters); splitting into smaller components (e.g., a dedicated chunker/state tracker) would allow unit testing without spinning up asyncio queues.

Reviewed files: 6
