-- Governance database: physically separate from memory DB.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS consent_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    learner_id UUID NOT NULL,
    guardian_id UUID NOT NULL,
    conversation_storage BOOLEAN NOT NULL DEFAULT FALSE,
    document_ingestion BOOLEAN NOT NULL DEFAULT FALSE,
    voice_recording BOOLEAN NOT NULL DEFAULT FALSE,
    career_introductions BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, learner_id)
);

CREATE TABLE IF NOT EXISTS safety_incidents (
    incident_id TEXT PRIMARY KEY,
    tenant_id UUID NOT NULL,
    learner_id UUID NOT NULL,
    category TEXT NOT NULL,
    transcript_excerpt TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sla_deadline TIMESTAMPTZ NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    reviewer_id TEXT,
    legal_hold BOOLEAN NOT NULL DEFAULT TRUE
);

ALTER TABLE consent_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE consent_records FORCE ROW LEVEL SECURITY;
ALTER TABLE safety_incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety_incidents FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS governance_consent_tenant_isolation ON consent_records;
CREATE POLICY governance_consent_tenant_isolation ON consent_records
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS governance_incident_tenant_isolation ON safety_incidents;
CREATE POLICY governance_incident_tenant_isolation ON safety_incidents
    USING (tenant_id::text = current_setting('app.current_tenant_id', true));
