# Skill: Write Tests

## Objective
A shared skill any engineer persona invokes when writing tests for their
segment, implementing PRD §14's testing strategy consistently across the
codebase rather than each persona inventing its own conventions.

## Rules of Engagement
- Match the existing test style in `tests/` (pytest, `pytest-asyncio`,
  `respx` for HTTP mocking, dataclass-based fixtures — see
  `tests/test_safety.py` for the canonical fail-closed testing pattern).
- Every test for a safety-relevant path must include at least one
  adversarial case (timeout, malformed response, boundary value), not
  only the happy path.
- Every test for a data-access path must include at least one
  cross-tenant/cross-learner isolation case, following
  `tests/test_memory_store.py::test_tenant_isolation_never_leaks_across_tenants`.

## Instructions
1. Identify which PRD §14 layer the code under test belongs to (RLS/
   isolation, safety classifier, voice latency, panel logic, end-to-end,
   or pilot feedback instrument) and follow that layer's method.
2. For RLS/isolation: write both a Python-level test (against
   `InMemoryVectorStore` or `PostgresMemoryStore`) AND, if touching real
   schema, a pgTAP SQL test per `build-memory-service.md`.
3. For safety classifier changes: add cases to
   `eval/safety_redteam_corpus/` and a corresponding assertion in the test
   suite — don't just eyeball a manual chat test.
4. For anything on the conversation turn path: extend
   `tests/test_orchestration_graph.py` with a full `graph.ainvoke()` case,
   not just a unit test of the node function in isolation, so the
   real control-flow wiring is exercised.
5. Run the full suite (`pytest -v`) and confirm no regressions before
   handing off. Report the before/after test count.
