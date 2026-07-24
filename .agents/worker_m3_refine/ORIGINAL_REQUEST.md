## 2026-07-24T10:20:09Z
You are worker_m3_refine, a Voice & Frontend Core UX Worker for Milestone 3 of the Vadi-Pehn 10/10 Production MVP Refinement project.
Working Directory: d:\Vadi Bhen\.agents\worker_m3_refine\

Objective: Connect Child Companion UI to Real Voice Pipeline (Core Product UX)

Task Details:
1. Upgrade `webapp/child/child.js` to communicate directly with `/api/v1/voice/turn` (and `services/voice-gateway` endpoints).
2. Wire low-latency streaming audio / voice responses to drive Vadi avatar animation states seamlessly (`idle` -> `listening` -> `thinking` -> `speaking`).
3. Implement barge-in handling (user speaking or clicking stop interrupts current TTS audio playback cleanly) and live canvas audio waveform visualization during TTS playback (`#audio-waveform-canvas` or canvas visualizer).
4. Maintain strict fail-closed safety checking (`check_input_safety` and `check_output_safety`) on all voice turns (returning `unsafe_self_harm` or `unsafe_general` safety responses when safety filter triggers).
5. Ensure `services/voice-gateway` voice synthesis generates fluent Indian female voice profile (`voice_id="2EiwWnXFnvU5JabPnv8n"` ElevenLabs or Kokoro `hi_female` fallback) with AI identity disclosure banner.
6. Create/update automated unit/integration test suites (e.g. `services/voice-gateway/tests/` or `webapp/child/` tests) to programmatically verify:
   - Voice turn endpoints return valid audio responses with safety checks applied.
   - Fail-closed safety behavior triggers on unsafe prompts.
   - ElevenLabs / Kokoro voice synthesis providers instantiate and output audio data.
7. Run all voice gateway and API gateway test suites (`pytest services/voice-gateway/` and `pytest services/api-gateway/`) and verify 100% pass rate. Document exact commands and output in your handoff report.
