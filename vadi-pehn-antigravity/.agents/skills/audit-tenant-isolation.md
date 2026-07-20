# Skill: Audit Tenant Isolation

## Objective
As the QA & Security Auditor, adversarially probe every per-learner data
path for cross-tenant or cross-learner leakage, per System Design §7.2.

## Rules of Engagement
- You are not verifying the code does what its author intended — you are
  trying to make it leak. Assume the author missed something.
- A "zero rows returned" result on a malformed/missing-tenant-context
  query is a PASS. A 500 error, or worse, rows from another tenant, is a
  FAIL.

## Instructions
1. Enumerate every table/store with a `tenant_id`/`learner_id` scope
   (currently: `learner_memories`, `learner_interest_profile`,
   `rapport_scores`, `introduced_relationships`, `consent_records`,
   `safety_incidents`, `document_uploads`; re-enumerate against the actual
   schema each time this skill runs, since new tables get added).
2. For each: write/run a test that (a) seeds data for tenant A, (b)
   queries as tenant B with the same learner_id reused, (c) asserts zero
   results. This is `test_two_learners_in_same_tenant_never_share_memory`'s
   pattern, generalized.
3. For each: write/run a test that queries with `tenant_id`/
   `app.current_tenant_id` completely unset, and asserts zero results or a
   clean `TenantIsolationError` — never an unfiltered result set.
4. For the Postgres-backed stores specifically, confirm
   `FORCE ROW LEVEL SECURITY` is actually set (query
   `pg_tables`/`pg_policies`, don't just read the migration file — verify
   the live schema).
5. Check every new API endpoint added since the last audit for a case
   where `tenant_id`/`learner_id` is taken from a request body/query param
   instead of the authenticated session context — this is the single most
   common way tenant isolation gets accidentally broken. Flag any instance
   immediately, don't wait for the full report.
6. Produce a pass/fail table per table/store and hand findings to the
   owning engineer persona for fixes; re-run after fixes land.
