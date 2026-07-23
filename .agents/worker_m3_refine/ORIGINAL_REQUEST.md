## 2026-07-23T14:27:21Z

You are the AI Platform & Safety Engineer (@backend-engineer & @safety-engineer) for Milestone 3 of Vadi-Pehn Full MVP Refinement.
Working directory: d:\Vadi Bhen
Metadata directory: d:\Vadi Bhen\.agents\worker_m3_refine

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks for Milestone 3 (Divisions 3 & 4):
1. Division 4 (AI Safety):
   - Add Hinglish self-harm keywords to `SELF_HARM_KEYWORDS` in `services/safety-proxy/src/safety_proxy/actions.py`: `"marna chahta"`, `"marna chahti"`, `"jeena nahi chahta"`, `"khatam karna chahta"`, `"khud ko hurt"`.
   - Maintain the safety-proxy dev bypass structure: `actions.py` `classify_input` and `classify_output` remain fail-closed without dev bypass logic; `safety-proxy/main.py` converts `CLASSIFIER_UNAVAILABLE` to `SAFE` when `allow_dev_bypass and is_dev` is True in `/check-input` and `/check-output`.
   - Verify prompt injection deflection ("ignore previous instructions") and self-harm escalation handling ("kill myself").

2. Division 3 (AI Platform):
   - Memory Writes: Ensure `AsyncMemoryWriter.write_memory_async()` saves `"Child: {message}\nVadi: {reply}"` into `learner_memories` in Supabase/Postgres.
   - Memory Reads: In `services/orchestration/src/orchestration/retrieval.py` / `graph.py`, implement `LIMIT 5` recency-based query fallback when vector embedding client is unavailable so context is always populated.
   - Persona Templates: Verify `sibling.jinja2` system prompt rendering.
   - Career Panel: When `panel_triggered=True`, look up the matching career persona template (e.g. `doctor.jinja2`, `engineer.jinja2`, `artist.jinja2`) and render that `.jinja2` file into system prompt context.

Run tests across `safety-proxy` and `orchestration` (`py -3 -m pytest services/safety-proxy/ services/orchestration/`).
Write a handoff report at `d:\Vadi Bhen\.agents\worker_m3_refine\handoff.md` with all changes and test results.
