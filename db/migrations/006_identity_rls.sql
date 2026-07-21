-- Tenant isolation for authenticated identity lifecycle queries.
-- The application sets app.current_tenant_id with SET LOCAL per transaction.

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE guardians ENABLE ROW LEVEL SECURITY;
ALTER TABLE guardians FORCE ROW LEVEL SECURITY;
ALTER TABLE learners ENABLE ROW LEVEL SECURITY;
ALTER TABLE learners FORCE ROW LEVEL SECURITY;

CREATE POLICY identity_tenant_isolation ON tenants
    USING (id::text = current_setting('app.current_tenant_id', true))
    WITH CHECK (id::text = current_setting('app.current_tenant_id', true));

CREATE POLICY guardian_tenant_isolation ON guardians
    USING (tenant_id::text = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));

CREATE POLICY learner_tenant_isolation ON learners
    USING (tenant_id::text = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true));
