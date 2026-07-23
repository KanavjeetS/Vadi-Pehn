## 2026-07-22T05:41:27Z

<USER_REQUEST>
You are worker_m3_1, a specialist worker (@voice-engineer & @frontend-engineer) for Milestone 3 (Child Companion Portal, ElevenLabs Indian Female Voice & Rich Animations — Requirement R3).
Your working directory is `d:\Vadi Bhen\.agents\worker_m3_1`.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Task Scope & Requirements:
1. ElevenLabs / Kokoro Voice Configuration:
   - Check `services/config.py`: Ensure `ElevenLabsSettings` and `VoiceSettings` expose Indian female voice parameters (`voice_id="2EiwWnXFnvU5JabPnv8n"`, `temperature=0.7`, speed=1.0, warmth=0.75). Ensure defaults work seamlessly.
   - Check `services/voice-gateway/src/voice_gateway/providers.py` (`ElevenLabsTTSService`) and `tts.py` (`KokoroTTSService`): Ensure synthesis calls forward parameter settings (`temperature=0.7`, stability=0.7, etc.) and fallback gracefully to Kokoro (`hi_female` profile) or Piper (`pa_in.onnx` for Punjabi) if ElevenLabs key is not set or fails.
2. Child Companion Portal (`webapp/child/index.html` & `webapp/child/child.js`):
   - Typing animation: Add a letter-by-letter typing animation in `child.js` when Vadi's response text is rendered in `#transcript-bubble` / `#caption-sub`.
   - Audio Waveform Visualizer: Add an HTML5 Canvas visualizer `#audio-waveform-canvas` in `webapp/child/index.html` and wire it up in `child.js` using Web Audio API (`AudioContext`, `AnalyserNode`) during speech input (mic active) and audio playback (`speakReply`).
   - AI Identity Disclosure Banner: Add an explicit visual banner at the top of `webapp/child/index.html` per child safety guardrails (`GUARDRAILS.md`): e.g. `<div id="ai-disclosure-banner" class="ai-disclosure-banner">🤖 Hi! I'm Vadi, your AI sibling-mentor</div>` with clear styling matching the portal theme.
   - Ensure chat and voice turns send `POST /api/v1/turn` and `POST /api/v1/voice/tts` smoothly.
3. Build & Test:
   - Run `pytest services/voice-gateway/tests/` using run_command.
   - Document all changes and test outputs in `d:\Vadi Bhen\.agents\worker_m3_1\handoff.md`.

</USER_REQUEST>
