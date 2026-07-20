---
description: Run an iterative research-propose-(apply)-verify loop to find and incorporate improvements
---

When the user types `/research-loop <topic>` (topic: a stack component
like "safety-classifier", "voice-latency", "embeddings", or "all"), run
the following loop.

### Setup
- `max_iterations = 3` unless specified otherwise
  (`/research-loop <topic> --max-iterations N`).
- `auto_apply_low_risk = false` unless the user passes
  `--auto-apply-low-risk`.
- `iteration = 0`

### Loop (repeat until no new findings or the iteration cap is hit)
1. `iteration += 1`.
2. Act as **@researcher**. Execute `research-and-propose.md` scoped to
   `<topic>`.
3. For each finding produced:
   - `urgent-safety`: stop the loop's normal flow immediately, surface it
     at the top of the report, and hand off to **@safety-engineer**
     regardless of iteration count or remaining budget.
   - `low-risk` with `auto_apply_low_risk == true`: apply per
     `research-and-propose.md` step 4, then immediately run
     `/qa-loop <affected-segment> --max-iterations 2` to verify nothing
     broke. If that loop doesn't come back clean, revert the change and
     downgrade the finding to `needs-review` instead.
   - `needs-review` (or `low-risk` with auto-apply off): do not apply.
     Add to the report as a proposal with the owning persona named.
4. If this iteration produced zero new findings not already logged in
   `research/findings/`, STOP — the research space for this topic is
   exhausted for now. Report and end.
5. Otherwise go to step 1, but narrow the search based on what this
   iteration surfaced (e.g. if a new embedding model was found, the next
   iteration digs into benchmarks/compatibility for that specific model
   rather than re-running the same broad search).

### After the loop ends (clean exhaustion or cap hit)
Produce a summary: findings by risk tier, what was auto-applied and
verified, what's pending human/persona review, and anything flagged
urgent-safety. Do not consider `needs-review` items "done" — they are
proposals until a human or the owning persona explicitly applies them.

### Guardrail
This workflow NEVER modifies `.agents/rules/`, `safety.py`,
`orchestration_graph.py`'s safety-gating nodes, or any RLS/schema file,
regardless of `--auto-apply-low-risk` — per `research-and-propose.md`'s
own constraint. If a finding would require touching one of these, it is
always `needs-review` or `urgent-safety`, never auto-applied.
