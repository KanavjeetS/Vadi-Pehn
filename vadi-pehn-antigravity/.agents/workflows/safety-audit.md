---
description: Run a dedicated, deep safety-and-privacy audit pass across the whole codebase, independent of any specific build segment
---

When the user types `/safety-audit`, run this independent of whatever
segment is currently in progress. Intended to be run periodically (e.g.
weekly during active development, or before any pilot/demo), not only
right after a build segment.

### Execution Sequence
1. Act as **@qa-auditor**. Read `GUARDRAILS.md` in full.
2. Run `audit-safety-failclosed.md` against the entire codebase, not just
   the most recently changed segment.
3. Run `audit-tenant-isolation.md` against every per-learner table/store
   that currently exists.
4. Act as **@safety-engineer**. Independently review:
   - Every place `SafetyVerdict` is consumed — confirm nothing treats
     `CLASSIFIER_UNAVAILABLE` as equivalent to `SAFE` anywhere, including
     in code paths added since the last audit.
   - Every place learner conversational content is persisted — confirm
     incident-severity turns still never reach `learner_memories`
     (GUARDRAILS.md G-003).
   - The Consent Ledger: confirm every write to a consent-gated table
     checks consent state first (AGENTS.md rule 4), for every table added
     since the last audit, not just the original set.
   - The rapport score: confirm it is not read/used anywhere as a growth
     or engagement metric (AGENTS.md rule 3) — grep for any dashboard,
     log, or analytics code that surfaces it outside the introduction-gate
     check.
5. Run the PRD §8.4 adversarial red-team corpus
   (`eval/safety_redteam_corpus/`) against the current safety proxy, if
   built, and report the pass rate.
6. Produce a report with a single top-line verdict: **CLEAR** (no findings)
   or **BLOCKED** (at least one live bypass or fail-open path found — list
   each with severity). A **BLOCKED** result means no segment should be
   presented as pilot-ready until it's resolved, regardless of what
   `/build-segment` or `/full-cycle` last reported.
7. Log any new pattern found to `GUARDRAILS.md`.
