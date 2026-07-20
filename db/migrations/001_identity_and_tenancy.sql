-- ============================================================
-- Migration: 001_identity_and_tenancy.sql
-- Implements: SD §3.1 — Identity & Tenancy tables
-- PRD: §3.1 (legal frameworks), §3.2 (guardian consent model)
-- DB: Memory Service (postgres-memory)
-- ============================================================

-- Extensions required by this service
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Tenants ──────────────────────────────────────────────────────────────────
-- Top-level organizational unit. Maps to an NGO, school, or deployment partner.
-- `region` drives which legal framework applies (PRD §3.1 — DPDP/COPPA/GDPR-K).
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    region      TEXT NOT NULL,   -- 'in' (India/DPDP), 'us' (COPPA), 'eu' (GDPR-K)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Guardians ─────────────────────────────────────────────────────────────────
-- Every learner MUST have an associated guardian (PRD §3.2).
-- Verification method must be appropriate for low-resource settings (no credit card).
CREATE TABLE IF NOT EXISTS guardians (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number        TEXT,
    email               TEXT,
    verification_method TEXT NOT NULL CHECK (verification_method IN (
        'ngo_cosign',       -- NGO caseworker co-signs enrollment
        'guardian_otp',     -- OTP to guardian phone
        'in_person'         -- in-person enrollment at partner site
    )),
    verified_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Learners ──────────────────────────────────────────────────────────────────
-- A learner without a guardian cannot exist (guardian_id is NOT NULL).
-- age_band: 1=8-10, 2=11-13, 3=14-17 — affects tone, content, session limits.
CREATE TABLE IF NOT EXISTS learners (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    guardian_id         UUID NOT NULL REFERENCES guardians(id),
    first_name          TEXT NOT NULL,
    age_band            SMALLINT NOT NULL CHECK (age_band IN (1, 2, 3)),
    preferred_language  TEXT NOT NULL DEFAULT 'hi',
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'deleted')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
