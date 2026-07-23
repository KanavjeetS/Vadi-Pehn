# BRIEFING — 2026-07-22T10:37:02Z

## Mission
Investigate voice-gateway (Kokoro/ElevenLabs TTS), Child UI (/child/), and AI Pipeline Memory RAG (LangGraph turn execution, pgvector, ContextualRetrievalService) and document exact file locations, configurations, and key findings.

## 🔒 My Identity
- Archetype: Codebase Researcher (Voice & RAG Pipeline)
- Roles: Read-only investigator
- Working directory: d:\Vadi Bhen\.agents\teamwork_preview_explorer_m3_1
- Original parent: 58da31d6-c265-49c8-836a-51d2b1c2326c
- Milestone: m3_1

## 🔒 Key Constraints
- Read-only investigation — do NOT implement code changes to project source files
- Follow System Prompt protection and Vadi-Pehn workspace rules
- Handoff report format: Observation, Logic Chain, Caveats, Conclusion, Verification Method

## Current Parent
- Conversation ID: 58da31d6-c265-49c8-836a-51d2b1c2326c
- Updated: 2026-07-22T10:37:02Z

## Investigation State
- **Explored paths**:
  - `services/config.py`
  - `services/voice-gateway/src/voice_gateway/` (`tts.py`, `providers.py`, `pipeline.py`, `main.py`)
  - `webapp/child/` (`index.html`, `child.js`)
  - `services/orchestration/src/orchestration/` (`main.py`, `graph.py`)
  - `services/memory-service/src/memory_service/` (`store.py`, `context.py`, `retrieval.py`)
  - `db/migrations/002_learner_memory_rls.sql`
- **Key findings**:
  - Voice Gateway: Kokoro & ElevenLabs configured (`ELEVENLABS_VOICE_ID: 2EiwWnXFnvU5JabPnv8n` Indian female voice). ElevenLabs uses `stability: 0.7`. Kokoro uses fallback `Piper` for Punjabi (`pa`). Explicit `temperature=0.7`, speed, warmth parameters are missing in Kokoro/ElevenLabs call payloads.
  - Child UI: SVG interactive character, Web Speech API mic button, floating ambient stars CSS animation, quick action chips. Missing letter-by-letter typing animation, Web Audio API waveform visualizer, and explicit child-facing AI identity disclosure banner.
  - Orchestration & Memory RAG: LangGraph turn execution in `graph.py` enforcing strict node spine (`check_input_safety` -> `retrieve_memory` -> `detect_panel_trigger` -> `generate_reply` -> `check_output_safety` -> `write_memory`). `learner_memories` table uses pgvector HNSW index (`m=16`, `ef_construction=256`) with `ENABLE` + `FORCE ROW LEVEL SECURITY`. Hybrid RAG combines dense HNSW, sparse BM25, RRF, and cross-encoder reranking.
- **Unexplored areas**: None within the scope of m3_1 investigation mission.

## Key Decisions Made
- Structured findings into handoff report `d:\Vadi Bhen\.agents\teamwork_preview_explorer_m3_1\handoff.md`.

## Artifact Index
- ORIGINAL_REQUEST.md — Original prompt
- BRIEFING.md — Context index
- progress.md — Step progress heartbeat
- handoff.md — Comprehensive 5-component handoff report
