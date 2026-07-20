-- ============================================================
-- Migration: 002_learner_memory_rls.sql
-- Implements: SD §3.2 — Conversational Memory with pgvector + RLS
-- PRD: §7 (multi-tenant memory), §3.4 (18-month retention)
-- DB: Memory Service (postgres-memory)
-- CRITICAL: Both ENABLE and FORCE ROW LEVEL SECURITY required (GUARDRAILS G-002)
-- ============================================================

-- ── Learner Memories ─────────────────────────────────────────────────────────
-- Primary conversational memory store. One row per turn summary.
-- HNSW index for fast approximate nearest-neighbor search (pgvector 0.8+).
-- 18-month rolling TTL via expires_at — pruned by nightly job (PRD §3.4).
CREATE TABLE IF NOT EXISTS learner_memories (
    id                      BIGSERIAL PRIMARY KEY,
    tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    learner_id              UUID NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    conversation_session_id UUID NOT NULL,
    embedding               vector(1536) NOT NULL,
    content                 TEXT NOT NULL,
    metadata                JSONB,
    -- metadata shape: {"source": "voice"|"text", "turn_id": "...", "sentiment_tag": "..."}
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at              TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '18 months')
    -- PRD §3.4: 18-month rolling retention. Nightly prune job deletes WHERE expires_at < NOW().
);

-- Supporting indexes
CREATE INDEX IF NOT EXISTS idx_memories_tenant_learner
    ON learner_memories(tenant_id, learner_id);

CREATE INDEX IF NOT EXISTS idx_memories_expiry
    ON learner_memories(expires_at);
    -- Used by nightly prune job (PRD §3.4).

-- HNSW vector index — SD §7.1 corrected configuration
-- m=16 (connectivity), ef_construction=256 (build quality) per SD §3.2
CREATE INDEX IF NOT EXISTS idx_memories_vector_hnsw
    ON learner_memories
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 256);

-- ── Row Level Security (GUARDRAILS G-002) ────────────────────────────────────
-- Both ALTER statements are REQUIRED. CREATE POLICY alone is NOT enough:
-- FORCE RLS prevents the table owner (app user) from bypassing the policy.
-- A connection pool bug or missing SET LOCAL call MUST return zero rows, not all rows.
ALTER TABLE learner_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE learner_memories FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON learner_memories
FOR ALL
USING (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);
-- NULLIF(..., '') handles the case where the setting is empty string (unset connection).
-- An unset app.current_tenant_id returns NULL, which never equals any tenant_id UUID.
-- Therefore: no SET LOCAL → zero rows returned (not an error, not all rows). ✓

-- ── Learner Interest Profile ──────────────────────────────────────────────────
-- Panel matching input (PRD §5.1). Separate from raw conversational memory.
-- Updated by Orchestration after each turn (interest drift tracking).
CREATE TABLE IF NOT EXISTS learner_interest_profile (
    learner_id          UUID PRIMARY KEY REFERENCES learners(id) ON DELETE CASCADE,
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    interest_embedding  vector(1536) NOT NULL,
    top_interests       TEXT[] NOT NULL DEFAULT '{}',
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE learner_interest_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE learner_interest_profile FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON learner_interest_profile
FOR ALL
USING (
    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
);
