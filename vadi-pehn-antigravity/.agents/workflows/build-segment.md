---
description: Build one named project segment end to end, from spec-check through QA
---

When the user types `/build-segment <segment-name>`, orchestrate strictly
using `.agents/agents.md` and `.agents/skills/`. Valid `<segment-name>`
values and their skill/persona mapping:

| segment-name | persona | skill |
|---|---|---|
| orchestration | @backend-engineer | build-orchestration-graph.md |
| memory-service | @data-engineer | build-memory-service.md |
| safety-proxy | @safety-engineer | build-safety-proxy.md |
| voice-gateway | @voice-engineer | build-voice-gateway.md |
| panel-service | @backend-engineer | build-panel-service.md |
| governance-service | @safety-engineer + @data-engineer | build-governance-service.md |
| ingestion-service | @data-engineer | build-ingestion-service.md |
| guardian-dashboard | @backend-engineer | build-guardian-dashboard.md |

### Execution Sequence
1. Act as **@architect** and confirm the target segment's scope against
   `docs/PRD-v2.md` / `docs/system-design.md`. Produce a short task list.
   If the segment touches anything in
   `.agents/rules/child-safety-non-negotiables.md`, say so explicitly
   before proceeding.
2. Shift context to the mapped persona(s) and execute the mapped skill
   file for `<segment-name>`.
3. Shift context to **@backend-engineer** (or the segment's owning
   persona) and execute `write-tests.md` for anything not already covered
   by the build skill's own test instructions.
4. Shift context to **@qa-auditor** and run `audit-tenant-isolation.md`
   if the segment touches any per-learner data table, and
   `audit-safety-failclosed.md` if the segment touches any conversation
   or generation path. Skip whichever doesn't apply, but say which you
   skipped and why.
5. If step 4 finds issues, hand back to the owning persona, fix, and
   re-run step 4. Do not proceed to step 6 until step 4 is clean —
   this is the same rework-loop principle as `/qa-loop`, scoped to just
   this segment.
6. Shift context to **@doc-keeper** and execute `sync-docs-with-code.md`.
7. Report: what was built, test count before/after, any GUARDRAILS.md
   entries added, and the recommended next segment per
   `docs/system-design.md`'s dependency order.
