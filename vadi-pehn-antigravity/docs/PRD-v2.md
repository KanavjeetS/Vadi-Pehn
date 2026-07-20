# Vadi-Pehn Virtual Sibling-Mentor Platform
## Product & Architecture Requirements Document — Version 2.0

**Status:** Refined from v1 architectural blueprint. This revision closes governance, safety-of-relationship, capacity-planning, and operational gaps required before this system can responsibly serve minors in production.

**Scoring:** v1 was self-assessed at 8.2/10 against a stated 9.8/10 target, with three gaps named (voice UX, safety gateway, vector overfiltering). This revision closes those three **and** eleven additional gaps that are non-negotiable for a child-facing product: consent and legal compliance, data lifecycle, emotional-safety-of-the-relationship-itself, escalation delivery, multilingual coverage, capacity math, security hardening, testing strategy, observability completeness, guardian/admin product surface, cost model, a corrected code defect, an API contract layer, and a risk register. Target: **9.8/10**, with the remaining 0.2 intentionally held back for outcomes only a regional pilot can validate (real-world rapport calibration, on-the-ground reviewer staffing, in-market language quality).

---

## 0. Executive Summary

Vadi-Pehn ("elder sibling") is an agentic AI mentorship platform for under-resourced youth, pairing each child with a persistent "sibling" persona that provides daily companionship, learning structure, and — once trust is established — introductions to simulated career-professional mentors. The system is built to run entirely on self-hosted open-weight models to control unit economics and data exposure.

This document keeps the sound parts of the original architecture (stateless/stateful separation, RLS-enforced multi-tenancy, LangGraph-as-backbone with CrewAI-as-tool) and adds the governance, safety, and operational layers a system serving minors requires before it can go anywhere near real users.

**The single most important addition in this revision is Section 3: Child Safety, Consent & Regulatory Governance, and Section 4: Emotional Safety of the Relationship.** Everything else — voice, vector search, OCR, deployment — is infrastructure in service of a product that a child will talk to every day. That relationship needs its own guardrails, separate from content-safety filtering.

---

## 1. Scope, Target Users & Non-Goals

| Item | Definition |
|---|---|
| Primary user | Children ages 8–17 (age-banded: 8–10, 11–13, 14–17), under-resourced, may be semi-literate or bilingual |
| Secondary user | Guardian/parent or guardian-equivalent (NGO caseworker, teacher-of-record) — **must exist for every learner account** |
| Tertiary user | Human reviewers (discrepancy resolution, safety escalation triage), platform administrators |
| Non-goal | This is **not** a therapy or crisis-intervention product. It must recognize crisis signals and hand off to humans/hotlines — it must never attempt to counsel through a self-harm or abuse disclosure itself. |
| Non-goal | This is **not** a replacement for a human mentor or sibling. The product must actively avoid positioning itself as one — see Section 4. |
| Deployment geography assumption | South Asian region (Hindi/Punjabi/Urdu-adjacent naming convention implies India/Pakistan diaspora or in-region deployment) — **this must be confirmed**, since it determines the applicable legal framework (Section 3.1) and the language models required (Section 6.5). |

---

## 2. System Architecture Overview

Retained from v1, extended with an explicit API contract layer and a governance plane that was previously absent.

```
+-----------------------------------------------------------------------------------+
|                              GOVERNANCE PLANE (NEW)                               |
|   Consent Ledger | Data Retention Jobs | Guardian Notification Bus | Audit Log     |
+-----------------------------------------------------------------------------------+
                                          |
+-----------------------------------------------------------------------------------+
|                                 ORCHESTRATION PLANE                                |
|                      +----------------------------------------+                   |
|                      |             LangGraph Core             |                   |
|                      |  - Session State & Checkpointing        |                   |
|                      |  - Relational 1:1 Routing               |                   |
|                      +-------------------+--------------------+                   |
|                     Tool Call (Async)    |    Direct Handoff                      |
|                     +--------------------+--------------------+                   |
|                     v                                         v                   |
|         +-----------------------+                 +-----------------------+       |
|         |     CrewAI Engine     |                 |  Stateless Agent Pool |       |
|         | - Multi-Agent Panel   |                 | - Sibling Persona     |       |
|         | - Career Synthesis    |                 | - Domain Curators     |       |
|         +-----------------------+                 +-----------------------+       |
+-----------------------------------------------------------------------------------+
                          |  Internal API Contract (Section 5.4)
                          v
+-----------------------------------------------------------------------------------+
|                             MULTI-TENANT MEMORY LAYER                             |
|   PostgreSQL (Relational) | pgvector (Embeddings) | MinIO (Evidence Objects)      |
+-----------------------------------------------------------------------------------+
```

The addition of a **Governance Plane** as a first-class architectural layer — not a checkbox appended later — is deliberate. Consent state and retention rules gate what the Memory Layer is even allowed to store, so it sits architecturally above the memory layer, not beside it.

---

## 3. Child Safety, Consent & Regulatory Governance *(new)*

This section did not exist in v1. For a platform whose entire user base is minors, this is not optional scaffolding — it is a launch blocker.

### 3.1 Applicable Legal Frameworks

The platform must explicitly select and document its compliance target before Phase 0 begins, since it changes schema, consent flows, and data-residency requirements:

- **India — DPDP Act 2023**: requires verifiable parental/guardian consent before processing any child's personal data, restricts behavioral tracking/targeted advertising to minors entirely, and requires a Data Fiduciary to allow consent withdrawal.
- **US — COPPA**: if any US-resident minors are served, requires verifiable parental consent, a public-facing privacy policy, and strict limits on data retention and third-party disclosure.
- **EU — GDPR-K (Art. 8)**: if EU minors are in scope, requires consent from a holder of parental responsibility for children under 16 (member-state-dependent, 13–16).

**Decision required before Phase 0:** confirm deployment geography. The rest of this section assumes DPDP (India) as primary with COPPA-equivalent controls layered in for portability, since the naming convention and NGO/under-resourced-youth framing suggest South Asian deployment.

### 3.2 Guardian Consent & Account Model

- No learner account may be created without a linked, verified guardian account. Verification uses a lightweight but auditable method appropriate for low-resource settings (NGO caseworker co-signature, OTP to guardian phone, or in-person enrollment at a partner site) rather than a credit-card-based age gate, which excludes the target population.
- Consent is granular and stored in a **Consent Ledger** (new table, see 3.5): consent to (a) conversational data storage, (b) report-card/document ingestion, (c) voice recording, (d) introduction to simulated career-professional personas. Each is independently revocable.
- Consent withdrawal triggers a data-deletion job (Section 3.4), not just a flag flip.

### 3.3 Mandatory Reporting Obligations

The Aegis S6 (self-harm) and a new **Aegis-adjacent "abuse disclosure"** classifier path must route to a defined human workflow, not just a bot script. v1's Colang flow says the bot delivers a supportive script and calls `trigger_guardian_escalation` — but never defines what that function does. This revision specifies it:

1. Classifier flags `unsafe_self_harm` or `abuse_disclosure`.
2. Sibling persona delivers the fixed supportive script (retained from v1) and does **not** continue probing for details — over-collection of trauma detail from a minor by an AI is itself a harm.
3. `trigger_guardian_escalation` writes an incident record to a **Safety Incident Queue** (Postgres table, `safety_incidents`) with severity, timestamp, redacted transcript excerpt, and learner/tenant ID.
4. An on-call human reviewer (staffed 24/7 if the platform operates in the child's evening hours — this is when disclosures cluster) is paged via SMS/push within a **15-minute SLA** for `unsafe_self_harm`.
5. If the reviewer cannot make contact with the guardian within a defined window, and local law requires it (suspected abuse, not self-harm), the incident escalates to the platform's designated child-protection point of contact for mandatory reporting — this must be a named legal/compliance role, not an engineering ticket.
6. All Safety Incident Queue access is itself access-controlled and logged; reviewers must be background-checked given they will read minors' private disclosures.

### 3.4 Data Retention & Deletion

Absent from v1 entirely. Minimum requirements:

| Data Class | Retention | Deletion Trigger |
|---|---|---|
| Conversational memory vectors | 18 months rolling, or until learner ages out (18) | Nightly pruning job (mentioned in v1 roadmap but never specified — this is the spec) |
| Report card / evidence scans (MinIO) | Duration of enrollment + 90 days | Guardian consent withdrawal, or account closure |
| Safety incident records | 7 years (legal hold, non-negotiable regardless of other deletion) | Never auto-deleted |
| Voice audio (raw) | **Not retained** — transcribed then discarded within the session; only text-derived memory persists | Immediate, post-STT |

### 3.5 Consent Ledger Schema (extends v1's schema)

```sql
CREATE TABLE consent_records (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    learner_id UUID NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    guardian_id UUID NOT NULL REFERENCES guardians(id),
    consent_type TEXT NOT NULL CHECK (consent_type IN
        ('conversation_storage', 'document_ingestion', 'voice_recording', 'career_introductions')),
    granted BOOLEAN NOT NULL DEFAULT FALSE,
    granted_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    verification_method TEXT NOT NULL, -- e.g. 'ngo_cosign', 'guardian_otp', 'in_person'
    UNIQUE (learner_id, consent_type)
);

CREATE TABLE safety_incidents (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    learner_id UUID NOT NULL REFERENCES learners(id),
    severity TEXT NOT NULL CHECK (severity IN ('self_harm', 'abuse_disclosure', 'criminal_planning', 'other')),
    transcript_excerpt TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewer_id UUID,
    reviewer_acknowledged_at TIMESTAMPTZ,
    guardian_contacted_at TIMESTAMPTZ,
    resolution_notes TEXT
);
```

---

## 4. Emotional Safety of the Relationship Itself *(new)*

This is the gap that matters most and was entirely absent from v1. Content-safety filtering (Section 8) protects against harmful *inputs and outputs*. It does not protect against the harm of a lonely child forming an unhealthy emotional dependency on an always-available, always-agreeable AI "sibling" — which is a real, documented risk pattern with companion AI products, and this platform is explicitly designed to be relationally sticky (that is the entire premise of the rapport score).

Requirements:

1. **Persistent AI disclosure.** The sibling persona must periodically and naturally remind the child it is an AI, not a real sibling — not as a disclaimer wall, but woven into dialogue (e.g., when the child expresses strong attachment, "I really like being able to talk with you like this, even though I'm an AI, not a real person"). This must never be design-suppressed to increase engagement metrics.
2. **No isolation-reinforcing behavior.** The sibling must never discourage the child from spending time with real friends, family, or guardians, and must proactively surface those relationships positively — the opposite failure mode of a grooming pattern, applied here to prevent parasocial substitution rather than exploitation, but the design principle (never isolate a minor from trusted adults) is the same one that governs Section 3.
3. **Session-frequency and duration guardrails**, not just rapport-maximizing ones. The rapport score formula in v1 (`w1·Frequency + w2·Duration + w3·Feedback`) currently has no upper bound — as written it rewards engagement without limit, which is the wrong incentive for a product used by children. This revision adds:
   - A soft daily session cap with a gentle in-conversation wind-down ("let's pick this up tomorrow") rather than a hard cutoff.
   - Rapport score must **not** be optimized as a growth/engagement KPI internally; it exists only to gate the trust-based professional-introduction feature (its original, narrower purpose in v1), and this constraint should be documented as a product principle so it isn't quietly repurposed into an engagement-maximization signal later.
4. **Guardian visibility into relationship health**, not just academic metrics — the guardian dashboard (Section 11) must surface session frequency/duration trends so a guardian can notice if a child's usage pattern looks like withdrawal rather than healthy engagement.
5. **Escalation-aware tone.** If the safety classifier fires repeatedly for the same learner over a short window (even at sub-threshold severity), that pattern itself should be surfaced to a human reviewer — repeated near-misses are a signal worth a human's attention even if no single message crossed the line.

---

## 5. Orchestration & Agentic Execution Flow

Retained from v1 (LangGraph as always-on backbone, CrewAI invoked only as an async tool for discovery panels) with the following additions.

### 5.1 Dynamic Panel Composition (retained)

Panel selection by top-two interest match, capped at three professional personas, gated by:

```
Introduction Eligibility = Right Persona ∧ Sustained Interest ∧ Relationship Bandwidth ∧ (Rapport Score ≥ 0.6)
```

**Gap closed:** v1 never defines "Relationship Bandwidth." This revision defines it explicitly: **a learner may have at most 3 concurrently "introduced" professional personas active at once**; a 4th introduction requires the lowest-engagement existing one to lapse (no interaction for 45+ days) before a new one can be gated in. This prevents an unbounded roster of shallow relationships and keeps each professional relationship meaningful.

**Gap closed — panel diversity:** Interest-vector matching alone risks reinforcing stereotypes (e.g., consistently routing certain demographic patterns toward a narrow set of careers). The panel-selection algorithm must include a diversity constraint: at least one of the three matched personas is selected from outside the learner's top-matched cluster, refreshed periodically, so the platform exposes rather than narrows a child's sense of possible futures. This should be a tracked fairness metric, not an implicit hope.

### 5.2 Fallback Behavior *(new — undefined in v1)*

If a child's interest vector doesn't cleanly map to any entry in the professional taxonomy (common for very open-ended or unusual interests), the sibling persona should not force a mismatch. It should acknowledge the interest conversationally and queue it for the nightly curation job to research/expand the taxonomy, rather than presenting an ill-fitting professional as a forced match.

### 5.3 CrewAI Panel Latency UX *(new)*

Multi-agent deliberation is not instant. v1 never addresses what the child experiences while a panel runs. Requirement: the sibling persona gives an immediate, in-character acknowledgment ("let me go ask my friends about this — give me a bit") and the voice/UI shows a lightweight "thinking" state, rather than the child facing silence or a raw loading spinner for what could be 10–30+ seconds of multi-agent turns.

### 5.4 Internal API Contract *(new)*

v1 describes the planes in prose with no interface boundary. Minimum contract to build against:

| Boundary | Protocol | Key Payload |
|---|---|---|
| LangGraph → CrewAI | Async tool call (internal function call, not network hop, if co-located; gRPC if split) | `{learner_id, interest_vector_ref, top_k_interests, session_id}` |
| LangGraph → Memory Layer | Async Postgres/pgvector client, tenant-scoped connection (Section 7) | `{tenant_id, learner_id, query_embedding, k}` |
| Voice Service → Orchestration | WebRTC data channel + REST webhook for turn completion | `{session_id, transcript_text, turn_id}` |
| Safety Proxy → Orchestration | Synchronous HTTP, blocking (must return before LLM call proceeds) | `{verdict: safe|unsafe_self_harm|unsafe_general, taxonomy_code}` |
| Orchestration → Guardian Notification Bus | Async event (queue-based, at-least-once delivery) | `{incident_id, severity, learner_id, timestamp}` |

---

## 6. Voice-First Experience

Retained core pipeline (LiveKit + Silero VAD + Whisper STT + Kokoro TTS), corrected and extended.

### 6.1 Pipeline (retained, annotated)

```
Child Voice (WebRTC) → Silero VAD → Whisper STT (local) → Input Safety Filter
   → vLLM Sibling (Llama-3.3) → Output Safety Filter (NEW) → Kokoro TTS → Audio Stream
```

**Gap closed:** v1's cascading-pipeline diagram shows the input safety filter but omits the **output** safety rail from the voice path entirely, even though the text-mode diagram (Section 8) explicitly includes output-rail checking. Voice must not be a side-channel that bypasses output validation — this revision makes the output rail mandatory in both modes before TTS synthesis begins.

### 6.2 Latency Budget *(new — v1 asserts "<4s" with no breakdown)*

| Stage | Target (p50) | Target (p95) |
|---|---|---|
| VAD turn-detection | <200ms | <400ms |
| STT (Whisper, local GPU) | <400ms | <800ms |
| Safety input filter | <300ms | <500ms |
| LLM time-to-first-sentence | <900ms | <1.6s |
| TTS time-to-first-audio-chunk | <250ms | <400ms |
| **End-to-end (child stops talking → audio starts)** | **~2.1s** | **~3.7s** |

This gives the "<4s" claim in v1 an actual backing budget and a p95 tolerance, and identifies the LLM generation step as the largest lever if latency needs to come down further (batching, smaller draft model, speculative decoding).

### 6.3 Sentence-Boundary Streaming & Kokoro Tuning (retained from v1, correct as specified)

### 6.4 Multilingual Coverage *(new — critical gap)*

v1 names "bilingual children" as the exact problem voice should solve, then specifies Kokoro-82M as the TTS engine — which has strong English/limited multilingual voice coverage — and doesn't address STT/LLM language coverage at all. This revision requires, before Phase 2 is considered complete:

- Confirm target languages (per Section 1, likely Hindi/Punjabi/Urdu and code-switched English).
- Whisper-large-v3 has solid multilingual STT coverage for these languages — retained.
- **Kokoro-82M's language coverage must be validated against the target language list before it is locked in as the TTS engine.** If coverage is insufficient, alternatives (e.g., a regional open-weight TTS model, or accepting Piper's lower quality for full language coverage) must be evaluated as a fallback, and this decision documented as an explicit go/no-go checkpoint in Phase 2, not assumed.
- The main LLM's persona must be validated for natural code-switched conversation (a real bilingual child mixes languages mid-sentence) — this needs a dedicated eval set, not just a translation check.

### 6.5 Accessibility Beyond Voice *(new)*

Voice solves literacy access but not all accessibility needs. The underlying React UI (kept as fallback/companion to voice) should still meet WCAG 2.1 AA basics — readable font sizing for low-vision users, captions for TTS audio for deaf/hard-of-hearing children, and a non-voice text-input path always available as a fallback (network conditions in under-resourced settings may not reliably support WebRTC).

---

## 7. Multi-Tenant Memory Layer & Vector Search

Retained: Postgres RLS enforcement, `FORCE ROW LEVEL SECURITY`, transaction-scoped `SET LOCAL app.current_tenant_id`, and the pgvector 0.8.0 iterative-scan fix for HNSW overfiltering.

### 7.1 Corrected/Completed Overfiltering Config

v1 shows only `SET hnsw.max_scan_tuples = 20000;` as a global parameter and separately mentions `relaxed_order` without wiring the two together. The complete, correct session-scoped configuration is:

```sql
-- Per-session, inside the same transaction as the tenant context injection
SET LOCAL hnsw.iterative_scan = relaxed_order;
SET LOCAL hnsw.max_scan_tuples = 20000;
```

Both must be set **per-transaction** alongside `app.current_tenant_id`, not as a global server default — a global `max_scan_tuples` setting affects every tenant's query cost uniformly regardless of that tenant's actual data volume, which is wasteful for small tenants and potentially insufficient for large ones.

### 7.2 RLS Isolation Testing Strategy *(new — v1 names this as a Phase 7 task with no method)*

- Automated tenant-leakage test suite using `pgTAP`, run in CI on every schema migration: for each table with an RLS policy, assert that a session scoped to tenant A returns zero rows when queried for tenant B's known-seeded data.
- A dedicated adversarial test: attempt the query **without** setting `app.current_tenant_id` at all (simulating a connection-pool bug) and assert the `FORCE ROW LEVEL SECURITY` policy returns zero rows rather than erroring open.
- Load-test RLS overhead specifically — confirm the tenant filter doesn't silently degrade the iterative-scan benefit under concurrent multi-tenant load at MVP scale (~100 concurrent users) before Scale Phase A.

### 7.3 Backup & Disaster Recovery *(new — entirely absent from v1)*

| Component | Backup Method | RPO | RTO |
|---|---|---|---|
| PostgreSQL (relational + pgvector) | Continuous WAL archiving + nightly base backup | 5 min | 1 hr |
| MinIO (evidence/report cards) | Cross-region object replication | 15 min | 2 hr |
| Safety incident queue | Included in Postgres backup, additionally exported to write-once cold storage given 7-year legal hold | 5 min | N/A (immutable) |

Given the data involved is minors' personal and academic records plus safety-incident logs, backup is not optional infrastructure hygiene here — it's a compliance requirement under most of the frameworks in Section 3.1.

---

## 8. Safety Guardrails & Pre-Filter Infrastructure

Retained: NeMo Guardrails proxy, Llama-3.1-NeMoGuard/Llama-Guard-3-8B on the Aegis 2.0 taxonomy, input+output rails, Colang flow structure.

### 8.1 Code Defect Fix *(critical — v1's code will not run)*

v1's `actions.py` has a real bug that would throw on every invocation:

```python
# v1 (broken) — "choices" is a list, not a dict; missing [0] index
result = response.json()["choices"]["message"]["content"].strip()
```

```python
# corrected
@action(name="run_llamaguard_check")
async def run_llamaguard_check(context: dict) -> str:
    user_message = context.get("user_message", "")
    payload = {
        "model": "llamaguard-3-8b",
        "messages": [{"role": "user", "content": user_message}],
        "temperature": 0.0,
        "max_tokens": 10
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://vllm-classifier:8002/v1/chat/completions",
                json=payload, timeout=3.0
            )
            response.raise_for_status()
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError):
            # Fail CLOSED, not open — a classifier outage must never be
            # silently treated as "safe". Route to human review instead.
            return "classifier_unavailable"

        if "unsafe" in result and "S6" in result:
            return "unsafe_self_harm"
        elif "unsafe" in result:
            return "unsafe_general"
        return "safe"
```

**This fail-closed behavior is itself a gap fix**, not just an error handler: v1's original code has no exception handling at all, meaning a classifier timeout or malformed response would crash the request rather than defaulting to a safe posture. For a child-safety gate, an unhandled exception must never resolve to "let the message through unfiltered."

### 8.2 Escalation Delivery (see Section 3.3 — cross-referenced, not duplicated)

### 8.3 Multilingual Safety Coverage *(new)*

Aegis 2.0 / Llama-Guard-3 are primarily English-trained taxonomies. If the platform serves Hindi/Punjabi/Urdu/code-switched input (Section 6.4), the safety classifier's recall on non-English harmful content must be **independently benchmarked**, not assumed to transfer. If recall is materially lower on regional languages, this is a launch blocker for those language cohorts specifically, not a general platform issue — a safety gate that only works in English while children converse in Hindi is a false sense of security.

### 8.4 Continuous Red-Teaming & Drift Monitoring *(new)*

- Scheduled adversarial testing (monthly, minimum) against the input/output rails using a maintained jailbreak-attempt corpus specific to child-safety bypass patterns.
- Sampling-based human review of a small, privacy-minimized percentage of flagged-but-passed conversations to catch classifier drift or emerging bypass patterns before they're exploited at scale.
- Track false-negative rate on the Aegis taxonomy over time as a first-class dashboard metric (Section 12), not just uptime/latency.

---

## 9. Multi-Modal Document Ingestion

Retained: MinIO storage → PII redaction → olmOCR (Qwen2-VL-7B) → confidence gate (0.85) → reconciliation, with human review for low-confidence and discrepant records.

### 9.1 Reviewer Vetting *(new)*

Human reviewers in the discrepancy queue see children's academic records and, per Section 3.3, potentially safety-incident excerpts. This revision requires background-checked, contractually bound reviewers with access scoped to only the specific flagged record (not free browsing of the tenant's data), logged per-access.

### 9.2 Third-Party Data in Report Cards *(new)*

Report cards often contain other students' names/rankings (class rank, comparative grading). v1 mentions redaction of "third-party classmate names and ranking details" — this is correct and retained, but this revision adds: the redaction step must be verified by a secondary automated check (not just the primary spatial-masking filter) before the image ever reaches the olmOCR VLM, since a VLM that "sees" an unredacted image has already processed that third party's personal data regardless of what happens downstream.

---

## 10. Deployment Topology & Capacity Planning

### 10.1 VRAM Capacity Table *(new — v1 asserts hardware sizing with no math shown)*

| Model | Approx. VRAM (FP8) | GPU |
|---|---|---|
| Llama-3.3-70B-Instruct | ~70GB | GPU 0 (dedicated, 80GB) |
| Llama-Guard-3-8B | ~8GB | GPU 1 |
| Qwen2-VL-7B (olmOCR) | ~8GB | GPU 1 |
| Whisper-large-v3 (distil) | ~3GB | GPU 1 |
| Kokoro-82M | ~2.5GB | GPU 1 (CPU-viable fallback) |
| **GPU 1 total** | **~21.5GB of 80GB** | Confirms v1's co-location claim is actually correct, but this was previously asserted, not shown |

This headroom on GPU 1 (~58GB free) should be earmarked explicitly for MVP-to-Scale-Phase-A growth (e.g., running a second Llama-Guard replica for higher-QPS safety filtering) rather than left as unaccounted slack.

### 10.2 Redundancy *(new — v1's dual-H100 node is a single physical point of failure)*

At MVP scale, a single node is an acceptable, documented risk (with a defined downtime runbook). Before Scale Phase A (~1,000 concurrent users), the plan must include at least N+1 redundancy for GPU 0 (the main conversational model) specifically, since that is a hard dependency for every active session — GPU 1's services (safety, OCR, TTS) can tolerate brief degraded-mode fallback (e.g., temporarily routing TTS to a CPU-only path) more gracefully than a full conversational outage.

### 10.3 Indicative Cost Model *(new — v1 has no unit economics)*

| Phase | Concurrent Users | Est. Monthly Infra Cost (self-hosted GPU, rented) | Cost Driver |
|---|---|---|---|
| MVP | ~100 | Single L40S/RTX 6000 rental | Base compute only |
| Scale Phase A | ~1,000 | Dual H100 node | Fixed cost regardless of load below ~1,000 ceiling — favorable unit economics past this point vs. per-token API pricing |
| Scale Phase B | ≥10,000 | Kubernetes GPU cluster, autoscaled | Marginal cost approaches per-request compute + storage growth |

This should be filled in with actual rented-GPU market rates at build time and compared explicitly against an equivalent hosted-API cost projection (e.g., what the same traffic would cost on a commercial API) to validate the self-hosting decision is still the right one at each phase — the original PRD asserts self-hosting saves cost but never shows the comparison.

---

## 11. Guardian & Administrator Dashboard *(new — named in v1's threat model but never specified)*

Minimum viable feature set:

- **Consent management**: view/grant/revoke each consent type from Section 3.2, with plain-language explanations of what each unlocks.
- **Relationship health view**: session frequency/duration trend (Section 4.4), age-appropriate summary of topics discussed (not raw transcripts, to preserve the child's sense of a private confiding space, except where a safety incident has been raised).
- **Safety incident notifications**: real-time alert delivery per Section 3.3, with acknowledgment tracking.
- **Academic sync status**: report card ingestion status, discrepancy flags awaiting resolution.
- **Data export & deletion request**: self-service trigger for the rights described in Section 3.1/3.4.
- **Admin-only surface**: tenant-wide safety-incident dashboard, reviewer workload/SLA compliance, classifier false-negative tracking (Section 8.4).

---

## 12. Observability & Evaluation

Retained: Langfuse via OpenTelemetry for the voice pipeline. Extended to close the gap that v1's tracing example only instruments voice sessions.

- Instrument **all** LangGraph/CrewAI execution paths (text-mode conversations, discovery panels, nightly curation jobs) with the same tracer provider, not just the voice entrypoint — a text-mode child conversation is exactly as safety-critical as a voice one, and currently has no observability example in v1 at all.
- Track, as first-class dashboard metrics beyond latency/token count: safety-rail trigger rate (per tenant, per age band), rapport-score distribution (to catch the over-engagement failure mode from Section 4.3), and discrepancy-queue backlog age.
- Alert on Safety Incident Queue SLA breaches (Section 3.3's 15-minute page) as a paging-severity alert, not a dashboard-only metric.

---

## 13. Security Hardening *(new)*

- **Session/auth**: short-lived JWTs for learner sessions, refresh-token rotation, device binding where feasible on low-cost shared devices common in the target population.
- **Secrets management**: model-serving API keys, DB credentials, and Langfuse keys via a secrets manager (Vault or cloud-native equivalent), never in `.env` files committed anywhere near the repo.
- **Supply chain**: checksum-verify all downloaded model weights (Llama, Kokoro, Whisper, Qwen2-VL) against published hashes before container build; pin exact model revisions rather than tracking `latest`.
- **Penetration testing**: scheduled (at minimum, before the Phase 7 pilot and annually thereafter), with explicit scope on RLS bypass attempts and the safety-proxy gateway.
- **Rate limiting / abuse prevention**: per-account and per-device request throttling to prevent scripted abuse of a system designed to be emotionally responsive to children.

---

## 14. Testing & QA Strategy *(new)*

| Layer | Method |
|---|---|
| RLS / tenant isolation | Automated `pgTAP` suite (Section 7.2), run on every migration |
| Safety classifier | Adversarial red-team corpus (Section 8.4), monthly; regression suite of known-bad prompts run on every model version bump |
| Voice pipeline | Latency budget conformance tests (Section 6.2) under simulated concurrent load |
| CrewAI panel logic | Deterministic unit tests on panel-selection algorithm (interest-matching + diversity constraint, Section 5.1) |
| End-to-end | Scripted conversation replay covering: normal use, self-harm disclosure, jailbreak attempt, low-confidence OCR document, consent withdrawal mid-session |
| Pilot | Phase 7's 100-user pilot must include a defined feedback instrument for **guardians**, not just usage telemetry — qualitative signal on whether the relationship feels healthy is not something dashboards alone will catch |

---

## 15. Implementation Roadmap (Revised)

Retained v1's 8-phase structure, with governance work moved earlier (it gates everything downstream) rather than left implicit, and a new closing phase for the gaps this revision introduces.

```
Phase 0: Foundations + Governance Skeleton (3-4 Weeks)   [governance work ADDED to original scope]
  - Stand up Postgres + RLS security skeleton
  - Deploy local Llama models via vLLM
  - Establish basic 1:1 conversational routing
  - Build Consent Ledger schema + guardian account model  (NEW)
  - Confirm legal/geographic compliance target (Section 3.1)  (NEW)
        |
        v
Phase 1: Memory & Continuity (3-4 Weeks)
  - Learner profile + history schemas
  - pgvector HNSW indices with per-transaction RLS + iterative-scan config (corrected, Section 7.1)
  - Nightly pruning jobs mapped to explicit retention table (Section 3.4)  (NEW)
        |
        v
Phase 2: LiveKit Voice Integration (4-5 Weeks — extended)
  - Deploy local LiveKit server
  - Integrate Silero VAD + Whisper STT
  - Configure Kokoro-82M TTS
  - Multilingual coverage go/no-go checkpoint (Section 6.4)  (NEW — hard gate)
  - Output safety rail wired into voice path, not just text path (Section 6.1)  (NEW)
        |
        v
Phase 3: Document Ingestion (3-4 Weeks)
  - MinIO + olmOCR + confidence gating (retained)
  - Reviewer vetting/access-scoping process (Section 9.1)  (NEW)
        |
        v
Phase 4: Agent Pools & Dynamic Gating (4-5 Weeks)
  - Career mentor personas + taxonomy
  - Four-stage introduction gate, with Relationship Bandwidth explicitly defined (Section 5.1)  (CORRECTED)
  - Panel diversity constraint implemented (Section 5.1)  (NEW)
        |
        v
Phase 5: CrewAI Discovery Panels (4-5 Weeks)
  - CrewAI as LangGraph tool
  - Panel-latency UX handling (Section 5.3)  (NEW)
  - Output verification against approved career-data source
        |
        v
Phase 6: Proxy-Level Safety, Escalation & Dashboards (Parallel Track, 5-6 Weeks — extended)
  - NeMo Guardrails gateway, Aegis 2.0 taxonomy, fail-closed classifier code (Section 8.1)  (CORRECTED)
  - Safety Incident Queue + on-call escalation SLA (Section 3.3)  (NEW)
  - Guardian + admin dashboard (Section 11)  (NEW)
        |
        v
Phase 7: Hardening & Regional Pilot (4-5 Weeks — extended)
  - RLS isolation test automation (Section 7.2)
  - WebRTC concurrent-stream stress tests
  - Penetration test (Section 13)  (NEW)
  - 100-user pilot with guardian qualitative feedback instrument (Section 14)  (NEW)
        |
        v
Phase 8: Continuous Safety & Drift Monitoring (Ongoing, post-launch)  (NEW PHASE)
  - Monthly red-team cadence (Section 8.4)
  - Multilingual safety-recall benchmarking (Section 8.3)
  - Rapport-score / engagement-pattern review against Section 4's anti-engagement-maximization principle
```

---

## 16. Risk Register *(new)*

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Child forms unhealthy parasocial dependency on sibling persona | Medium | High | Section 4 guardrails; guardian visibility into engagement trends |
| Safety classifier misses non-English harmful content | Medium-High (unverified) | Critical | Section 8.3 mandatory benchmarking before regional launch |
| RLS misconfiguration leaks cross-tenant minor data | Low (with testing) / High if untested | Critical | Section 7.2 automated adversarial test suite |
| Guardian consent is procedurally weak in low-resource enrollment settings | Medium | High (legal + trust) | Section 3.2 NGO co-sign / in-person verification path |
| Single-node GPU 0 outage takes down all active conversations | Medium at scale | High | Section 10.2 redundancy plan gated to Scale Phase A |
| Career-professional persona hallucinates inaccurate guidance | Medium | Medium | Existing output-verification layer (retained) + Section 5.2 fallback for unmatched interests |
| Reviewer with data access misuses minors' records | Low | Critical | Section 9.1 vetting + scoped, logged access |

---

## Appendix A: Summary of Changes from v1

| # | Gap | Section |
|---|---|---|
| 1 | Voice-first UX for low-literacy/bilingual children | 6 (retained + extended) |
| 2 | Proactive safety gateway | 8 (retained + fixed) |
| 3 | pgvector RLS overfiltering | 7.1 (retained + corrected wiring) |
| 4 | No consent/guardianship model or legal compliance framework | 3 |
| 5 | No data retention/deletion policy | 3.4 |
| 6 | No emotional-safety-of-relationship design | 4 |
| 7 | Undefined escalation delivery mechanism | 3.3 |
| 8 | Undefined "Relationship Bandwidth" gate term | 5.1 |
| 9 | No panel-diversity/fairness constraint | 5.1 |
| 10 | Broken safety-classifier code + no fail-closed behavior | 8.1 |
| 11 | No multilingual coverage validation despite bilingual target | 6.4, 8.3 |
| 12 | No latency budget breakdown behind the "<4s" claim | 6.2 |
| 13 | No VRAM capacity math behind hardware sizing | 10.1 |
| 14 | No backup/DR plan | 7.3 |
| 15 | No guardian/admin dashboard specification | 11 |
| 16 | No security hardening plan (secrets, supply chain, pentesting) | 13 |
| 17 | No testing/QA strategy | 14 |
| 18 | No cost model / unit economics validation | 10.3 |
| 19 | Incomplete observability (voice-only tracing) | 12 |
| 20 | No internal API contract between planes | 5.4 |
| 21 | No CrewAI panel-latency UX | 5.3 |
| 22 | No risk register | 16 |
