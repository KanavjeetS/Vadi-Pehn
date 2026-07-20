---
description: Run the full multi-segment build pipeline in dependency order, with human approval gates on safety/data-critical segments
---

When the user types `/full-cycle`, orchestrate the entire remaining build
using `.agents/agents.md`, `.agents/skills/`, and the other workflows in
this directory. This is the top-level pipeline — use `/build-segment` for
one piece at a time instead if you want more control.

### Segment order (per `docs/system-design.md`'s dependency structure —
### foundation is already built; this resumes from there)
1. `memory-service` (real Postgres/RLS — everything else depends on real
   persistence existing)
2. `safety-proxy` (real NeMo Guardrails — everything conversational
   depends on this being real, not mocked)
3. `voice-gateway`
4. `governance-service`
5. `panel-service`
6. `ingestion-service`
7. `guardian-dashboard`

### Execution Sequence
1. Act as **@architect**. Confirm which segments from the list above are
   already implemented (re-use `bootstrap-workspace.md`'s status check)
   and produce the actual remaining order for this run.
2. For each remaining segment, in order:
   a. Run `/build-segment <segment-name>` in full, including its internal
      QA rework loop.
   b. **Approval gate:** if the segment is `memory-service`,
      `safety-proxy`, or `governance-service` (the three that touch
      schema, consent, or the safety-critical path), STOP after step (a)
      and explicitly ask the human: "Segment `<name>` is built and passing
      its own QA loop. This segment touches [schema / safety-critical
      logic / consent] — please review before I continue to the next
      segment." Wait for explicit approval before proceeding to the next
      segment. Do not treat silence or an unrelated reply as approval.
   c. For all other segments, proceed automatically to the next one, but
      still report what was completed after each.
3. After all segments in this run are complete, run `/qa-loop all` once
   as a final cross-segment integration pass (a bug can exist at the
   boundary between two individually-correct segments).
4. Run `/research-loop all` once (without `--auto-apply-low-risk`, so it
   only produces a proposal report — a full-cycle run should surface
   opportunities, not silently change behavior on its way out).
5. Produce a final report: segments completed, GUARDRAILS.md entries
   added this run, outstanding `needs-review`/`urgent-safety` research
   findings, and what's left per `docs/system-design.md`.

### Hard stop conditions
Stop the entire cycle immediately (not just the current segment) and
escalate to the human if, at any point: `audit-safety-failclosed.md`
finds a live bypass (not just a missing test) of the safety proxy, or any
skill/workflow would need to violate
`.agents/rules/child-safety-non-negotiables.md` to proceed.
