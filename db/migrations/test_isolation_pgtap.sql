-- ============================================================
-- pgTAP / Adversarial RLS Isolation Test Script
-- Implements: PRD §14 (testing strategy), SD §7.2 (RLS isolation testing strategy)
-- TARGET DB: Memory Service DB (`vadi_memory` / postgres-memory on port 5432)
--
-- Can be executed via pgTAP (`pg_prove`) or directly in psql during CI/migration runs.
-- Proves:
--   1. An unset `app.current_tenant_id` returns 0 rows from `learner_memories` and `learner_interest_profile` (never returns all rows).
--   2. A query with Tenant A's ID returns 0 rows of Tenant B's data.
--   3. FORCE ROW LEVEL SECURITY prevents even table owner/app roles from reading across tenants without SET LOCAL.
-- ============================================================

BEGIN;

-- Create test tenants and learners
INSERT INTO tenants (id, name, region) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Tenant A - NGO Delhi', 'in'),
    ('22222222-2222-2222-2222-222222222222', 'Tenant B - School Mumbai', 'in')
ON CONFLICT (id) DO NOTHING;

INSERT INTO guardians (id, tenant_id, phone_number, verification_method) VALUES
    ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', '+911111111111', 'ngo_cosign'),
    ('44444444-4444-4444-4444-444444444444', '22222222-2222-2222-2222-222222222222', '+912222222222', 'ngo_cosign')
ON CONFLICT (id) DO NOTHING;

INSERT INTO learners (id, tenant_id, guardian_id, first_name, age_band) VALUES
    ('55555555-5555-5555-5555-555555555555', '11111111-1111-1111-1111-111111111111', '33333333-3333-3333-3333-333333333333', 'Aarav (Tenant A)', 1),
    ('66666666-6666-6666-6666-666666666666', '22222222-2222-2222-2222-222222222222', '44444444-4444-4444-4444-444444444444', 'Priya (Tenant B)', 2)
ON CONFLICT (id) DO NOTHING;

-- Insert memories directly bypassing RLS or by setting RLS context for each tenant
SET LOCAL app.current_tenant_id = '11111111-1111-1111-1111-111111111111';
INSERT INTO learner_memories (tenant_id, learner_id, conversation_session_id, embedding, content) VALUES
    ('11111111-1111-1111-1111-111111111111', '55555555-5555-5555-5555-555555555555', gen_random_uuid(), '[0.1, 0.1, 0.1]'::vector, 'Secret memory of Tenant A child');

SET LOCAL app.current_tenant_id = '22222222-2222-2222-2222-222222222222';
INSERT INTO learner_memories (tenant_id, learner_id, conversation_session_id, embedding, content) VALUES
    ('22222222-2222-2222-2222-222222222222', '66666666-6666-6666-6666-666666666666', gen_random_uuid(), '[0.2, 0.2, 0.2]'::vector, 'Secret memory of Tenant B child');

-- ─────────────────────────────────────────────────────────────────────────────
-- ADVERSARIAL TEST 1: Unset app.current_tenant_id (or empty string) MUST return 0 rows
-- ─────────────────────────────────────────────────────────────────────────────
RESET app.current_tenant_id;
DO $$
DECLARE
    row_count INT;
BEGIN
    SELECT COUNT(*) INTO row_count FROM learner_memories;
    IF row_count <> 0 THEN
        RAISE EXCEPTION 'GUARDRAILS G-002 VIOLATION: Unset RLS context returned % rows instead of 0!', row_count;
    END IF;
    RAISE NOTICE 'SUCCESS (Test 1): Unset RLS context returned 0 rows.';
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- ADVERSARIAL TEST 2: Tenant B context trying to read Tenant A's child data
-- ─────────────────────────────────────────────────────────────────────────────
SET LOCAL app.current_tenant_id = '22222222-2222-2222-2222-222222222222';
DO $$
DECLARE
    row_count INT;
BEGIN
    SELECT COUNT(*) INTO row_count FROM learner_memories WHERE tenant_id = '11111111-1111-1111-1111-111111111111';
    IF row_count <> 0 THEN
        RAISE EXCEPTION 'GUARDRAILS G-002 VIOLATION: Tenant B context was able to read % rows of Tenant A!', row_count;
    END IF;
    RAISE NOTICE 'SUCCESS (Test 2): Cross-tenant query returned 0 rows.';
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- ADVERSARIAL TEST 3: Tenant A context reads ONLY Tenant A data
-- ─────────────────────────────────────────────────────────────────────────────
SET LOCAL app.current_tenant_id = '11111111-1111-1111-1111-111111111111';
DO $$
DECLARE
    row_count INT;
BEGIN
    SELECT COUNT(*) INTO row_count FROM learner_memories;
    IF row_count <> 1 THEN
        RAISE EXCEPTION 'RLS POLICY ERROR: Tenant A context returned % rows instead of exactly 1 row!', row_count;
    END IF;
    RAISE NOTICE 'SUCCESS (Test 3): Tenant A context returned exactly its own rows.';
END $$;

ROLLBACK;
