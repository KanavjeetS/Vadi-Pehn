-- ============================================================
-- Migration: 004_governance_schema.sql
-- Implements: SD §3.4 — Governance schema (Consent Ledger, Incidents, Access Log)
-- PRD: §3.2 (Consent Ledger), §3.3 (Mandatory Reporting / Safety Queue), §3.4 (7-year hold), §9.1 (Reviewer Access Log)
-- TARGET DB: Governance Service DB (`vadi_governance` / postgres-governance on port 5433)
-- CRITICAL NOTE: Physically separate from `postgres-memory` per SD Architecture Non-Negotiable.
-- ============================================================

-- ── Consent Records (PRD §3.2, SD §3.4) ──────────────────────────────────────
-- Granular consent stored per learner & consent_type.
-- Consent types: 'conversation_storage', 'document_ingestion', 'voice_recording', 'career_introductions'.
-- Each type is independently revocable. Consent withdrawal triggers a data-deletion job.
CREATE TABLE IF NOT EXISTS consent_records (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL,
    learner_id          UUID NOT NULL,
    guardian_id         UUID NOT NULL,
    consent_type        TEXT NOT NULL CHECK (consent_type IN (
                            'conversation_storage',
                            'document_ingestion',
                            'voice_recording',
                            'career_introductions'
                        )),
    granted             BOOLEAN NOT NULL DEFAULT FALSE,
    granted_at          TIMESTAMPTZ,
    revoked_at          TIMESTAMPTZ,
    verification_method TEXT NOT NULL, -- e.g. 'ngo_cosign', 'guardian_otp', 'in_person'
    UNIQUE (learner_id, consent_type)
);

CREATE INDEX IF NOT EXISTS idx_consent_learner_status
    ON consent_records(learner_id, consent_type, granted);

-- ── Safety Incidents (PRD §3.3, SD §3.4) ─────────────────────────────────────
-- Mandatory reporting queue. 15-minute SLA for reviewer paging on self_harm / abuse_disclosure.
-- CRITICAL RULE: No RLS FORCE-deletion cascade on this table ever — 7-year legal hold (PRD §3.4)
-- overrides tenant offboarding; tenant_id is retained for audit even if a tenant is deactivated.
CREATE TABLE IF NOT EXISTS safety_incidents (
    id                          BIGSERIAL PRIMARY KEY,
    tenant_id                   UUID NOT NULL,
    learner_id                  UUID NOT NULL,
    severity                    TEXT NOT NULL CHECK (severity IN (
                                    'self_harm',
                                    'abuse_disclosure',
                                    'criminal_planning',
                                    'classifier_unavailable',
                                    'other'
                                )),
    transcript_excerpt          TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewer_id                 UUID,
    reviewer_acknowledged_at    TIMESTAMPTZ,
    guardian_contacted_at       TIMESTAMPTZ,
    mandatory_report_filed_at   TIMESTAMPTZ,
    resolution_notes            TEXT,
    sla_deadline                TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '15 minutes')
);

CREATE INDEX IF NOT EXISTS idx_incidents_unacknowledged
    ON safety_incidents(created_at, severity)
    WHERE reviewer_acknowledged_at IS NULL;

-- ── Reviewer Access Log (PRD §9.1, SD §3.4) ──────────────────────────────────
-- Background-checked reviewers have scoped access to flagged records only.
-- Every read/view access to sensitive disclosures or document scans MUST be logged.
CREATE TABLE IF NOT EXISTS reviewer_access_log (
    id                  BIGSERIAL PRIMARY KEY,
    reviewer_id         UUID NOT NULL,
    accessed_record_type TEXT NOT NULL,   -- 'safety_incident' | 'discrepancy_record'
    accessed_record_id  BIGINT NOT NULL,
    accessed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_access_log_reviewer
    ON reviewer_access_log(reviewer_id, accessed_at);
