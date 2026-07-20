# AGENTS.md — Vadi-Pehn: An AI Mentor

Standing instructions for every agent working in this workspace. Read this
before any task, regardless of which persona or skill is active.

## Source of Truth

This project has two governing documents. Every agent MUST treat them as
authoritative and MUST NOT contradict them without an explicit, logged
human approval:

- `docs/PRD-v2.md` — product requirements, governance, and child-safety
  policy. Section numbers referenced throughout this config (e.g. "PRD 8.1")
  point here.
- `docs/system-design.md` — service boundaries, schemas, API contracts,
  sequence flows. Section numbers referenced as "System Design §X".

If a task requires deviating from either document, STOP and ask the human
before writing code. Do not silently "improve" the architecture mid-task.

## Non-Negotiable Rules (apply to every agent, every skill, every task)

1. **Fail closed, always.** Any safety classifier timeout, malformed
   response, or unknown error MUST resolve to blocking generation and
   routing to human review — never to "safe". This is PRD §8.1. There is
   no task, refactor, or performance optimization that justifies relaxing
   this.
2. **Tenant and learner isolation is load-bearing, not decorative.** Every
   new query against `learner_memories`, `consent_records`,
   `safety_incidents`, or any other per-learner table MUST be scoped by
   `tenant_id` AND `learner_id`, enforced at the database layer (RLS), not
   just in application code. See System Design §7 and the existing test
   suite in `tests/test_memory_store.py` for the pattern to follow.
3. **The rapport score is never a growth metric.** Do not add code,
   dashboards, or prompts that optimize engagement/session frequency as an
   end in itself. It exists only to gate career-mentor introductions
   (PRD §4.3). If you see this principle being violated anywhere, flag it,
   don't fix-and-continue silently.
4. **Consent gates data existence, not just access.** Before any write to
   a learner's data that depends on a specific consent type, check the
   Governance Service's consent state first. Do not write-then-filter.
5. **No real child data, ever, anywhere in this repo.** Test fixtures use
   synthetic data only. Never fetch, paste, or generate content that reads
   as a real transcript, real report card, or real personal detail of a
   real minor, even as an example.
6. **Persona prompts are reviewed like safety-critical code.** Changes to
   `prompts/*.md` go through the same scrutiny as changes to
   `safety.py` or RLS policies — a bad prompt edit for something a child
   talks to daily is a product-safety incident, not a copy tweak.
7. **Every external dependency stays behind an interface.** LLM, embedding,
   STT, TTS, safety-classifier, and memory-store backends must be swappable
   via the `SIBLING_*_BACKEND` env vars in `config.py`. Never hardcode a
   concrete backend into orchestration or API code.

## Team & How to Work

The full team is defined in `.agents/agents.md`. Reusable technical
procedures are in `.agents/skills/`. Multi-step automations are in
`.agents/workflows/` (invoke with `/workflow-name`). Lessons learned from
past mistakes are logged in `GUARDRAILS.md` — read it before starting
non-trivial work, and append to it when you find and fix a real bug or
near-miss, not just any change.

## Coding Standards

- Python 3.10+, type hints on all public functions, `black`-formatted.
- Every new service module gets tests in the same PR/commit — no
  "tests later" for anything touching safety, memory, or consent.
- Commit messages reference the PRD or System Design section a change
  implements or closes, e.g. `feat(safety): wire NeMoGuard client per
  System Design §4.3`.

## When Unsure

Prefer asking a clarifying question over guessing on anything that touches:
safety classification, data retention/deletion, consent, or cross-tenant
data access. Everything else — implementation detail, code style,
non-safety-critical UX — use best judgment and proceed.
