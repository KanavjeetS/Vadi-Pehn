# Skill: Build Voice Gateway (LiveKit + Whisper + Kokoro)

## Objective
As the Voice Pipeline Engineer, implement the real Voice Gateway service:
LiveKit WebRTC transport, Silero VAD, `WhisperSTTClient`, and
`KokoroTTSClient` — currently interface-only stubs in
`src/sibling/voice/stt.py` and `tts.py` — without changing
`voice_session.py`'s orchestration of them.

## Rules of Engagement
- `STTClient`/`TTSClient` interfaces are frozen. Implement them, don't
  redesign them — `VoiceSession` and `orchestration_graph.py` already
  depend on the existing method signatures and are tested against them.
- Multilingual coverage is a hard gate, not a nice-to-have (PRD §6.4):
  before this segment is marked complete, Kokoro's language coverage must
  be validated against the project's actual target languages. If coverage
  is insufficient, this must be flagged and the fallback (Piper, or a
  regional TTS model) evaluated — do not silently ship English-only.
- The latency budget table in PRD §6.2 is the acceptance criterion.

## Instructions
1. Stand up LiveKit locally per PRD's `voice_agent.py` pattern, updated to
   fix the same fail-closed and correctness issues already fixed elsewhere
   in this codebase (e.g. don't let a VAD/STT error silently produce an
   empty transcript that then gets treated as a real (empty) user turn).
2. Implement `WhisperSTTClient.transcribe()` against a local
   faster-distil-whisper-large-v3 endpoint, populating `TranscriptResult`
   exactly as `MockSTTClient` already does (same dataclass shape).
3. Implement `KokoroTTSClient.synth_chunk()` with `KOKORO_STREAM=true` and
   `KOKORO_CHUNK_SIZE=50` per PRD's tuning guidance, returning `AudioChunk`
   with a real (not estimated) `duration_ms_estimate`.
4. Wire per-chunk output-safety gating exactly as `orchestration_graph.py`
   already does for the mock path — verify this isn't bypassed anywhere in
   the LiveKit event loop (GUARDRAILS.md G-004).
5. Build a load test that measures actual p50/p95 against the PRD §6.2
   budget table under simulated concurrent sessions, and report a
   pass/fail per stage (VAD, STT, safety, LLM-first-sentence, TTS-first-
   chunk, end-to-end).
6. Run the multilingual go/no-go check from PRD §6.4 before declaring this
   segment complete; document the result in `docs/system-design.md`'s
   traceability appendix via `@doc-keeper`.
