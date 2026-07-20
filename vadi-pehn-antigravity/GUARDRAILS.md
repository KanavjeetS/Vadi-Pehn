# GUARDRAILS.md — Learned Failure Patterns

This file exists so agents stop repeating mistakes across sessions. Read it
before starting work. Append to it whenever `/qa-loop` or `/research-loop`
finds and fixes a real recurring issue, or whenever a human corrects an
agent's approach in a way that should generalize.

Format per entry: what went wrong, why it's tempting to get wrong, the rule
that prevents it, and where it's enforced/tested.

---

### G-001: Safety classifier errors must never resolve to "safe"
**What went wrong (source: PRD §8.1 code review):** the original safety
action code indexed `response.json()["choices"]["message"]` (missing the
list index `[0]`), which throws on every real call. An unhandled exception
in that path is indistinguishable, from the caller's perspective, from "no
verdict" — and it's tempting to let that fall through to "let the message
proceed" so the demo doesn't break.
**Rule:** any exception, timeout, or malformed response in a safety check
MUST resolve to `SafetyVerdict.CLASSIFIER_UNAVAILABLE`, which blocks
generation. Never catch-and-ignore on a safety path.
**Enforced by:** `src/sibling/safety.py::NeMoGuardSafetyClient._call`,
tested in `tests/test_safety.py::test_real_safety_client_fails_closed_on_timeout`.

### G-002: RLS predicates filter tenant AND learner, never tenant alone
**What went wrong:** it's easy to write a query scoped by `tenant_id` only
and assume application logic will handle learner-level separation. Two
learners under the same guardian/tenant must never see each other's memory.
**Rule:** every per-learner table query includes both `tenant_id` and
`learner_id` in the WHERE/RLS predicate. Rank-then-filter is wrong order;
filter-then-rank is correct (filter tenant+learner first, THEN do vector
similarity ranking).
**Enforced by:** `tests/test_memory_store.py::test_two_learners_in_same_tenant_never_share_memory`
(mirrored at the Postgres layer by the pgTAP suite once §7.2 is built).

### G-003: Blocked/incident turns are never written to ordinary RAG memory
**What went wrong:** it's tempting to log every turn to memory uniformly
for "completeness." A self-harm disclosure or blocked-input turn, if
written into `learner_memories` like a normal turn, becomes retrievable
context for future conversations — over-collecting trauma detail into the
child's own long-term memory retrieval path.
**Rule:** `write_memory` node only persists turns where `outcome ==
"generated"`. Incident-severity turns go to the Governance Service's
`safety_incidents` table instead, which has its own access controls.
**Enforced by:** `orchestration_graph.py::write_memory`, tested in
`test_orchestration_graph.py::test_self_harm_disclosure_short_circuits_to_fixed_script`.

### G-004: Output safety must gate every streamed chunk, not the assembled reply
**What went wrong:** streaming TTS starts speaking the first sentence
before later sentences exist. Running the output-safety check once on the
full assembled reply (the naive approach) means unsafe content in a later
sentence has already been spoken by the time it's caught.
**Rule:** call `safety_client.check_output` per sentence-chunk, before that
chunk is forwarded to TTS, and stop generation at the first blocked chunk.
**Enforced by:** `orchestration_graph.py::generate_and_check_output`.

### G-005: Consent withdrawal deletes immediately, not on the nightly batch
**What went wrong:** the 18-month rolling retention prune and a
guardian-initiated consent withdrawal are different triggers with different
urgency. Conflating them (queuing a withdrawal into the same nightly batch
as routine expiry) violates the rights-triggered nature of a withdrawal.
**Rule:** `delete_for_learner()` is a synchronous, immediate delete path,
separate from `prune_expired()`.
**Enforced by:** `memory_store.py`, tested in
`test_memory_store.py::test_consent_withdrawal_deletes_all_learner_memories`.

---

## Template for new entries

```
### G-0XX: <short title>
**What went wrong (source: <where this was found>):** <description>
**Rule:** <the concrete, checkable rule>
**Enforced by:** <file/test that enforces it — every guardrail needs a
test or a lint rule, not just a sentence here>
```
