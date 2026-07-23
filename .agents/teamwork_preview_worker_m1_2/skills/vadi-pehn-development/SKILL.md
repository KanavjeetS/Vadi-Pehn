---
name: vadi-pehn-development
description: >
  Guide the creation, modification, and debugging of every service in the
  Vadi-Pehn Virtual Sibling-Mentor Platform. Covers LangGraph orchestration,
  CrewAI panels, NeMo Guardrails safety proxy, Postgres/pgvector memory,
  Langfuse observability, voice pipeline (LiveKit/Whisper/Kokoro), and
  the full 9-persona agent team workflow.
---

# Vadi-Pehn Development Skill

This skill activates for ANY coding task in the Vadi-Pehn project. Read it
in full before writing a single line. Rules in `AGENTS.md` still apply.

---

## 0. Before ANY Code

1. **Identify the PRD/SD section** your task implements. Say it explicitly.
   Do not proceed if you cannot identify it.
2. **Identify the owning persona** from `AGENTS.md`'s table. You are operating
   as that persona for this task.
3. **Check if the task touches a child-safety non-negotiable** (AGENTS.md Part 1).
   If yes, say so explicitly. This affects review routing.
4. **Apply Karpathy Principle 1 (Think Before Coding)**:
   State your assumptions. Name ambiguities. Stop if confused.

---

## 1. Project Architecture Reference

```
vadi-pehn/
├── services/
│   ├── api-gateway/
│   ├── orchestration/       ← LangGraph, personas/, tools/
│   ├── voice-gateway/       ← LiveKit, Silero VAD, Whisper STT, Kokoro TTS
│   ├── safety-proxy/        ← NeMo Guardrails, config.yml, rails/, actions.py
│   ├── panel-service/       ← CrewAI crews, diversity selector
│   ├── memory-service/      ← asyncpg, pgvector, RLS-scoped connections
│   ├── governance-service/  ← Consent Ledger, Safety Incident Queue
│   ├── ingestion-service/   ← MinIO, olmOCR, PII redaction
│   └── dashboard-bff/
├── db/migrations/           ← SQL + pgTAP test files co-located
├── eval/safety_redteam_corpus/
├── research/findings/
└── docs/
```

---

## 2. Segment → Persona → Skill Mapping

| Segment | Persona | Skill reference |
|---|---|---|
| `orchestration` | `@backend-engineer` | See §3 below |
| `memory-service` | `@data-engineer` | See §4 below |
| `safety-proxy` | `@safety-engineer` | See §5 below |
| `voice-gateway` | `@voice-engineer` | See §6 below |
| `panel-service` | `@backend-engineer` | See §7 below |
| `governance-service` | `@safety-engineer + @data-engineer` | See §8 below |
| `ingestion-service` | `@data-engineer` | See §9 below |
| `guardian-dashboard` | `@backend-engineer` | See §10 below |

---

## 3. Orchestration Service (LangGraph)

**Core graph spine — do not break this sequence:**
```
check_input_safety → [SAFE] → retrieve_memory → generate_and_check_output → write_memory
                  → [UNSAFE] → handle_unsafe_input (fixed script, no LLM)
```

**Rules:**
- New nodes go AFTER `check_input_safety` returning SAFE. Never before or parallel.
- Any node producing user-facing text MUST pass through `safety_client.check_output`.
- New state fields go in `TurnState` TypedDict with populate/consume comment.
- Every new node needs a unit test in `tests/test_orchestration_graph.py`.
- Persona system prompts are loaded from `services/orchestration/personas/<name>.jinja2`.
  Never inline a prompt string in Python.

**Langfuse instrumentation (required on every LLM call):**
```python
from langfuse.decorators import observe

@observe(name="generate_reply")
async def generate_and_check_output(state: TurnState) -> TurnState:
    # tenant_id and learner_id are passed as metadata, hashed
    ...
```

---

## 4. Memory Service (Postgres + pgvector + RLS)

**Every query pattern:**
```python
async with pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute("SET LOCAL app.current_tenant_id = $1", tenant_id)
        await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        await conn.execute("SET LOCAL hnsw.max_scan_tuples = 20000")
        # now execute your query
```

**Rules:**
- `FORCE ROW LEVEL SECURITY` must be confirmed in the migration itself,
  not assumed from the CREATE POLICY.
- Every migration has a co-located pgTAP test file proving tenant isolation.
- `PostgresMemoryStore` implements the same abstract interface as `InMemoryVectorStore`
  (don't delete the in-memory version — it stays as the test backend).

---

## 5. Safety Proxy (NeMo Guardrails)

**Endpoints to implement (exact shape — do not deviate):**
```
POST /internal/v1/safety/check-input
  body: { learner_id, message_text, age_band }
  → { verdict: "safe"|"unsafe_self_harm"|"unsafe_general"|"classifier_unavailable",
      taxonomy_code: "S6"|...|null }
  timeout: 3000ms → return classifier_unavailable on any timeout/exception

POST /internal/v1/safety/check-output
  body: { learner_id, draft_reply_text }
  → { verdict: "safe"|"unsafe_general"|"classifier_unavailable" }
```

**Hard rules:**
- The safety proxy NEVER delivers the supportive script on self-harm. It only returns
  the verdict. The Orchestration Service handles the response.
- On `unsafe_self_harm`, Orchestration calls Governance Service to create an incident.
- On voice path: check-output is called PER SENTENCE CHUNK, not after the full reply.

---

## 6. Voice Gateway (LiveKit + Whisper + Kokoro)

**Turn pipeline:**
```
Child speaks → Silero VAD (end-of-turn detection)
  → Whisper-large-v3 (faster-distil) STT → transcript
  → Orchestration /voice-turn webhook
       → Safety check-input
       → LLM streaming (sentence-by-sentence)
       → Safety check-output PER CHUNK (dedicated low-latency classifier replica)
       → Kokoro-82M TTS → audio chunk
  → Voice Gateway streams audio to child
```

**Latency budget (p95, PRD §6.2):**
- STT: ≤500ms
- Safety check-input: ≤300ms
- LLM first-chunk: ≤1200ms
- Safety check-output (per chunk): ≤300ms
- TTS first-chunk: ≤500ms
- Total: ≤3700ms

---

## 7. Panel Service (CrewAI)

**Panel composition rule (PRD §5.1):**
- Fetch `learner_interest_profile.top_interests` from Memory Service.
- Match against `professional_personas.profession_taxonomy_code`.
- Select: top-2 matches + 1 diversity-constraint persona.
- If no clean taxonomy match: set `panel_status = no_match_fallback`, queue for
  nightly curation review. Do NOT fabricate a match.
- Max active relationships per learner: 3 (relationship bandwidth, PRD §5.1).

**CrewAI pattern:**
```python
# Each persona is a CrewAI Agent loaded from the persona directory
# Fact validation agent always runs AFTER the career suggestion agent
# Output Guard validates all career claims against approved_fact_source_ref
```

---

## 8. Governance Service

**Critical facts:**
- **Separate Postgres instance** from Memory Service. Never propose merging.
- Safety incidents have a 7-year legal hold — no cascade delete on this table ever.
- The `sla_deadline = NOW() + INTERVAL '15 minutes'` is set at incident creation.
- When Governance DB is unreachable: Orchestration falls back to direct SMS webhook
  (not silence — this is more severe than Memory DB failure).

---

## 9. Ingestion Service

**Document flow:**
```
Upload → MinIO → PII redaction → olmOCR (Qwen2-VL-7B)
       → if confidence < 0.85: discrepancy queue (do NOT write to learner profile)
       → if confidence ≥ 0.85: call Memory Service to write (checks Governance consent first)
```

---

## 10. Guardian Dashboard (BFF)

- Read-optimized views. Does NOT own source-of-truth data.
- Consent management routes through Governance Service.
- All session-level reads are RLS-scoped.

---

## 11. Langfuse Observability (All Services)

Required trace tags on every LLM call and DB query in the hot path:
- `tenant_id` — hashed (SHA-256 truncated) for non-incident telemetry
- `learner_id` — hashed
- `session_id` — raw (session is not PII)
- `service_name` — e.g. `orchestration`, `panel-service`
- `safety_verdict` — input + output verdicts as custom metadata

Alert thresholds (System Design §8):
- Safety SLA breach: page if `sla_deadline` passes without acknowledgment
- Voice p95 latency > 3700ms sustained for 5 min: alert
- RLS zero-row anomaly: alert if tenant-scoped query with historical results returns zero

---

## 12. Model Training Plan

| Agent | Model | Training |
|---|---|---|
| Sibling Mentor | Llama-3.3-70B FP8 | RLHF on child-safe corpus; Aegis 2.0 alignment |
| Career Panel | MoE architecture | Expert routing: career × geography × skill_pathway domains |
| Ingestion/OCR | SLM (Qwen2-VL-7B) | olmOCR fine-tune on regional academic document layouts |

**Non-negotiable:** No real learner data for training. Synthetic corpus only, clearly labeled.

---

## 13. Build Segment Execution Checklist

For every `/build-segment <name>`:
- [ ] `@architect`: confirm scope against PRD/SD section
- [ ] Owning persona: implement per the segment guide in §3–10 above
- [ ] `@backend-engineer`: write tests (`pytest -v`, all green)
- [ ] `@qa-auditor`: run `audit-tenant-isolation.md` if data tables touched
- [ ] `@qa-auditor`: run `audit-safety-failclosed.md` if LLM generation touched
- [ ] Fix all issues from QA (rework loop, max 5 iterations)
- [ ] `@doc-keeper`: update PRD/SD/README for any resolved open questions
- [ ] Report: what was built, test count, GUARDRAILS.md entries added

---

## 14. References

- [System Design](file:///d:/Vadi%20Bhen/SystemDesign.md) — Authoritative technical spec
- [PRD](file:///d:/Vadi%20Bhen/PRD.md) — Product & governance requirements
- [AGENTS.md](file:///d:/Vadi%20Bhen/.agents/AGENTS.md) — Rules & persona definitions
- [GUARDRAILS.md](file:///d:/Vadi%20Bhen/.agents/GUARDRAILS.md) — Safety lessons log
- All 14 build skills: `d:\Vadi Bhen\vadi-pehn-antigravity\.agents\skills\`
- All 5 workflows: `d:\Vadi Bhen\vadi-pehn-antigravity\.agents\workflows\`
