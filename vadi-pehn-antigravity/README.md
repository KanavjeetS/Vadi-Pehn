# Vadi-Pehn — Antigravity Agent Configuration

This is the full multi-agent build system for the Vadi-Pehn project,
configured for Google Antigravity IDE. It doesn't contain application
code — it contains the **team, skills, and automated workflows** that will
build the application code, wired specifically to `docs/PRD-v2.md` and
`docs/system-design.md` (both included here), not generic best practices.

## What's in here

```
AGENTS.md                          standing rules, read before every task
GUARDRAILS.md                      learned failure patterns (seeded with 5 real ones)
docs/
  PRD-v2.md                        product requirements + governance (source of truth)
  system-design.md                 architecture, schemas, API contracts (source of truth)
.agents/
  agents.md                        9 personas, one per service-ownership boundary
  rules/
    coding-standards.md
    child-safety-non-negotiables.md
  skills/                          14 modular technical procedures, one per build segment
  workflows/                       5 slash commands, including the two "loop" agents
research/findings/                 where /research-loop writes its output
eval/safety_redteam_corpus/        where the safety-proxy adversarial test set lives
```

## Installation

1. Merge this directory into the same repo root as the
   `vadi-pehn-sibling-voice-rag` foundation build (the `src/sibling/`,
   `tests/`, `prompts/` tree from the first build segment). This config
   assumes that code already exists at the repo root — it references
   `src/sibling/orchestration_graph.py`, `src/sibling/safety.py`, etc.
   directly.
2. Open the merged repo as an Antigravity workspace.
3. Antigravity will automatically pick up `AGENTS.md` at the root and
   everything under `.agents/`.

## The two "loop" agents you asked for

- **`/qa-loop <target>`** — iteratively finds and fixes issues (tests,
  tenant-isolation leaks, safety bypasses) until a clean pass or a bounded
  iteration cap, whichever comes first. Fixes trivial bugs directly;
  hands judgment calls to the owning persona. Logs recurring patterns to
  `GUARDRAILS.md` so they don't reappear in a later segment.
- **`/research-loop <topic>`** — iteratively scans the project's actual
  stack (LangGraph, vLLM, NeMo Guardrails, Whisper, Kokoro, pgvector,
  olmOCR, etc.) for relevant updates and better techniques, classifies
  each by risk, and either logs a proposal or (only for explicitly
  low-risk, reversible changes, and only if you pass
  `--auto-apply-low-risk`) applies and verifies it itself. It never
  touches safety-critical code, schema, or consent logic on its own,
  regardless of flags.

Both are bounded (default 3–5 iterations) so they terminate predictably —
"loop forever" isn't actually what you want from an agent with write
access to a codebase; a loop that reports "still failing after N tries,
here's exactly why" is more useful than one that silently keeps going.

## Other workflows

- **`/build-segment <name>`** — build one service end to end (spec check →
  build → tests → QA rework loop → doc sync).
- **`/full-cycle`** — runs all remaining segments in dependency order, with
  a mandatory human-approval gate after any segment touching schema,
  consent, or the safety-critical path (memory-service, safety-proxy,
  governance-service) before continuing to the next one.
- **`/safety-audit`** — a standalone, periodic deep audit independent of
  any specific build segment. Run this weekly during active development,
  and always before showing the project to anyone outside the team.

## Suggested first commands

```
/build-segment memory-service
/build-segment safety-proxy      # requires human approval to proceed past
/safety-audit
/build-segment voice-gateway
/research-loop all
```

## Why nine personas and not four

The original Antigravity codelab pattern uses a generic four-role team
(PM/Engineer/QA/DevOps). That's the right shape for a typical CRUD app.
This project has three service boundaries a generic team would blur
together — orchestration, voice, and safety are genuinely different
disciplines with different failure modes — plus governance/privacy and
research/documentation concerns that a child-safety product can't treat
as afterthoughts. Nine focused personas with real veto power
(`@safety-engineer` in particular) cost more setup than four generic ones,
and are worth it for exactly the reasons in PRD §3–4.
