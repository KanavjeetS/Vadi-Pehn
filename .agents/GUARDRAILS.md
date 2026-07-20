# GUARDRAILS.md — Vadi-Pehn Safety & Isolation Lessons

This file is a living log. The `/qa-loop` workflow appends to it when the
same class of issue appears in 2+ iterations. `@qa-auditor` reads this
in full before iteration 1 of any QA loop. `@researcher` appends urgent
findings under `## Pending Urgent Research Findings`.

**Format for new entries:**
```
## G-NNN: [Short title]
**Date:** YYYY-MM-DD
**Discovered in:** <segment name or file>
**Occurrences:** <list of files/commits where this pattern appeared>
**What happened:** <1–3 sentences>
**What must always be true:** <the invariant, phrased as a positive assertion>
**Test that proves it:** <pytest path or pgTAP file>
```

---

## Pending Urgent Research Findings
*(Append one-liners here when @researcher finds an urgent-safety finding)*

---

## G-001: Safety Proxy Must Be Network-Level, Not a Library
**Date:** 2026-07-19
**Discovered in:** System Design §2 (design decision)
**What happened:** Early drafts treated the safety classifier as an imported
library call. If the Orchestration Service process is compromised or has a bug,
it could skip a function call. A network-level proxy cannot be bypassed by
application code.
**What must always be true:** The LLM inference endpoint is only reachable
through the Safety Proxy's reverse-proxy path. The Orchestration Service
has no direct route to vLLM that bypasses the proxy.
**Test that proves it:** Network policy test (docker-compose network isolation
or K8s NetworkPolicy) — `orchestration` service cannot reach `vllm-main` directly.

---

## G-002: RLS Policy Requires FORCE ROW LEVEL SECURITY
**Date:** 2026-07-19
**Discovered in:** System Design §3.2
**What happened:** `CREATE POLICY` alone does not protect table owners.
`FORCE ROW LEVEL SECURITY` must also be set, or the Postgres superuser role
used by some ORMs bypasses the policy entirely.
**What must always be true:** Both `ALTER TABLE x ENABLE ROW LEVEL SECURITY`
AND `ALTER TABLE x FORCE ROW LEVEL SECURITY` are present in every migration
for `learner_memories` and `learner_interest_profile`.
**Test that proves it:** pgTAP file: `db/migrations/<timestamp>_learner_memories.test.sql`
asserts tenant A session returns zero rows for tenant B's data.

---

## G-003: Governance DB Unreachability Is More Severe Than Memory DB Unreachability
**Date:** 2026-07-19
**Discovered in:** System Design §7 (failure modes table)
**What happened:** Treating both databases with equal fallback behavior would cause
a self-harm safety incident to be silently dropped if the Governance DB is down.
**What must always be true:** If the Governance Service DB is unreachable when
an incident needs to be written, Orchestration falls back to a direct SMS webhook
to the on-call reviewer — it does NOT return a 500 silently.
**Test that proves it:** Integration test with Governance DB deliberately unavailable:
assert that the incident is delivered via the fallback paging path.

---

## G-004: Voice Output Safety Must Gate Every Sentence Chunk, Not the Full Reply
**Date:** 2026-07-19
**Discovered in:** System Design §5.2 (design decision closing PRD §6.1 gap)
**What happened:** PRD §6.1 originally named an open gap: voice output bypassed
the output safety rail because safety was checked on the full reply, but the
full reply doesn't exist until after the first audio chunks are already playing.
**What must always be true:** The Voice Gateway's streaming path calls
`check-output` on each sentence chunk BEFORE that chunk is passed to Kokoro TTS.
No audio chunk is synthesized or played without a SAFE verdict for that chunk.
**Test that proves it:** `tests/test_voice_gateway.py` asserts that a stream
containing an unsafe mid-reply chunk results in audio stopping at that chunk
and a graceful hold message, not continuing playback.
