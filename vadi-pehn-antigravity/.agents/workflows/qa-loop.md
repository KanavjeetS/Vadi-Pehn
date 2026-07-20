---
description: Run an iterative find-issues-then-fix loop against a target until clean or the iteration cap is hit
---

When the user types `/qa-loop <target>` (target: a segment name, a file
path, or "all"), run the following loop. This is the "keep going until the
finite finds an error or it's absolutely correct" agent — bounded so it
terminates predictably either way.

### Setup
- `max_iterations = 5` unless the user specifies a different number
  (`/qa-loop <target> --max-iterations N`).
- `iteration = 0`
- Read `GUARDRAILS.md` in full before iteration 1 — do not re-discover a
  documented lesson from scratch.

### Loop (repeat until clean or `iteration == max_iterations`)
1. `iteration += 1`. Announce which iteration this is.
2. Act as **@qa-auditor**. Run, as applicable to `<target>`:
   - `pytest -v` (full suite, not just target-relevant tests — a fix
     elsewhere may have broken something)
   - `audit-tenant-isolation.md` if target touches per-learner data
   - `audit-safety-failclosed.md` if target touches conversation/
     generation paths
   - Static review for anything AGENTS.md's non-negotiable rules cover
3. If zero issues found: STOP. Report "clean after N iterations" and end
   the loop successfully. Do not keep iterating past a clean result "to be
   sure" — that wastes budget without adding confidence.
4. If issues found: for each, classify as **trivial** (clear bug, one
   correct fix, e.g. a typo, an off-by-one, a missing await) or
   **judgment-call** (multiple reasonable fixes, or touches a
   safety/schema/consent boundary).
5. Fix all **trivial** issues directly (as @qa-auditor, per its
   constraint in `agents.md` allowing this). For **judgment-call** issues,
   hand off to the owning persona (per `build-segment.md`'s
   segment→persona table) to decide and fix — do not guess on these
   yourself even under loop pressure to finish.
6. If the SAME category of issue is found in 2 or more iterations (e.g.
   two different fail-open bugs in two different files), this is a
   pattern, not a one-off — append a new entry to `GUARDRAILS.md` using
   its template, citing both occurrences, before continuing the loop.
7. Go to step 1.

### If the cap is hit without a clean result
Stop. Do not keep looping silently past `max_iterations` — report exactly
what's still failing, why it wasn't a trivial fix, and hand off to a human
or the owning persona with full context. A loop that never terminates is a
bug in the loop, not a sign to keep trying.
