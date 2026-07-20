# Skill: Sync Docs With Code

## Objective
As the Documentation Synchronizer, after a build segment lands, check
`docs/PRD-v2.md` and `docs/system-design.md` for drift against what was
actually built, and produce a minimal, precise patch — not a rewrite.

## Rules of Engagement
- A doc-vs-code mismatch has two possible resolutions: the doc was right
  and the code needs fixing (flag to the owning engineer persona), or the
  code made a reasonable call on something the doc left open (update the
  doc). You do not get to silently pick which — say which one you believe
  it is and why, then apply only the second kind directly.
- Never alter a governance or safety requirement's *meaning* while "just
  syncing docs" — if a build segment implemented something that
  contradicts a safety/governance requirement, that's a finding for
  `@safety-engineer` and a human, not a doc edit.

## Instructions
1. Diff the segment's actual API endpoints, schema, and control flow
   against the relevant System Design section.
2. For each discrepancy found, classify it: (a) code deviated from doc
   incorrectly — file as a bug for the owning persona; (b) doc left this
   genuinely open and code made a reasonable, documented decision — patch
   the doc's "Design decision" callout style (see System Design §5.2, §9
   for the existing tone/format to match); (c) doc is simply stale
   (e.g. an endpoint was renamed) — patch directly.
3. Keep patches surgical: quote the specific paragraph/table row changed,
   don't regenerate whole sections.
4. Update the Appendix A traceability table in PRD-v2.md or the
   traceability appendix in system-design.md if a gap listed there is now
   closed by this segment, or if this segment revealed a new gap worth
   tracking the same way.
5. Update the segment's own `README.md` (following the existing style in
   `sibling-voice-rag/README.md`'s "what's real vs. placeholder" table).
