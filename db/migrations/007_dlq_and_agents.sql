-- Migration 007: Memory Write DLQ, Professional Agent & Curator Tables
-- Implements: Resilient Memory Ingestion (DLQ Retries) & Dual Agent Persona Extensions

-- 1. Memory Write Dead-Letter Queue (DLQ) Table
CREATE TABLE IF NOT EXISTS memory_write_dlq (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    learner_id UUID NOT NULL,
    session_id UUID,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_retry_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'pending' -- 'pending', 'processing', 'failed', 'resolved'
);

CREATE INDEX IF NOT EXISTS idx_memory_write_dlq_tenant_learner ON memory_write_dlq(tenant_id, learner_id);
CREATE INDEX IF NOT EXISTS idx_memory_write_dlq_status ON memory_write_dlq(status);

-- RLS for memory_write_dlq
ALTER TABLE memory_write_dlq ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_write_dlq FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS memory_write_dlq_tenant_policy ON memory_write_dlq;
CREATE POLICY memory_write_dlq_tenant_policy ON memory_write_dlq
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);


-- 2. Professional Agent Pathways & Skill Roadmaps
CREATE TABLE IF NOT EXISTS professional_career_pathways (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    learner_id UUID NOT NULL,
    career_title VARCHAR(255) NOT NULL,
    required_skills JSONB DEFAULT '[]'::jsonb,
    milestones JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE professional_career_pathways ENABLE ROW LEVEL SECURITY;
ALTER TABLE professional_career_pathways FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS professional_career_tenant_policy ON professional_career_pathways;
CREATE POLICY professional_career_tenant_policy ON professional_career_pathways
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);


-- 3. Curator Agent Verified Learning Resources
CREATE TABLE IF NOT EXISTS curated_learning_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    topic VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    source_url TEXT,
    summary TEXT NOT NULL,
    age_suitability_min INT DEFAULT 8,
    age_suitability_max INT DEFAULT 17,
    verified_safe BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE curated_learning_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE curated_learning_resources FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS curated_learning_tenant_policy ON curated_learning_resources;
CREATE POLICY curated_learning_tenant_policy ON curated_learning_resources
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
