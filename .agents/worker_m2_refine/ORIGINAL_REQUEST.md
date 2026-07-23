## 2026-07-23T19:35:54Z
You are the Backend & Infrastructure Engineer (@backend-engineer & @devops) for Milestone 2 of Vadi-Pehn Full MVP Refinement.
Working directory: d:\Vadi Bhen
Metadata directory: d:\Vadi Bhen\.agents\worker_m2_refine

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks for Milestone 2 (Divisions 2 & 7):
1. Division 2 (Backend Engineering):
   - Harden endpoints in `services/api-gateway/`, `services/governance-service/`, and `services/dashboard-bff/`.
   - Ensure `GET /api/v1/guardian/overview` queries real Supabase/Postgres tables for session counts, learner streaks, and safety incident counts (no stub zeros).
   - Ensure `GET /api/v1/admin/overview` and `/api/v1/admin/observability/metrics` query real DB metrics (no stub zeros).
   - Add `X-Request-ID` middleware/header to all API gateway and dashboard BFF responses for OpenTelemetry tracing.
   - Verify rate-limiting middleware (`check_rate_limit`).

2. Division 7 (Infrastructure & DevOps):
   - Create `docker-compose.yml` at repo root mapping all 9 microservices with proper ports, `depends_on`, healthchecks, and `.env` references.
   - Create `.env.example` at repo root matching `.env` structure with documented placeholders.
   - Create `Makefile` at repo root with targets: `make dev` (runs `py start_desktop.py`), `make docker-up`, `make docker-down`, `make test`, `make lint`.
   - Create `services/logging_config.py` with `configure_logging()` setting up Python structured JSON logging. Call `configure_logging()` in `start_desktop.py` and all service `main.py` entry points.

Run tests across services (e.g. `py -3 -m pytest services/dashboard-bff/ services/api-gateway/ services/governance-service/`).
Write a handoff report at `d:\Vadi Bhen\.agents\worker_m2_refine\handoff.md` detailing all changes and test results.
