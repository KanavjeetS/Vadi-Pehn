# Skill: Build Safety Proxy Service

## Objective
As the Child Safety & Governance Engineer, build the real, standalone
Safety Proxy service that `NeMoGuardSafetyClient` (already implemented in
`src/sibling/safety.py`) talks to — a genuine network-level reverse proxy,
per the System Design §2 design decision, not a library.

## Rules of Engagement
- This is the single most safety-critical segment in the project. Every
  decision here defaults to the more conservative option.
- The service must implement BOTH endpoints exactly as specified in System
  Design §4.3: `POST /internal/v1/safety/check-input` and
  `POST /internal/v1/safety/check-output`, with the exact response shape
  `{verdict, taxonomy_code}` that `NeMoGuardSafetyClient` already expects
  — do not change the client to match a different shape.
- Read GUARDRAILS.md G-001 and G-004 before writing any code here.

## Instructions
1. Stand up NVIDIA NeMo Guardrails per PRD §8, using the corrected,
   fail-closed `actions.py` pattern already fixed in PRD §8.1 (the
   `choices[0]` fix and the try/except that returns
   `classifier_unavailable` rather than raising).
2. Configure `config.yml` and `rails/jailbreak.co` per PRD §8's YAML/Colang
   examples, wired to the Aegis 2.0 taxonomy via Llama-Guard-3-8B (or the
   configured classifier model).
3. Implement the two endpoints as a thin FastAPI wrapper around the
   Guardrails runtime, matching System Design §4.3's contract exactly,
   including the 3-second timeout budget.
4. On `unsafe_self_harm`, the service itself does NOT deliver the
   supportive script (that's the Orchestration Service's job per System
   Design §5.3) — it only returns the verdict and taxonomy code.
5. Write a test suite that runs the PRD §8.4 adversarial red-team corpus
   (start a `eval/safety_redteam_corpus/` with at least 20 seed examples
   across self-harm, jailbreak, and general-unsafe categories — synthetic
   only, per `.agents/rules/child-safety-non-negotiables.md` rule 4) and
   asserts expected verdicts.
6. Verify end-to-end against `NeMoGuardSafetyClient`'s existing tests in
   `tests/test_safety.py` — those tests currently mock the HTTP layer;
   after this skill, also add a live-integration variant (skippable
   without a running proxy).
7. This segment is never marked "done" by this persona alone — it
   requires `@qa-auditor` to run `/safety-audit` and get a clean pass.
