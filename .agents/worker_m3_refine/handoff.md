# Handoff Report — Milestone 3 Refinement (Divisions 3 & 4)

## 1. Observation

- **Division 4 (AI Safety)**:
  - File: `services/safety-proxy/src/safety_proxy/actions.py`
    - Lines 28-39: Updated `SELF_HARM_KEYWORDS` to include Hinglish keywords: `"marna chahta"`, `"marna chahti"`, `"jeena nahi chahta"`, `"khatam karna chahta"`, `"khud ko hurt"`.
    - Lines 98-105 & 164-171: Removed `allow_dev_bypass` branches directly inside `classify_input` and `classify_output`, returning `SafetyVerdict.unavailable()` (`CLASSIFIER_UNAVAILABLE`) when `http_client is None`.
  - File: `services/safety-proxy/src/safety_proxy/main.py`
    - Lines 90-95 & 126-131: Preserved dev bypass conversion in `/check-input` and `/check-output` endpoints from `CLASSIFIER_UNAVAILABLE` to `SAFE` when `allow_dev_bypass and is_dev` is True.
  - File: `services/safety-proxy/tests/test_safety_proxy.py`
    - Added unit test coverage for Hinglish self-harm keywords and updated redteam corpus testing to route non-keyword queries through `NeMoSafetyClient` and `TestClient(app)`.

- **Division 3 (AI Platform)**:
  - Memory Writes:
    - File: `services/orchestration/src/orchestration/graph.py` (lines 560-578) & `services/memory-service/src/memory_service/write_pipeline.py` (lines 84-184).
    - Verified `AsyncMemoryWriter.write_memory_async()` saves dialogue formatted as `"Child: {message}\nVadi: {reply}"` into `learner_memories`.
    - File: `services/memory-service/tests/test_async_writer_consent.py` (lines 115-140) & `services/orchestration/tests/test_graph.py` (lines 398-415): Added explicit unit tests verifying this format.
  - Memory Reads:
    - File: `services/orchestration/src/orchestration/retrieval.py` created with `OrchestrationRetrieval.retrieve_context`.
    - Executes `LIMIT 5` recency-based `memory_store.query()` fallback when vector embedding client is unavailable or fails.
    - File: `services/orchestration/src/orchestration/graph.py` (lines 302-323): Integrated `OrchestrationRetrieval` into `retrieve_memory` node.
  - Persona Templates:
    - Verified `services/orchestration/personas/sibling.jinja2` system prompt rendering.
    - Created career persona templates in `services/orchestration/personas/`: `doctor.jinja2`, `engineer.jinja2`, `artist.jinja2`.
    - File: `services/orchestration/src/orchestration/graph.py` (lines 385-458): Added `_resolve_career_persona_template(state)` and rendering logic in `generate_reply` when `panel_triggered=True`.

- **Test Commands Executed**:
  - `py -3 -m pytest services/safety-proxy/ services/orchestration/ services/memory-service/`
  - Output: 61 tests passed out of 61.

## 2. Logic Chain

1. *Hinglish Self-Harm Keywords*: Adding `"marna chahta"`, `"marna chahti"`, `"jeena nahi chahta"`, `"khatam karna chahta"`, `"khud ko hurt"` to `SELF_HARM_KEYWORDS` in `actions.py` allows the fast local pre-filter to catch Hinglish self-harm expressions immediately and return `UNSAFE_SELF_HARM` (S6), triggering `handle_unsafe_input` and `create_governance_incident`.
2. *Fail-Closed Safety Proxy Structure*: `classify_input` and `classify_output` in `actions.py` now return pure fail-closed verdicts (`CLASSIFIER_UNAVAILABLE`) on network timeout or when no HTTP client is supplied. `/check-input` and `/check-output` in `main.py` handle converting `CLASSIFIER_UNAVAILABLE` to `SAFE` ONLY when `allow_dev_bypass` and `is_dev` are active.
3. *Recency Memory Retrieval Fallback*: When the vector embedding client is offline or unavailable, `OrchestrationRetrieval` queries `memory_store.query(..., k=5)` which fetches the 5 most recent dialogue chunks. This ensures the prompt memory context is never empty.
4. *Career Panel Jinja2 Rendering*: When `state.panel_triggered=True`, `_resolve_career_persona_template` identifies the target career (e.g. `doctor.jinja2`, `engineer.jinja2`, `artist.jinja2`), renders the corresponding `.jinja2` template file with the learner's age band and language, and appends it to the system prompt context.
5. *Memory Writes Formatting*: Dialogue written via `write_memory_async` is formatted as `"Child: {message}\nVadi: {reply}"`, persisting the turn in `learner_memories`.

## 3. Caveats

No caveats. All tasks completed and verified with real implementations and unit tests without hardcoding or facades.

## 4. Conclusion

Milestone 3 (Divisions 3 & 4) requirements are fully implemented, fail-closed safety invariants are maintained, and all test suites pass cleanly across `safety-proxy`, `orchestration`, and `memory-service`.

## 5. Verification Method

To verify these changes independently:
1. Run the test suite:
   ```bash
   py -3 -m pytest services/safety-proxy/ services/orchestration/ services/memory-service/
   ```
2. Inspect `services/safety-proxy/src/safety_proxy/actions.py` to confirm `SELF_HARM_KEYWORDS` contains Hinglish keywords and `classify_input`/`classify_output` have no inline dev bypass logic.
3. Inspect `services/orchestration/src/orchestration/retrieval.py` and `graph.py` to confirm `LIMIT 5` recency query fallback and career persona Jinja2 template rendering.
4. Inspect `services/orchestration/personas/` for `doctor.jinja2`, `engineer.jinja2`, `artist.jinja2`.
