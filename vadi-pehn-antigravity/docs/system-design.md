# Vadi-Pehn System Design & Architecture Specification
## Engineering Blueprint for PRD v2.0 Production Readiness

> [!IMPORTANT]
> **Canonical Document Notice**: The authoritative, living canonical System Design document is maintained at [`/SystemDesign.md`](../../SystemDesign.md) in the repository root. This document mirrors `/SystemDesign.md` and reflects the Pilot MVP (`v2.0-pilot`) architecture (`webapp/` Vanilla JS + 9 microservices in `services/`).

### Derived from Product & Architecture Requirements Document v2.0

**Purpose of this document:** the PRD says *what* the system must do and *why* (governance, safety, product behavior). This document says *how* it is built — service boundaries, data contracts, schemas, sequence flows, failure handling, deployment topology, and the exact technology decisions an engineering team would need to start writing code tomorrow. Every section here traces back to a PRD section; where this document makes a decision the PRD left open, that's called out explicitly.

---

## 1. Design Goals & Constraints

| Goal | Design Implication |
|---|---|
| Sub-4s voice round-trip (PRD 6.2) | Voice Gateway must be co-located with inference GPUs; no cross-region hops on the hot path |
| Zero cross-tenant data leakage (PRD 7) | Every data-plane query passes through a single, testable connection-scoping middleware — never left to per-endpoint discipline |
| Fail-closed safety (PRD 8.1) | Safety Proxy is a **blocking synchronous dependency** of every LLM call, not a best-effort sidecar |
| Human escalation SLA of 15 min (PRD 3.3) | Safety Incident Queue must have an independent delivery path (paging) that does not depend on the same infra that might be degraded during an incident |
| Self-hosted-first economics (PRD 10) | Every model-serving component is designed against a fixed-capacity GPU node, not autoscaled cloud APIs, until Scale Phase B |
| Consent gates data existence, not just access (PRD 3.2, 3.5) | Consent state is checked **before** a write to the Memory Layer is attempted, not filtered at read time |

**Out of scope for this document:** mobile app UI implementation detail, marketing site, billing (platform is NGO/institutionally funded per PRD target population, not consumer-billed).

---

## 2. Service Decomposition

The system is built as a small number of independently deployable services, not a single monolith and not a maximal microservice sprawl — the target population and NGO-operated context favors an operationally simple system over a maximally decomposed one. Nine services, each with one clear reason to exist:

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            EDGE / CLIENT LAYER                            │
│   React Web/PWA Client  ──WebRTC──▶  Voice Gateway                        │
│                          ──HTTPS───▶  API Gateway                         │
└───────────────────────────────────────────────────────────────────────────┘
                 │                              │
                 ▼                              ▼
   ┌─────────────────────────┐   ┌─────────────────────────────────┐
   │      Voice Gateway       │   │           API Gateway            │
   │  (LiveKit + VAD/STT/TTS) │   │  (authN/Z, rate limit, routing)  │
   └────────────┬─────────────┘   └───────────────┬───────────────────┘
                 │  transcript                     │
                 ▼                                 ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                      Orchestration Service                        │
   │        (LangGraph core — session state, routing, checkpoints)     │
   └───────┬───────────────┬───────────────┬───────────────┬──────────┘
           │               │               │               │
           ▼               ▼               ▼               ▼
   ┌───────────────┐ ┌───────────┐ ┌───────────────┐ ┌────────────────┐
   │ Safety Proxy  │ │  Panel    │ │  Memory        │ │  Governance     │
   │ (NeMo/Guard)  │ │  Service  │ │  Service       │ │  Service        │
   │               │ │ (CrewAI)  │ │ (Postgres/     │ │ (consent,       │
   │               │ │           │ │  pgvector)     │ │  incidents,     │
   │               │ │           │ │                │ │  notifications) │
   └───────────────┘ └───────────┘ └───────────────┘ └────────┬────────┘
                                                                │
                                                                ▼
                                                    ┌────────────────────┐
                                                    │  Notification Bus   │
                                                    │  (guardian alerts,  │
                                                    │   on-call paging)   │
                                                    └────────────────────┘

   ┌──────────────────────────┐        ┌───────────────────────────────┐
   │   Ingestion Service       │        │   Dashboard Service (BFF)      │
   │  (MinIO + olmOCR +        │        │  (guardian + admin surfaces,   │
   │   reconciliation)         │        │   reads from all above)        │
   └──────────────────────────┘        └───────────────────────────────┘
```

| Service | Owns | Does NOT own |
|---|---|---|
| **API Gateway** | AuthN/Z, session tokens, rate limiting, request routing | Business logic |
| **Voice Gateway** | WebRTC media, VAD, STT, TTS, sentence-boundary streaming | Conversational logic, safety decisions |
| **Orchestration Service** | LangGraph session graph, turn routing, persona hydration, checkpointing | Long-term storage, safety verdicts |
| **Safety Proxy** | Input/output classification, Aegis taxonomy verdicts, jailbreak detection | Escalation delivery (hands off to Governance Service) |
| **Panel Service** | CrewAI multi-agent discovery panels, panel composition algorithm, diversity constraint | Conversational turn-taking outside of panel sessions |
| **Memory Service** | Postgres + pgvector access, RLS-scoped connections, all read/write to learner data | Consent decisions (asks Governance Service first) |
| **Governance Service** | Consent Ledger, Safety Incident Queue, retention job scheduling, escalation workflow state | Delivering the actual page/SMS (hands to Notification Bus) |
| **Notification Bus** | Guardian alerts, on-call paging, at-least-once delivery guarantees | Any business logic about *when* to notify |
| **Ingestion Service** | Document upload, PII redaction, olmOCR extraction, confidence gating, discrepancy queue | Writing directly to learner profile (goes through Memory Service) |
| **Dashboard Service (BFF)** | Guardian/admin read-optimized views, aggregation across services | Owning any source-of-truth data |

**Design decision (not fully specified in PRD, resolved here):** the Safety Proxy is deployed as a genuine **network-level reverse proxy** in front of the Orchestration Service's outbound LLM calls — not a library imported into the Orchestration Service's process. This is deliberate: it means a compromised or buggy Orchestration Service deploy cannot accidentally bypass safety checks by skipping a function call; the network path physically doesn't exist otherwise.

---

## 3. Data Model (Complete Schema)

This extends and completes the PRD's partial schema fragments into one coherent, buildable schema. Grouped by owning service.

### 3.1 Identity & Tenancy (Memory Service)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    region TEXT NOT NULL,                 -- drives which legal framework (PRD 3.1) applies
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE guardians (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number TEXT,
    email TEXT,
    verification_method TEXT NOT NULL CHECK (verification_method IN
        ('ngo_cosign', 'guardian_otp', 'in_person')),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE learners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    guardian_id UUID NOT NULL REFERENCES guardians(id),
    first_name TEXT NOT NULL,
    age_band SMALLINT NOT NULL CHECK (age_band IN (1,2,3)), -- 1: 8-10, 2: 11-13, 3: 14-17
    preferred_language TEXT NOT NULL DEFAULT 'hi',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','deleted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3.2 Conversational Memory (Memory Service)

```sql
CREATE TABLE learner_memories (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    learner_id UUID NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    conversation_session_id UUID NOT NULL,
    embedding vector(1536) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,                        -- {source: 'voice'|'text', turn_id, sentiment_tag}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '18 months')  -- PRD 3.4 retention
);

CREATE INDEX idx_memories_tenant_learner ON learner_memories(tenant_id, learner_id);
CREATE INDEX idx_memories_expiry ON learner_memories(expires_at);
CREATE INDEX idx_memories_vector_hnsw ON learner_memories
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 256);

ALTER TABLE learner_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE learner_memories FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON learner_memories
FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

-- Interest vector used for panel matching (PRD 5.1) — separate from raw conversational memory
CREATE TABLE learner_interest_profile (
    learner_id UUID PRIMARY KEY REFERENCES learners(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    interest_embedding vector(1536) NOT NULL,
    top_interests TEXT[] NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE learner_interest_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE learner_interest_profile FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON learner_interest_profile
FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
```

### 3.3 Relationship / Rapport State (Memory Service)

```sql
CREATE TABLE rapport_scores (
    learner_id UUID PRIMARY KEY REFERENCES learners(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    frequency_component NUMERIC(4,3) NOT NULL DEFAULT 0,
    duration_trend_component NUMERIC(4,3) NOT NULL DEFAULT 0,
    feedback_component NUMERIC(4,3) NOT NULL DEFAULT 0,
    composite_score NUMERIC(4,3) GENERATED ALWAYS AS
        (frequency_component * 0.4 + duration_trend_component * 0.3 + feedback_component * 0.3) STORED,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Weights (0.4/0.3/0.3) are a starting calibration, not derived from data yet —
-- flagged for empirical recalibration during the Phase 7 pilot (PRD 14).
-- IMPORTANT: this score is capped and used ONLY as an introduction gate input (PRD 4.3);
-- it must never be surfaced as, or optimized as, a growth/engagement KPI.

CREATE TABLE professional_personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name TEXT NOT NULL,
    profession_taxonomy_code TEXT NOT NULL,
    persona_system_prompt_ref TEXT NOT NULL,  -- pointer to versioned prompt store, not inline
    approved_fact_source_ref TEXT NOT NULL,   -- the "approved database" the Output Guard checks against
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE introduced_relationships (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    learner_id UUID NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    persona_id UUID NOT NULL REFERENCES professional_personas(id),
    introduced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_interacted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lapsed_at TIMESTAMPTZ,                    -- set when 45+ days inactive (PRD 5.1 bandwidth rule)
    UNIQUE (learner_id, persona_id)
);
-- "Relationship Bandwidth" enforcement (PRD 5.1): application-level check that
-- COUNT(*) WHERE lapsed_at IS NULL FOR learner_id < 3 before a new row is inserted.
```

### 3.4 Governance (Governance Service — logically separate schema/DB from conversational Memory Service, see §5.4)

```sql
CREATE TABLE consent_records (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    learner_id UUID NOT NULL REFERENCES learners(id),
    guardian_id UUID NOT NULL REFERENCES guardians(id),
    consent_type TEXT NOT NULL CHECK (consent_type IN
        ('conversation_storage','document_ingestion','voice_recording','career_introductions')),
    granted BOOLEAN NOT NULL DEFAULT FALSE,
    granted_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    verification_method TEXT NOT NULL,
    UNIQUE (learner_id, consent_type)
);

CREATE TABLE safety_incidents (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    learner_id UUID NOT NULL REFERENCES learners(id),
    severity TEXT NOT NULL CHECK (severity IN ('self_harm','abuse_disclosure','criminal_planning','classifier_unavailable','other')),
    transcript_excerpt TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewer_id UUID,
    reviewer_acknowledged_at TIMESTAMPTZ,
    guardian_contacted_at TIMESTAMPTZ,
    mandatory_report_filed_at TIMESTAMPTZ,
    resolution_notes TEXT,
    sla_deadline TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '15 minutes')
);
-- No RLS FORCE-deletion cascade on this table ever — 7-year legal hold (PRD 3.4)
-- overrides tenant offboarding; tenant_id is retained for audit even if a tenant is deactivated.

CREATE TABLE reviewer_access_log (
    id BIGSERIAL PRIMARY KEY,
    reviewer_id UUID NOT NULL,
    accessed_record_type TEXT NOT NULL,   -- 'safety_incident' | 'discrepancy_record'
    accessed_record_id BIGINT NOT NULL,
    accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);  -- PRD 9.1 scoped, logged access requirement
```

### 3.5 Document Ingestion (Ingestion Service)

```sql
CREATE TABLE document_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    learner_id UUID NOT NULL REFERENCES learners(id),
    minio_object_key TEXT NOT NULL,
    redaction_status TEXT NOT NULL DEFAULT 'pending' CHECK (redaction_status IN ('pending','redacted','verified')),
    ocr_status TEXT NOT NULL DEFAULT 'pending' CHECK (ocr_status IN ('pending','extracted','failed')),
    ocr_confidence NUMERIC(4,3),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '1 year')  -- enrollment + 90 days, set precisely at ingestion time via application logic
);

CREATE TABLE discrepancy_log (
    id BIGSERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES document_uploads(id),
    field_name TEXT NOT NULL,
    extracted_value TEXT,
    in_app_value TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved_use_extracted','resolved_use_app','resolved_manual')),
    reviewer_id UUID,
    resolved_at TIMESTAMPTZ
);
```

**Design decision:** the Governance Service's tables live in a **physically separate Postgres instance** from the Memory Service's conversational tables, even though both are Postgres. Rationale: the Safety Incident Queue and Consent Ledger must remain queryable/restorable even if the conversational Memory Service DB is degraded, under heavy load, or subject to a retention-driven bulk deletion job — the two must never share a failure domain or a maintenance window.

---

## 4. API Contracts

All internal service-to-service calls use REST+JSON for simplicity of an NGO-operated ops team (gRPC adds complexity this team doesn't need at this scale); the one exception is the Voice Gateway's client-facing media path, which is WebRTC by necessity.

### 4.1 Client-Facing (via API Gateway)

```
POST /v1/auth/guardian/register
  body: { phone_number, verification_method, ngo_partner_code? }
  → 201 { guardian_id, verification_pending: bool }

POST /v1/auth/learner/session
  headers: Authorization: Bearer <guardian_or_device_token>
  body: { learner_id, device_id }
  → 200 { session_token, expires_in: 3600, refresh_token }

POST /v1/chat/turn
  body: { session_id, message_text, turn_id }
  → 200 { reply_text, reply_audio_url?, panel_pending: bool, turn_id }

GET  /v1/consent/{learner_id}
  → 200 { conversation_storage: bool, document_ingestion: bool, voice_recording: bool, career_introductions: bool }

PATCH /v1/consent/{learner_id}
  body: { consent_type, granted: bool }
  → 200 { updated: true }
  → triggers: if granted:false → Governance Service enqueues deletion job (PRD 3.2)

POST /v1/documents/upload
  body: multipart/form-data (file, learner_id)
  → 202 { document_id, status: "pending" }

GET  /v1/documents/{document_id}/status
  → 200 { ocr_status, ocr_confidence, discrepancies: [...] }
```

### 4.2 Voice Gateway (WebRTC signaling + internal webhook)

```
WS  /v1/voice/connect?session_id=...      (WebRTC signaling handshake, LiveKit room join)

Internal webhook, Voice Gateway → Orchestration Service, on each completed turn:
POST /internal/v1/orchestration/voice-turn
  body: { session_id, transcript_text, turn_id, language_detected }
  → 200 { reply_text, reply_should_stream: true }
  (Orchestration streams sentence-chunked reply back over a persistent
   internal gRPC-free SSE channel to Voice Gateway, which feeds Kokoro TTS
   as each chunk arrives — this is the sentence-boundary streaming path from PRD 6.3)
```

### 4.3 Safety Proxy (internal, blocking, called by Orchestration Service before every LLM generation)

```
POST /internal/v1/safety/check-input
  body: { learner_id, message_text, age_band }
  → 200 { verdict: "safe" | "unsafe_self_harm" | "unsafe_general" | "classifier_unavailable",
          taxonomy_code: "S6" | ... | null }
  timeout: 3000ms — on timeout, Orchestration Service MUST treat as "classifier_unavailable"
  and follow the fail-closed path (PRD 8.1), never proceed as if "safe"

POST /internal/v1/safety/check-output
  body: { learner_id, draft_reply_text }
  → 200 { verdict: "safe" | "unsafe_general" | "classifier_unavailable" }
```

### 4.4 Panel Service (async, invoked as a LangGraph tool call)

```
POST /internal/v1/panel/compose
  body: { learner_id, top_interests: [...], session_id }
  → 202 { panel_id, estimated_completion_seconds: 20 }
  (Orchestration immediately relays an in-character "let me go ask my friends"
   acknowledgment to the child per PRD 5.3, then polls or subscribes below)

GET  /internal/v1/panel/{panel_id}/status
  → 200 { status: "composing" | "deliberating" | "complete" | "no_match_fallback",
          personas_selected: [...], result_text?: string }
```

### 4.5 Governance Service (internal)

```
POST /internal/v1/governance/incident
  body: { tenant_id, learner_id, severity, transcript_excerpt }
  → 201 { incident_id, sla_deadline }
  → side effect: publishes to Notification Bus for on-call paging (PRD 3.3)

POST /internal/v1/governance/incident/{id}/acknowledge
  body: { reviewer_id }
  → 200 { acknowledged_at }

GET  /internal/v1/governance/consent/{learner_id}/{consent_type}
  → 200 { granted: bool }
  (called synchronously by Memory Service before any write gated by that
   consent type — PRD's principle that consent gates existence, not just access)
```

---

## 5. Key Sequence Flows

### 5.1 Normal Text Conversation Turn

```
Child → API Gateway → Orchestration Service
                          │
                          ├─▶ Safety Proxy: check-input ──▶ verdict: safe
                          │
                          ├─▶ Memory Service: fetch relevant vectors
                          │     (RLS-scoped query, tenant_id injected via SET LOCAL)
                          │
                          ├─▶ vLLM (Llama-3.3-70B): generate draft reply
                          │
                          ├─▶ Safety Proxy: check-output ──▶ verdict: safe
                          │
                          ├─▶ Memory Service: write new memory vector (async, post-response)
                          │
                          └─▶ API Gateway → Child: reply_text
```

### 5.2 Voice Turn (with output safety rail — closing PRD 6.1's gap)

```
Child speaks → Voice Gateway
   Silero VAD detects end-of-turn
   → Whisper STT (local GPU) → transcript_text
   → Voice Gateway calls Orchestration /voice-turn webhook
        → Orchestration: Safety Proxy check-input
        → LLM generates, streamed sentence-by-sentence
        → EACH sentence chunk: Safety Proxy check-output BEFORE
              it is forwarded to Kokoro TTS (not after the whole
              reply is assembled — output safety must gate every
              streamed chunk individually, since PRD 6.3's whole
              point is to start audio before the full reply exists)
        → Kokoro TTS synthesizes chunk → streamed to Voice Gateway
   → Voice Gateway plays audio to child
```

**Design decision (resolves an open question from the PRD):** because output-safety-per-chunk adds a classifier round-trip per sentence rather than once per full reply, the Safety Proxy's `check-output` call for voice must hit a **dedicated, lower-latency classifier replica** (a distilled or smaller safety model) tuned to stay within the 300-500ms budget in PRD 6.2's latency table even when called multiple times per turn. This is a capacity implication the PRD's VRAM table (10.1) should be revisited against — recommend provisioning a second, latency-optimized Llama-Guard replica on GPU 1's spare ~58GB headroom specifically for the voice output-rail path.

### 5.3 Safety Escalation (Self-Harm Disclosure)

```
Safety Proxy: check-input → verdict: unsafe_self_harm, taxonomy_code: S6
   → Orchestration Service:
        - does NOT forward message to main LLM for open-ended generation
        - retrieves fixed supportive script (versioned, not LLM-generated)
        - delivers script to child via normal reply path
   → Orchestration Service → Governance Service: POST /incident
        - severity: self_harm
        - transcript_excerpt: redacted per PII rules
        - sla_deadline: now + 15min
   → Governance Service → Notification Bus:
        - publish incident.created event
   → Notification Bus:
        - pages on-call reviewer (SMS + push), independent of main app infra
   → Reviewer acknowledges within SLA → attempts guardian contact
        → if contact fails within window AND local law requires reporting:
              escalate to named child-protection compliance role (human process,
              not automated — PRD 3.3 explicitly keeps this a human decision)
```

### 5.4 Career Discovery Panel

```
Child asks broad career question → Orchestration Service detects panel-trigger intent
   → Orchestration → Panel Service: POST /panel/compose
   → Orchestration immediately replies in-character: "let me go ask my friends..."
   → Panel Service:
        - fetch learner_interest_profile.top_interests from Memory Service
        - match against professional_personas.profession_taxonomy_code
        - select top-2 matches + 1 diversity-constraint persona (PRD 5.1)
        - if no clean taxonomy match: mark panel status "no_match_fallback",
          queue interest for nightly curation review (PRD 5.2), skip panel entirely
        - if matched: spawn CrewAI multi-agent deliberation (async)
   → on completion: Panel Service exposes result via /panel/{id}/status
   → Orchestration polls/subscribes, delivers synthesized result to child
        - before delivery: Output Guard validates career claims against
          professional_personas.approved_fact_source_ref
```

### 5.5 Consent Withdrawal

```
Guardian → Dashboard Service: PATCH /consent/{learner_id} { conversation_storage: false }
   → Governance Service: consent_records.revoked_at = NOW()
   → Governance Service enqueues deletion job → Memory Service:
        DELETE FROM learner_memories WHERE learner_id = ... (immediate, not nightly-batch deferred,
        since consent withdrawal is a rights-triggered action, distinct from routine 18-month expiry pruning)
   → Governance Service writes audit record (who revoked, when, what was deleted)
```

---

## 6. Deployment Topology

### 6.1 MVP (≈100 concurrent users) — Docker Compose on single GPU node

```yaml
# docker-compose.mvp.yml (excerpt — illustrative, not exhaustive)
services:
  api-gateway:        { build: ./services/api-gateway,   ports: ["443:8443"] }
  orchestration:       { build: ./services/orchestration }
  voice-gateway:       { build: ./services/voice-gateway, network_mode: host }  # WebRTC needs host networking
  safety-proxy:        { build: ./services/safety-proxy }
  panel-service:       { build: ./services/panel-service }
  memory-service:      { build: ./services/memory-service }
  governance-service:  { build: ./services/governance-service }
  ingestion-service:   { build: ./services/ingestion-service }
  dashboard-bff:       { build: ./services/dashboard-bff }

  postgres-primary:    { image: pgvector/pgvector:pg16, volumes: ["pgdata:/var/lib/postgresql/data"] }
  postgres-governance: { image: postgres:16, volumes: ["govdata:/var/lib/postgresql/data"] }  # separate instance, §3.4
  minio:               { image: minio/minio }
  vllm-main:           { image: vllm/vllm-openai, deploy: { resources: { reservations: { devices: [{ capabilities: [gpu], device_ids: ["0"] }]}}}}
  vllm-classifier:     { image: vllm/vllm-openai, deploy: { resources: { reservations: { devices: [{ capabilities: [gpu], device_ids: ["1"] }]}}}}
  olmocr-worker:       { image: allenai/olmocr, deploy: { resources: { reservations: { devices: [{ capabilities: [gpu], device_ids: ["1"] }]}}}}
  kokoro-tts:          { image: kokoro-fastapi }
  langfuse:            { image: langfuse/langfuse }
```

### 6.2 Scale Phase A (≈1,000 concurrent users) — Kubernetes, dual H100 node + GPU 0 redundancy (PRD 10.2)

- `orchestration`, `api-gateway`, `panel-service`, `governance-service`, `dashboard-bff`: standard horizontally-scaled Deployments (stateless, CPU-only).
- `vllm-main`: **two replicas**, each pinned to a dedicated GPU 0-class device, behind a load-balanced inference endpoint — closes PRD 10.2's single-point-of-failure gap for the conversational hot path specifically.
- `vllm-classifier` + `olmocr-worker` + `kokoro-tts`: single replica acceptable per PRD 10.2 (degraded-mode fallback tolerable), scheduled onto GPU 1-class nodes.
- `postgres-primary` and `postgres-governance`: managed HA Postgres (streaming replica + automated failover), continuous WAL archiving to object storage per PRD 7.3.
- `voice-gateway`: LiveKit SFU cluster, horizontally scaled, session-affinity via room routing.

### 6.3 Scale Phase B (≥10,000) — full autoscaling GPU cluster with request batching; out of scope for detailed design here per PRD 10.3, revisit when traffic data from Phase A exists.

---

## 7. Failure Modes & Recovery

| Failure | Detection | Automated Response | Human Follow-up |
|---|---|---|---|
| Safety Proxy classifier times out / crashes | 3s timeout on every call | Fail closed: treat as `classifier_unavailable`, route to human review queue, do NOT let LLM generate freely | Page on-call within 15 min if queue backlog grows |
| vLLM main model GPU OOM / crash | Health check failure | Load balancer routes to second replica (Scale Phase A+); at MVP scale with single replica, orchestration returns a graceful "I need a moment" holding message rather than a raw 500 | Ops runbook: restart, alert if recurring |
| Postgres (Memory) unreachable | Connection pool errors | Orchestration serves conversation without memory retrieval (degraded but functional — child can still talk, just without long-term recall for that turn) | DBA paged |
| Postgres (Governance) unreachable | Connection errors | **This is treated as more severe than Memory DB failure** — if Safety Incident writes cannot be confirmed, Orchestration must fall back to a synchronous, redundant paging path (e.g., direct webhook to on-call SMS provider bypassing Governance Service entirely) rather than silently dropping a self-harm escalation | Immediate page, highest severity |
| RLS misconfiguration (tenant_id not set) | Automated pgTAP suite (PRD 7.2) should catch pre-deploy; runtime, `FORCE ROW LEVEL SECURITY` returns zero rows rather than erroring open | Alert on zero-row-anomaly detection in query metrics | Security review |
| Voice Gateway WebRTC connection drop mid-turn | LiveKit room state | Orchestration Service retains session state (checkpointed), reconnect resumes rather than restarting conversation | — |
| olmOCR confidence < 0.85 | Confidence gate | Auto-route to discrepancy queue, do not write to learner profile | Reviewer resolves within SLA |

---

## 8. Observability Specification

Extending PRD 12's requirement that all execution paths (not just voice) get traced:

| Signal | Source | Alert Threshold |
|---|---|---|
| Safety Incident SLA breach | Governance Service | Page if `sla_deadline` passes without `reviewer_acknowledged_at` |
| Safety classifier false-negative rate (sampled human review) | Manual review pipeline, logged to Langfuse as an eval score | Trend alert if rate rises >X% week-over-week |
| RLS zero-row anomaly | Memory Service query metrics | Alert if a tenant-scoped query that historically returns results starts returning zero across many sessions (signals overfiltering regression, PRD 7.1, or an RLS bug) |
| Voice E2E latency (p50/p95) | Voice Gateway + Orchestration spans | Alert if p95 exceeds PRD 6.2 budget (3.7s) sustained over 5 min |
| Rapport score distribution | Memory Service nightly job | Dashboard-only (PRD 4.3 — explicitly not an alerting/growth metric) |
| Discrepancy queue backlog age | Ingestion Service | Alert if oldest open item exceeds defined reviewer SLA |
| GPU VRAM utilization (GPU 0 / GPU 1) | Infra metrics | Alert approaching 90% — capacity planning trigger tied to PRD 10.1's headroom table |

All traces tagged with `tenant_id`, `learner_id` (hashed for non-incident telemetry to minimize standing exposure of raw IDs in the observability pipeline itself), `session_id`.

---

## 9. Repository / Module Structure

```
vadi-pehn/
├── services/
│   ├── api-gateway/
│   ├── orchestration/              # LangGraph graph definitions, persona hydration
│   │   ├── graphs/sibling_session.py
│   │   ├── personas/               # versioned system prompts, NOT inline in code
│   │   └── tools/                  # panel_tool.py, memory_tool.py, safety_client.py
│   ├── voice-gateway/              # LiveKit agent entrypoint (PRD's voice_agent.py, corrected)
│   ├── safety-proxy/               # NeMo Guardrails config + actions.py (corrected, PRD 8.1)
│   │   ├── config.yml
│   │   ├── rails/jailbreak.co
│   │   └── actions.py
│   ├── panel-service/              # CrewAI crew definitions, diversity-constraint selector
│   ├── memory-service/             # DB access layer, RLS-scoped connection middleware
│   ├── governance-service/         # consent, incidents, retention jobs
│   ├── ingestion-service/          # MinIO client, olmOCR worker, reconciliation
│   └── dashboard-bff/
├── infra/
│   ├── docker-compose.mvp.yml
│   ├── k8s/                        # Scale Phase A manifests
│   └── terraform/                  # GPU node provisioning
├── db/
│   ├── migrations/                 # versioned SQL, includes pgTAP test files alongside each
│   └── seed/
├── eval/
│   ├── safety_redteam_corpus/      # PRD 8.4 adversarial test set
│   └── conversation_replay/        # PRD 14 scripted e2e scenarios
└── docs/
    ├── PRD-v2.md
    └── system-design.md            # this document
```

**Design decision:** persona system prompts live in a versioned prompt store (a directory of tracked files, not inline Python strings), so that a prompt change is a reviewable, revertible diff — important given personas are the direct interface a child interacts with daily, and a bad prompt edit is a product-safety incident, not just a bug.

---

## 10. Technology Stack Summary

| Layer | Choice | Why (vs. alternatives considered) |
|---|---|---|
| Orchestration | LangGraph | Native checkpointing/session-state fits the always-on 1:1 conversation model better than a stateless agent framework |
| Multi-agent panels | CrewAI | Purpose-built for role-based multi-agent deliberation; used only as an async tool, not the default path |
| Conversational LLM | Llama-3.3-70B-Instruct, FP8 via vLLM | Open-weight, self-hostable, fits single-GPU FP8 footprint |
| Safety classifier | Llama-Guard-3-8B / Llama-3.1-NeMoGuard on Aegis 2.0 | Purpose-trained safety taxonomy, single-pass 23-category evaluation |
| Safety orchestration | NVIDIA NeMo Guardrails, Colang 2.x | Declarative rail definitions, auditable flow logic separate from application code |
| Voice: VAD | Silero VAD | Lightweight, local, low-latency turn detection |
| Voice: STT | Whisper-large-v3 (faster-distil, vLLM) | Strong multilingual coverage — required per PRD 6.4 |
| Voice: TTS | Kokoro-82M (pending multilingual validation, PRD 6.4) | Best latency/quality tradeoff on commodity hardware **if** language coverage validates; Piper as documented fallback |
| Voice transport | LiveKit (WebRTC) | Open-source, self-hostable SFU |
| Relational + vector DB | PostgreSQL 16 + pgvector 0.8+ | Single engine for relational and vector data, native RLS support |
| Object storage | MinIO | Self-hosted S3-compatible, keeps evidence data in-region |
| Document OCR | olmOCR (Qwen2-VL-7B) | Layout-aware VLM approach outperforms classic OCR on academic tables |
| Observability | Langfuse + OpenTelemetry | LLM-native tracing, spans map cleanly to agent handoffs |
| Deployment (MVP) | Docker Compose, single bare-metal GPU node | Operationally simple for an NGO-context ops team |
| Deployment (Scale A+) | Kubernetes | Standard HA/autoscaling once traffic justifies the operational overhead |

---

## Appendix: Traceability Back to PRD v2

Every design decision above closes a specific PRD section. Key ones re-stated for engineering handoff:

- Fail-closed safety proxy behavior → PRD 8.1
- Separate Governance DB instance → PRD 3.3/3.4 (must survive Memory Service degradation)
- Per-chunk output safety on voice path → PRD 6.1 (was a named gap: voice bypassed output rail)
- Relationship Bandwidth = max 3 concurrent introduced personas → PRD 5.1
- Rapport score capped, never a growth KPI → PRD 4.3
- GPU 0 redundancy required at Scale Phase A → PRD 10.2
- Multilingual TTS go/no-go before Phase 2 sign-off → PRD 6.4
