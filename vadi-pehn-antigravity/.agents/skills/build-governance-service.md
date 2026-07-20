# Skill: Build Governance Service

## Objective
As the Child Safety & Governance Engineer (with @data-engineer for schema),
build the Governance Service: Consent Ledger, Safety Incident Queue,
retention job scheduling, and the escalation workflow — System Design §2,
§3.4, §5.3; PRD §3.

## Rules of Engagement
- This service's database is a physically separate Postgres instance from
  the Memory Service (System Design §3.4 design decision). Do not merge
  them, even for local dev convenience — model the separation in
  `docker-compose.dev.yml` too, so dev parity is real.
- The 15-minute SLA on `unsafe_self_harm` incidents (PRD §3.3) needs an
  independent delivery path that does not depend on the same infra that
  might be degraded during an incident (System Design §7's failure-mode
  table). Do not implement paging as "just another row read by a
  dashboard poller."
- Consent withdrawal triggers immediate deletion, not nightly-batch
  deferral (GUARDRAILS.md G-005).

## Instructions
1. Implement the `consent_records` and `safety_incidents` schema exactly
   per System Design §3.4, in a separate DB/service from
   `learner_memories`.
2. Implement `POST /internal/v1/governance/incident`,
   `POST /internal/v1/governance/incident/{id}/acknowledge`, and
   `GET /internal/v1/governance/consent/{learner_id}/{consent_type}`
   per System Design §4.5.
3. Implement the Notification Bus contract (at-least-once delivery) for
   paging an on-call reviewer — start with a pluggable interface
   (`NotificationSender`) with a mock (logs to console/file) and a real
   SMS/push backend stub, same interface-first pattern as everywhere else
   in this codebase.
4. Wire `orchestration_graph.py`'s `IncidentRecord` objects (already
   produced in the correct shape) to actually POST to this service —
   currently they're only constructed locally and not sent anywhere; this
   skill closes that gap.
5. Implement the nightly retention job (`prune_expired`-equivalent for
   consent-scoped data) and the immediate-deletion path for consent
   withdrawal, matching System Design §5.5's sequence flow exactly.
6. Write tests for: SLA-deadline calculation, immediate-vs-nightly
   deletion distinction, and that an incident write failure triggers the
   redundant/direct paging fallback described in System Design §7's
   failure-mode table rather than silently dropping the escalation.
