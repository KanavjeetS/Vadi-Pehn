# Skill: Build Memory Service (Postgres + pgvector + RLS)

## Objective
As the Data & Privacy Engineer, implement the `PostgresMemoryStore` class
currently stubbed in `src/sibling/memory_store.py`, wiring it to a real
Postgres+pgvector instance per System Design §3.2 and §7.1, replacing the
`InMemoryVectorStore` used in dev/tests (which stays as the test backend —
do not delete it).

## Rules of Engagement
- Schema is not open for redesign here — implement exactly what's in
  System Design §3.2 (`learner_memories`, `learner_interest_profile`) and
  §7.1's corrected per-transaction iterative-scan configuration.
- Every method must open a transaction and issue `SET LOCAL
  app.current_tenant_id = $1` before any query, per §7.1 — this is not
  optional even for `write()`.
- `FORCE ROW LEVEL SECURITY` must be enabled — verify this in the
  migration, don't just assume the CREATE POLICY is enough.

## Instructions
1. Write the migration in `db/migrations/` creating `learner_memories` and
   `learner_interest_profile` exactly as specified in System Design §3.2,
   including the HNSW index and RLS policy.
2. Implement `PostgresMemoryStore.write/query/delete_for_learner/
   prune_expired` using `asyncpg`, following the exact per-transaction
   parameter injection pattern from System Design §7.1:
   ```
   SET LOCAL app.current_tenant_id = $1;
   SET LOCAL hnsw.iterative_scan = relaxed_order;
   SET LOCAL hnsw.max_scan_tuples = 20000;
   ```
3. Write a pgTAP test file alongside the migration
   (`db/migrations/<timestamp>_learner_memories.test.sql`) that asserts:
   a session scoped to tenant A gets zero rows querying for tenant B's
   seeded data, AND a session with `app.current_tenant_id` unset gets zero
   rows rather than an error or all rows (System Design §7.2's adversarial
   test).
4. Add a Python integration test (skippable if no live Postgres is
   configured, via a pytest marker) that runs the same assertions through
   `PostgresMemoryStore` directly.
5. Update `docker-compose.dev.yml` if any new extensions or init scripts
   are needed.
6. Hand off to `@qa-auditor` (or run `/qa-loop memory-service`) before
   marking this segment done.
