# Handoff Report — Codebase Research (Voice & RAG Pipeline)

**Agent ID**: `teamwork_preview_explorer_m3_1`  
**Role**: Read-only Codebase Researcher (Voice & RAG Pipeline)  
**Date**: 2026-07-22  

---

## 1. Observation

### A. `services/voice-gateway` TTS & Voice Configuration
1. **Centralized Configuration (`services/config.py`)**:
   - `ElevenLabsSettings` (`lines 210-216`):
     ```python
     class ElevenLabsSettings(BaseSettings):
         api_key: str = Field("", alias="ELEVENLABS_API_KEY")
         voice_id: str = Field("2EiwWnXFnvU5JabPnv8n", alias="ELEVENLABS_VOICE_ID")  # Indian female calm voice
     ```
   - `VoiceSettings` (`lines 218-235`):
     ```python
     class VoiceSettings(BaseSettings):
         vad_model_path: str = Field("models/silero_vad.onnx", alias="VAD_MODEL_PATH")
         whisper_url: str = Field("http://localhost:8003", alias="WHISPER_URL")
         whisper_model: str = Field("faster-distil-whisper-large-v3", alias="WHISPER_MODEL")
         kokoro_url: str = Field("http://localhost:8004", alias="KOKORO_URL")
         piper_path: str = Field("piper", alias="PIPER_PATH")
         voice_classifier_url: str = Field("http://vllm-classifier-voice:8002", alias="VOICE_CLASSIFIER_URL")
         orchestration_url: str = Field("http://orchestration:8000", alias="ORCHESTRATION_URL")
         gateway_url: str = Field("http://voice-gateway:8000", alias="VOICE_GATEWAY_URL")
     ```
2. **Kokoro TTS Implementation (`services/voice-gateway/src/voice_gateway/tts.py`)**:
   - `KokoroTTSService.synthesize()` (`lines 79-116`):
     ```python
     if language == "pa":
         return await self.fallback_service.synthesize(text, language)
     ...
     response = await client.post(
         f"{self.kokoro_url}/v1/audio/speech",
         json={
             "input": text,
             "voice": "en_us_male" if language == "en" else "hi_female",
             "response_format": "wav",
         },
         timeout=2.0,
     )
     ```
   - `PiperTTSService.synthesize()` (`lines 43-77`): Executes subprocess `piper --model models/pa_in.onnx --output-raw` as fallback for Punjabi (`pa`).
3. **ElevenLabs TTS Implementation (`services/voice-gateway/src/voice_gateway/providers.py`)**:
   - `ElevenLabsTTSService.synthesize()` (`lines 67-108`):
     ```python
     url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs.voice_id}/stream"
     body = {
         "text": text,
         "model_id": "eleven_multilingual_v2",
         "voice_settings": {
             "stability": 0.7,
             "similarity_boost": 0.75,
             "style": 0.0,
             "use_speaker_boost": True
         }
     }
     ```
   - Parameter Observation: ElevenLabs specifies `stability: 0.7`, but parameters for `temperature=0.7`, speed, and warmth are not configurable in `KokoroTTSService` payload or `ElevenLabsSettings`.

### B. Child UI (`/child/` Portal Interface)
1. **HTML Structure (`webapp/child/index.html`)**:
   - Top Header (`lines 279-297`): Back button (`←`), Streak badge (`★ 5 day streak`), Grown-up button (`📞 Grown-up` linking to `/guardian/`).
   - Ambient Particle Animation (`lines 34-50, 271-276`): CSS `.ambient-stars` with floating star particles animated via `@keyframes floatTwinkle 4s ease-in-out infinite alternate;`.
   - SVG Interactive Character (`lines 148-151, 302-319`): `#vadi-svg` SVG avatar with floating body animation `@keyframes floatBody 3.5s ease-in-out infinite`, clickable eyes, cheeks, and mouth.
   - Microphone Trigger Button (`lines 188-203, 327-329`): `#mic-trigger-btn` with `@keyframes pulseMicBtn 1.2s ease-in-out infinite alternate;` when listening.
   - Action Chips (`lines 331-337`): Quick buttons (`✨ Cheer me on`, `🧭 Meet a friend`, `🔮 Go offline`, `💙 Safety check`, `🔮 Say goodbye`).
   - UI Badges & Elements (`lines 253-265, 340`): `#transcript-bubble` for chat text and `⚡ Vadi-Pehn` branding badge.
2. **JavaScript Logic (`webapp/child/child.js`)**:
   - Web Speech API STT (`lines 110-158`): `toggleVoice()` uses `window.SpeechRecognition` / `webkitSpeechRecognition` set to `lang = 'hi-IN'`, calling `quickAction(transcript)`.
   - Turn API Request (`lines 56-108`): `quickAction()` sends `POST /api/v1/turn` with `{session_id, tenant_id, learner_id, age_band, message_text, language: 'hi'}`. Fail-closed error handling preserves safety on turn failure.
   - ElevenLabs Audio Playback (`lines 161-201`): `speakReply()` sends `POST /api/v1/voice/tts` and plays base64 MP3 audio response using HTML5 `Audio`.
   - SVG Mouth Animation (`lines 36-50`): `setMouthState()` manipulates SVG `#vadi-mouth` path for `'speaking'`, `'listening'`, and `'idle'`.
3. **Missing Features / Gaps in Child UI**:
   - Typing Animation: `child.js` sets `captionSub.innerText = "Vadi is thinking..."` and displays text response directly without letter-by-letter typing animation.
   - Audio Waveform Visualizer: No Web Audio API / HTML5 Canvas audio waveform visualizer component present during listening/speech playback.
   - Child-Facing AI Identity Disclosure: Line 340 contains `⚡ Vadi-Pehn`, but there is no explicit visual banner disclosing "I am an AI assistant" on the UI (though backend injects AI disclosure text every 5 turns).

### C. LangGraph Turn Execution & Memory RAG Pipeline
1. **Orchestration FastAPI Router (`services/orchestration/src/orchestration/main.py`)**:
   - Endpoint `POST /internal/v1/orchestration/turn` (`lines 113-130`): Validates internal service token and calls `graph.run_turn()`.
   - Endpoint `POST /internal/v1/orchestration/stream` (`lines 133-163`): Streams SSE deltas for voice gateway pipeline.
   - Lifespan Setup (`lines 77-103`): Instantiates `asyncpg.Pool`, `NomicEmbeddingClient`, `HybridRetrievalEngine`, `PostgresMemoryStore`, `ContextualRetrievalService`, `AsyncMemoryWriter`, and `OrchestrationGraph`.
2. **LangGraph Graph Spine (`services/orchestration/src/orchestration/graph.py`)**:
   - Graph Execution Sequence (`lines 6-12, 613-656`):
     `check_input_safety` → `[SAFE]` → `retrieve_memory` → `detect_panel_trigger` → `generate_reply` → `check_output_safety` → `write_memory` / `create_governance_incident`.
   - Node `check_input_safety` (`lines 248-271`): Calls `safety_client.check_input`. Non-SAFE verdict routes to `handle_unsafe_input` (`lines 553-581`), producing a fixed supportive script without invoking LLM generation (GUARDRAIL G-001).
   - Node `retrieve_memory` (`lines 292-344`): Calls `context_service.get_contextual_summary()` (Hybrid RAG dense/sparse + RLS check).
   - Node `generate_reply` (`lines 373-447`): Loads JINJA2 persona template (`personas/sibling.jinja2`), calls `llm_client.generate(temperature=0.7)`. Appends AI identity disclosure every 5 turns or when child expresses attachment (`lines 432-441`).
   - Node `check_output_safety` (`lines 485-518`): Calls `safety_client.check_output`. On output safety violation, replaces draft with safe fallback (GUARDRAIL G-004).
   - Node `write_memory` (`lines 521-551`): Asynchronously persists turn conversation via `memory_writer.write_memory_async()` if consent is active.
3. **Database Schema & RLS (`db/migrations/002_learner_memory_rls.sql`)**:
   - Table `learner_memories` (`lines 13-25`): `id` (BIGSERIAL), `tenant_id` (UUID), `learner_id` (UUID), `conversation_session_id` (UUID), `embedding` (vector(1536)), `content` (TEXT), `metadata` (JSONB), `created_at`, `expires_at` (18-month rolling retention).
   - Index `idx_memories_vector_hnsw` (`lines 37-40`): `USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 256)`.
   - RLS Enforcement (`lines 46-57`):
     ```sql
     ALTER TABLE learner_memories ENABLE ROW LEVEL SECURITY;
     ALTER TABLE learner_memories FORCE ROW LEVEL SECURITY;
     CREATE POLICY tenant_isolation_policy ON learner_memories FOR ALL
     USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
     ```
4. **Memory Service & RAG Engine (`services/memory-service/src/memory_service/`)**:
   - `store.py` (`lines 38-157`): `PostgresMemoryStore.write()` and `query()` issue `SET LOCAL app.current_tenant_id = $1` inside an `asyncpg` transaction. `query()` also sets `hnsw.iterative_scan = relaxed_order` and `hnsw.max_scan_tuples = 20000`.
   - `retrieval.py` (`lines 42-151`): `HybridRetrievalEngine.retrieve_hybrid()` executes dense HNSW search (`1 - (embedding <=> $1::vector)`), sparse BM25 search (`ts_rank_cd`), Reciprocal Rank Fusion (`RRF`), and cross-encoder reranking under RLS.
   - `context.py` (`lines 43-176`): `ContextualRetrievalService.get_contextual_summary()` combines RAG items, filters out revoked consent categories, retrieves session history window, checks rapport score (`>= 70.0`), and matches career panel personas from `learner_interest_profile` if threshold is met.

---

## 2. Logic Chain

1. **Voice Pipeline Configuration & Parameters**:
   - Observation: `services/config.py` sets `ELEVENLABS_VOICE_ID = "2EiwWnXFnvU5JabPnv8n"` (Indian female calm voice). `ElevenLabsTTSService` (`providers.py:91-96`) configures `stability: 0.7`, `similarity_boost: 0.75`. `KokoroTTSService` (`tts.py:104-108`) sends `"voice": "hi_female"` for non-English synthesis and routes Punjabi (`pa`) to local Piper (`pa_in.onnx`).
   - Reasoning: The Indian female voice profile is present in both ElevenLabs and Kokoro configurations. However, parameters such as `temperature=0.7`, speed, and warmth are not exposed as configurable fields in `VoiceSettings` or passed to Kokoro/ElevenLabs API payloads.
2. **Child UI User Experience & Safety Compliance**:
   - Observation: `webapp/child/index.html` and `child.js` implement SVG avatar animations, ambient star particles (`floatTwinkle`), Web Speech API STT, and ElevenLabs audio playback.
   - Reasoning: While basic chat/voice messaging and SVG mouth animations work, three key UI features required by product specs are missing or incomplete:
     a) Letter-by-letter typing animation during response rendering.
     b) Audio waveform visualizer (Web Audio API / Canvas) showing real-time frequency data during recording or audio playback.
     c) Explicit child-facing AI identity disclosure banner on the portal interface.
3. **LangGraph & Memory RAG Pipeline Integrity**:
   - Observation: `services/orchestration/src/orchestration/graph.py` implements a strict 7-stage graph spine. `db/migrations/002_learner_memory_rls.sql` enforces `ENABLE` and `FORCE ROW LEVEL SECURITY`.
   - Reasoning: The RAG memory pipeline enforces multi-tenant database isolation at the PostgreSQL level via `SET LOCAL app.current_tenant_id = $1`. The `HybridRetrievalEngine` combines dense HNSW vector search (`m=16`, `ef_construction=256`), sparse BM25 text search, RRF fusion, and cross-encoder reranking. The safety proxy gates both input (`check_input_safety`) and output (`check_output_safety`), ensuring fail-closed safety compliance.

---

## 3. Caveats

1. **Unexecuted Live WebRTC Stream Testing**: Investigation was strictly read-only code analysis; active WebRTC LiveKit audio streaming sessions were not executed live against GPU containers (`vllm-main`, `kokoro-82m`).
2. **Database Connection Prerequisites**: Full end-to-end execution of `PostgresMemoryStore` requires running PostgreSQL instances on ports `5432` (Memory DB) and `5433` (Governance DB) with the `pgvector` extension installed.

---

## 4. Conclusion

The Vadi-Pehn Voice & Memory RAG codebase architecture is fully established and compliant with core security and safety non-negotiables. To achieve full feature completeness for Milestone 3 (Child Companion Portal & Voice Synthesis) and Milestone 6 (Memory RAG Verification), the following actionable fix strategy is recommended:

1. **Voice Gateway Enhancements**:
   - Extend `ElevenLabsSettings` and `VoiceSettings` in `services/config.py` to include `voice_temperature = 0.7`, `voice_speed = 1.0`, and `voice_warmth = 0.75`.
   - Update `ElevenLabsTTSService` and `KokoroTTSService` to pass these parameters to the respective synthesis endpoints.
2. **Child UI (`/child/`) Enhancements**:
   - Add a letter-by-letter typing animation helper in `child.js` when updating `transcript-bubble`.
   - Implement an HTML5 Canvas / Web Audio API waveform visualizer component in `index.html` linked to `AudioContext` during microphone recording and audio playback.
   - Add a prominent, child-friendly AI identity disclosure banner (e.g., `"🤖 Hi! I'm Vadi, your AI sibling-mentor"`) at the top of `index.html`.
3. **Memory RAG & LangGraph Integration**:
   - Ensure `start_desktop.py` mounts `/api/v1/turn` and `/api/v1/voice/tts` to route properly to `orchestration` and `voice-gateway` services.

---

## 5. Verification Method

To independently verify the observations and findings in this report:

1. **Inspect Voice Gateway & Configuration**:
   - File: `d:\Vadi Bhen\services\config.py` (`lines 210-235`)
   - File: `d:\Vadi Bhen\services\voice-gateway\src\voice_gateway\tts.py` (`lines 79-116`)
   - File: `d:\Vadi Bhen\services\voice-gateway\src\voice_gateway\providers.py` (`lines 67-108`)
2. **Inspect Child UI**:
   - File: `d:\Vadi Bhen\webapp\child\index.html` (`lines 34-50, 279-344`)
   - File: `d:\Vadi Bhen\webapp\child\child.js` (`lines 56-201`)
3. **Inspect LangGraph & Memory RAG**:
   - File: `d:\Vadi Bhen\services\orchestration\src\orchestration\graph.py` (`lines 248-551, 613-656`)
   - File: `d:\Vadi Bhen\db\migrations\002_learner_memory_rls.sql` (`lines 13-78`)
   - File: `d:\Vadi Bhen\services\memory-service\src\memory_service\store.py` (`lines 38-157`)
   - File: `d:\Vadi Bhen\services\memory-service\src\memory_service\retrieval.py` (`lines 42-151`)
   - File: `d:\Vadi Bhen\services\memory-service\src\memory_service\context.py` (`lines 43-176`)
4. **Run Existing Test Suite**:
   ```bash
   pytest services/voice-gateway/tests/test_pipeline.py
   pytest services/orchestration/tests/test_graph.py
   pytest services/memory-service/tests/test_contextual_rapport.py
   ```
