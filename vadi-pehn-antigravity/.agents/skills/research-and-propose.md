# Skill: Research & Propose

## Objective
As the Research Agent, scan for improvements relevant to this project's
actual stack — not generic AI news — and produce dated, sourced,
risk-classified findings the team can act on.

## Rules of Engagement
- In scope: LangGraph, CrewAI, vLLM, Llama-Guard/NeMo Guardrails and the
  Aegis taxonomy, Whisper/faster-distil-whisper, Kokoro-82M (and its
  documented fallback, Piper), pgvector, olmOCR/Qwen2-VL, LiveKit,
  Langfuse — i.e., exactly the stack named in System Design §10's
  technology table. Out of scope: general AI industry news with no
  concrete applicability here.
- Every finding is written to `research/findings/YYYY-MM-DD-<slug>.md`,
  never applied silently in the same pass it was found, UNLESS it is
  classified `low-risk` (see risk classification below) AND the invoking
  workflow explicitly allows auto-apply.
- Always cite sources with dates. If a claim can't be sourced, label it
  clearly as your own inference, not a cited fact.

## Risk Classification (apply to every finding)
- **low-risk**: a newer minor/patch version of a non-safety dependency,
  a pure performance optimization with no behavior change, a
  documentation-only improvement. May be auto-applied if the workflow
  allows it.
- **needs-review**: a new technique that changes behavior but not a
  safety- or privacy-critical path (e.g. a better RAG chunking strategy,
  a cheaper embedding model with comparable quality). Requires the owning
  engineer persona's sign-off before applying.
- **urgent-safety**: a CVE, a known jailbreak technique against
  Llama-Guard/NeMo Guardrails, a reported failure mode in a dependency
  this project's safety path relies on. Flag immediately at the top of
  your output, do not wait for the next scheduled research pass, and
  route to `@safety-engineer` directly regardless of what triggered this
  skill.

## Instructions
1. Search for updates/advisories/new techniques for the in-scope stack,
   prioritizing anything published since the last entry in
   `research/findings/`.
2. For each finding: what changed, why it matters to this specific
   project (cite the exact PRD/System Design section it would affect),
   risk classification, and a concrete proposed next step (not just "this
   exists").
3. Write the finding file. If `urgent-safety`, also append a one-line
   pointer to it at the top of `GUARDRAILS.md` under a `## Pending Urgent
   Research Findings` heading (create the heading if absent) so it's
   impossible to miss.
4. If invoked by `/research-loop --auto-apply-low-risk` and a finding is
   `low-risk`, apply it directly (e.g. bump a dependency version, run the
   test suite, confirm green) and note in the finding file that it was
   auto-applied plus the test result.
5. Never modify `safety.py`, RLS policies, the Consent Ledger schema, or
   any file under `.agents/rules/` as part of an auto-apply, regardless of
   risk classification — these always route to `needs-review` or
   `urgent-safety` at minimum.
