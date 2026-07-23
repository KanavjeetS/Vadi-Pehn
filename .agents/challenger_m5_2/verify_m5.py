"""
Empirical verification script for Milestone 5 Remediation security controls.
"""
import sys
import os
from uuid import uuid4

# Set up import paths
sys.path.insert(0, os.path.abspath("services/dashboard-bff/src"))
sys.path.insert(0, os.path.abspath("services/api-gateway/src"))
sys.path.insert(0, os.path.abspath("."))

from fastapi.testclient import TestClient
from dashboard_bff.main import app
from api_gateway.auth import create_jwt_token

def main():
    print("=== Empirical Security Controls Verification ===")
    
    with TestClient(app) as client:
        # 1. Request with X-User-Role: admin header but no Bearer token returns HTTP 401
        res1 = client.get("/api/v1/admin/observability/metrics", headers={"X-User-Role": "admin"})
        print(f"[Check 1] X-User-Role header only: status = {res1.status_code} (expected 401)")
        assert res1.status_code == 401, f"Expected 401, got {res1.status_code}"

        res1_overview = client.get("/api/v1/admin/overview", headers={"X-User-Role": "admin"})
        print(f"[Check 1b] Admin overview header only: status = {res1_overview.status_code} (expected 401)")
        assert res1_overview.status_code == 401, f"Expected 401, got {res1_overview.status_code}"

        # 2. Request with invalid Bearer token returns HTTP 401
        res2 = client.get("/api/v1/admin/observability/metrics", headers={"Authorization": "Bearer invalid_token_xyz"})
        print(f"[Check 2] Invalid Bearer token: status = {res2.status_code} (expected 401)")
        assert res2.status_code == 401, f"Expected 401, got {res2.status_code}"

        res2_overview = client.get("/api/v1/admin/overview", headers={"Authorization": "Bearer invalid_token_xyz"})
        print(f"[Check 2b] Invalid Bearer token on overview: status = {res2_overview.status_code} (expected 401)")
        assert res2_overview.status_code == 401, f"Expected 401, got {res2_overview.status_code}"

        # 3. Request with learner or guardian role Bearer token returns HTTP 403
        t_learner = create_jwt_token(user_id=str(uuid4()), tenant_id=str(uuid4()), role="learner")
        res3_learner = client.get("/api/v1/admin/observability/metrics", headers={"Authorization": f"Bearer {t_learner}"})
        print(f"[Check 3a] Learner Bearer token on admin metrics: status = {res3_learner.status_code} (expected 403)")
        assert res3_learner.status_code == 403, f"Expected 403, got {res3_learner.status_code}"

        t_guardian = create_jwt_token(user_id=str(uuid4()), tenant_id=str(uuid4()), role="guardian")
        res3_guardian = client.get("/api/v1/admin/observability/metrics", headers={"Authorization": f"Bearer {t_guardian}"})
        print(f"[Check 3b] Guardian Bearer token on admin metrics: status = {res3_guardian.status_code} (expected 403)")
        assert res3_guardian.status_code == 403, f"Expected 403, got {res3_guardian.status_code}"

        res3_guardian_overview = client.get("/api/v1/admin/overview", headers={"Authorization": f"Bearer {t_guardian}"})
        print(f"[Check 3c] Guardian Bearer token on admin overview: status = {res3_guardian_overview.status_code} (expected 403)")
        assert res3_guardian_overview.status_code == 403, f"Expected 403, got {res3_guardian_overview.status_code}"

        # 4. Request with valid admin Bearer token returns HTTP 200
        t_admin = create_jwt_token(user_id=str(uuid4()), tenant_id=str(uuid4()), role="admin")
        res4_metrics = client.get("/api/v1/admin/observability/metrics", headers={"Authorization": f"Bearer {t_admin}"})
        print(f"[Check 4a] Valid admin Bearer token on metrics: status = {res4_metrics.status_code} (expected 200)")
        assert res4_metrics.status_code == 200, f"Expected 200, got {res4_metrics.status_code}"

        res4_overview = client.get("/api/v1/admin/overview", headers={"Authorization": f"Bearer {t_admin}"})
        print(f"[Check 4b] Valid admin Bearer token on overview: status = {res4_overview.status_code} (expected 200)")
        assert res4_overview.status_code == 200, f"Expected 200, got {res4_overview.status_code}"

    print("\nALL EMPIRICAL SECURITY CONTROL CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
