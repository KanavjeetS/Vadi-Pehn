# Handoff Report — Deployment Story Canonicalization & Verification (Milestone 2)

**Agent**: `worker_m2_refine` (DevOps & Infra Worker)  
**Date**: 2026-07-24  
**Working Directory**: `d:\Vadi Bhen\.agents\worker_m2_refine\`  

---

## 1. Observation

Direct observations from codebase inspection, file modifications, and verification tool execution:

- **Desktop Dev Launcher (`start_desktop.py`)**:
  - Previously imported 8 microservices, omitting `memory_service` from `sub_apps` and `desktop_lifespan`.
  - Added line: `from memory_service.main import app as memory_app, lifespan as memory_lifespan`.
  - Added `memory_lifespan` to `desktop_lifespan` context manager stack.
  - Added `memory_app` to `sub_apps` list, mounting all 9 microservices (`api_gateway`, `dashboard_bff`, `orchestration`, `voice_gateway`, `governance`, `panel`, `safety_proxy`, `ingestion`, `memory_service`) on single-process FastAPI server.

- **Production Docker Compose Stack (`docker-compose.yml`)**:
  - Root `docker-compose.yml` previously lacked database services for pgvector memory DB and isolated governance DB.
  - Added service `postgres-memory` using image `pgvector/pgvector:pg16` on port `5432:5432`.
  - Added service `postgres-governance` using image `postgres:16-alpine` on port `5433:5432`.
  - Added `MEMORY_DB_HOST: "postgres-memory"` and `GOVERNANCE_DB_HOST: "postgres-governance"` to `x-internal-urls`.
  - Added healthcheck dependencies: `memory-service` depends on `postgres-memory`, `governance-service` depends on `postgres-governance`.
  - Root `docker-compose.yml` now defines all 9 microservices + Nginx webapp frontend + 2 physically isolated Postgres DB instances.
  - Verified syntax via `docker compose -f docker-compose.yml config --quiet` (Return Code: `0`).

- **Infrastructure Folder Cleanup (`infra/`)**:
  - Created `infra/README.md` defining canonical launchers (`start_desktop.py` for local dev; root `docker-compose.yml` for multi-container stack).
  - Prepend `DEPRECATED` notices to `infra/docker-compose.yml`, `infra/docker-compose.dev.yml`, and `infra/docker-compose.mvp.yml` directing developers to canonical root launchers.
  - Prepend `EXPERIMENTAL / REFERENCE ONLY` notices to `infra/k8s/deployment.yaml` and `infra/k8s/network-policy.yaml`.

- **PowerShell Task Runner (`vadi.ps1`)**:
  - Verified `dev` target maps to `py "$Root\start_desktop.py"`.
  - Verified `docker-up` target maps to `docker compose -f "$Root\docker-compose.yml" up -d`.
  - Added `"check"` target mapping to `py -m pytest "$Root\tests\test_deployment_canonicalization.py" -v`.
  - Updated help documentation text to highlight `dev` and `docker-up` as canonical launchers and document `check`.
  - Verified execution via `powershell -ExecutionPolicy Bypass -Command ".\vadi.ps1 help"`.

- **Pytest Deployment Test Suite (`tests/test_deployment_canonicalization.py`)**:
  - Created 5 automated tests:
    1. `test_docker_compose_canonical_services`: Asserts all 9 microservices, nginx, `postgres-memory`, and `postgres-governance` are present in `docker-compose.yml`.
    2. `test_docker_compose_config_syntax`: Runs `docker compose config --quiet` CLI syntax check.
    3. `test_start_desktop_imports_and_mounts`: Asserts `start_desktop.py` imports and mounts all 9 microservices and webapp static paths (`/child`, `/guardian`, `/admin`).
    4. `test_vadi_ps1_canonical_launchers`: Asserts `vadi.ps1` target definitions and help text accurately document canonical launchers.
    5. `test_infra_folder_canonicalization`: Asserts `infra/README.md` exists and legacy compose files carry `DEPRECATED` headers.
  - Executed deployment test suite via `powershell -ExecutionPolicy Bypass -Command ".\vadi.ps1 check"`. Result: **5 passed in 0.75s**.
  - Executed full test suite via `powershell -ExecutionPolicy Bypass -Command ".\vadi.ps1 test"`. Result: **218 passed in 77.06s** (0 regressions across entire codebase).

---

## 2. Logic Chain

1. **Local Development Canonicalization**:
   - Single-process development relies on `start_desktop.py` to route internal service calls locally without requiring Docker containers.
   - Including `memory_service` in `start_desktop.py`'s `sub_apps` and `desktop_lifespan` guarantees that all 9 microservices run in parity within single-process desktop mode.

2. **Production Container Stack Canonicalization**:
   - Production multi-container topology requires all microservices, frontend reverse proxy, and underlying persistent DBs to be defined in a single file (`docker-compose.yml`).
   - Per System Design §3 and Architecture Non-Negotiables, Memory DB (`postgres-memory` with pgvector) and Governance DB (`postgres-governance`) MUST be physically isolated instances.
   - Adding both DB containers and volume mounts to root `docker-compose.yml` ensures `docker compose up` (`.\vadi.ps1 docker-up`) provisions the complete runtime environment out of the box.

3. **Ambiguity Elimination in `infra/`**:
   - Having multiple compose files (`infra/docker-compose.dev.yml`, `infra/docker-compose.mvp.yml`, `infra/docker-compose.yml`) caused confusion over which file to run.
   - Writing `infra/README.md` and prepending explicit `DEPRECATED` headers directs developers directly to `start_desktop.py` or root `docker-compose.yml`.

4. **Task Runner & Verification Integrity**:
   - `vadi.ps1` serves as the primary developer CLI interface. Adding `.\vadi.ps1 check` provides an instant programmatic sanity check that can be executed prior to commits or deployments.
   - Programmatically testing file contents, YAML structure, and CLI invocation guarantees that canonicalization is enforced by CI/CD.

---

## 3. Caveats

- **Docker CLI in Headless CI**: `test_docker_compose_config_syntax` includes a fallback to PyYAML parsing if `docker` binary is unavailable in lightweight CI environments.
- **Port Binding Conflicts**: Running `start_desktop.py` (port 8080) and `docker compose up` (port 80 / 8000+) simultaneously can cause port conflicts if microservice host ports overlap. Each launcher is intended to run independently.

---

## 4. Conclusion

- Canonical deployment story is 100% established and programmatically verified.
- **Local Dev**: `start_desktop.py` / `.\vadi.ps1 dev` mounts all 9 microservices.
- **Production Stack**: Root `docker-compose.yml` / `.\vadi.ps1 docker-up` contains all 9 microservices + Nginx + 2 Postgres DBs.
- **Ambiguity Cleaned**: `infra/` directory documented with `README.md` and deprecation headers.
- **Validation**: `.\vadi.ps1 check` executes `tests/test_deployment_canonicalization.py` with 5/5 passing tests.
- **Full Test Suite**: `.\vadi.ps1 test` passes **218/218 tests** across all microservices and regression suites.

---

## 5. Verification Method

Independent verification steps:

1. **Run Deployment Validation Suite**:
   ```powershell
   powershell -ExecutionPolicy Bypass -Command ".\vadi.ps1 check"
   ```
   *Expected Output*: 5 passed tests in under 1 second.

2. **Verify Docker Compose Syntax**:
   ```powershell
   docker compose -f docker-compose.yml config --quiet
   ```
   *Expected Output*: Exit code 0 with zero syntax errors.

3. **Verify Launcher Help Text**:
   ```powershell
   powershell -ExecutionPolicy Bypass -Command ".\vadi.ps1 help"
   ```
   *Expected Output*: Displays `dev` and `docker-up` with canonical launcher notes and `check` validation target.
