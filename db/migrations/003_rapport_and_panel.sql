-- ============================================================
-- Migration: 003_rapport_and_panel.sql
-- Implements: SD §3.3 — Rapport State + Professional Personas
-- PRD: §4 (rapport score gate), §5.1 (panel composition, relationship bandwidth)
-- DB: Memory Service (postgres-memory)
-- ============================================================

-- ── Rapport Scores ────────────────────────────────────────────────────────────
-- IMPORTANT: composite_score is a generated column — application cannot write it directly.
-- Weights (0.4/0.3/0.3) are empirical starting point; recalibrate during Phase 7 pilot.
-- WARNING: This score is ONLY an introduction gate (≥ 0.6 threshold per PRD §5.1).
-- It must NEVER be surfaced as, or optimized as, a growth/engagement KPI (PRD §4).
CREATE TABLE IF NOT EXISTS rapport_scores (
    learner_id                  UUID PRIMARY KEY REFERENCES learners(id) ON DELETE CASCADE,
    tenant_id                   UUID NOT NULL REFERENCES tenants(id),
    frequency_component         NUMERIC(4, 3) NOT NULL DEFAULT 0,
    duration_trend_component    NUMERIC(4, 3) NOT NULL DEFAULT 0,
    feedback_component          NUMERIC(4, 3) NOT NULL DEFAULT 0,
    composite_score             NUMERIC(4, 3) GENERATED ALWAYS AS (
        frequency_component * 0.4
        + duration_trend_component * 0.3
        + feedback_component * 0.3
    ) STORED,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Professional Personas ─────────────────────────────────────────────────────
-- Shared across all tenants — these are the career mentor personas.
-- persona_system_prompt_ref is a FILE PATH (versioned .jinja2 file), never inline text.
-- approved_fact_source_ref points to the database the Output Guard validates against.
CREATE TABLE IF NOT EXISTS professional_personas (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name                TEXT NOT NULL,
    profession_taxonomy_code    TEXT NOT NULL,
    persona_system_prompt_ref   TEXT NOT NULL,  -- e.g. "personas/career/engineer_v2.jinja2"
    approved_fact_source_ref    TEXT NOT NULL,  -- e.g. "fact_db/engineering_india_2025.json"
    active                      BOOLEAN NOT NULL DEFAULT TRUE
);

-- ── Introduced Relationships ──────────────────────────────────────────────────
-- Tracks which professional persona each learner has been "introduced" to.
-- Relationship Bandwidth Rule (PRD §5.1): max 3 active relationships per learner.
-- "Active" = lapsed_at IS NULL. Enforcement: application-level check before INSERT.
-- A 4th intro requires the lowest-engagement existing one to have lapsed_at SET
-- (45+ days inactive, set by a scheduled job — not automatic DB logic).
CREATE TABLE IF NOT EXISTS introduced_relationships (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    learner_id          UUID NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    persona_id          UUID NOT NULL REFERENCES professional_personas(id),
    introduced_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_interacted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lapsed_at           TIMESTAMPTZ,       -- NULL = active; set when > 45 days inactive
    UNIQUE (learner_id, persona_id)
);

CREATE INDEX IF NOT EXISTS idx_relationships_learner_active
    ON introduced_relationships(learner_id)
    WHERE lapsed_at IS NULL;
-- Partial index on active-only rows makes the bandwidth check (COUNT active per learner) fast.
