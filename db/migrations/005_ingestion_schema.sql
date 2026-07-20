-- ============================================================
-- Migration: 005_ingestion_schema.sql
-- Implements: SD §3.5 — Document Ingestion & Discrepancy Log
-- PRD: §9 (Multi-Modal Document Ingestion, olmOCR extraction, discrepancy queue)
-- TARGET DB: Memory Service DB (`vadi_memory` / postgres-memory on port 5432)
-- ============================================================

-- ── Document Uploads (PRD §9, SD §3.5) ───────────────────────────────────────
-- Tracks uploaded report cards, scans, and academic evidence stored in MinIO.
-- PII redaction must complete and verify BEFORE olmOCR extraction occurs.
-- Retention: enrollment + 90 days (expires_at set during ingestion flow).
CREATE TABLE IF NOT EXISTS document_uploads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    learner_id      UUID NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
    minio_object_key TEXT NOT NULL,
    redaction_status TEXT NOT NULL DEFAULT 'pending' CHECK (redaction_status IN (
                        'pending',
                        'redacted',
                        'verified'
                    )),
    ocr_status      TEXT NOT NULL DEFAULT 'pending' CHECK (ocr_status IN (
                        'pending',
                        'extracted',
                        'failed'
                    )),
    ocr_confidence  NUMERIC(4, 3),
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '1 year')
);

CREATE INDEX IF NOT EXISTS idx_uploads_tenant_learner
    ON document_uploads(tenant_id, learner_id);

CREATE INDEX IF NOT EXISTS idx_uploads_expiry
    ON document_uploads(expires_at);

-- ── Discrepancy Log (PRD §9, SD §3.5) ────────────────────────────────────────
-- Logged whenever olmOCR extracted data disagrees with in-app/guardian reported data
-- or when ocr_confidence is below the 0.85 threshold.
CREATE TABLE IF NOT EXISTS discrepancy_log (
    id              BIGSERIAL PRIMARY KEY,
    document_id     UUID NOT NULL REFERENCES document_uploads(id) ON DELETE CASCADE,
    field_name      TEXT NOT NULL,
    extracted_value TEXT,
    in_app_value    TEXT,
    status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                        'open',
                        'resolved_use_extracted',
                        'resolved_use_app',
                        'resolved_manual'
                    )),
    reviewer_id     UUID,
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_discrepancy_status
    ON discrepancy_log(status)
    WHERE status = 'open';
