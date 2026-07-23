# BRIEFING — 2026-07-22T10:37:30Z

## Mission
Investigate `start_desktop.py` and service routing across 9 microservices to diagnose 404/503 errors in single-process desktop development mode and formulate a fix strategy for Requirement R1.

## 🔒 My Identity
- Archetype: Codebase Researcher (Backend & Routing)
- Roles: Read-only investigator for start_desktop.py & microservice routing
- Working directory: d:\Vadi Bhen\.agents\teamwork_preview_explorer_m1_1
- Original parent: 58da31d6-c265-49c8-836a-51d2b1c2326c
- Milestone: m1_1

## 🔒 Key Constraints
- Read-only investigation — do NOT implement or modify project source files directly.
- Document exact file paths, line numbers, mounting prefixes, and root cause analysis.
- Follow 5-component handoff report (Observation, Logic Chain, Caveats, Conclusion, Verification Method).

## Current Parent
- Conversation ID: 58da31d6-c265-49c8-836a-51d2b1c2326c
- Updated: 2026-07-22T10:37:30Z

## Investigation State
- **Explored paths**:
  - `start_desktop.py`
  - `services/config.py`
  - `services/api-gateway/src/api_gateway/main.py`
  - `services/orchestration/src/orchestration/main.py`
  - `services/voice-gateway/src/voice_gateway/main.py`
  - `services/governance-service/src/governance_service/main.py`
  - `services/safety-proxy/src/safety_proxy/main.py` & `client.py`
  - `services/ingestion-service/src/ingestion_service/main.py`
  - `services/panel-service/src/panel_service/main.py`
  - `services/dashboard-bff/src/dashboard_bff/main.py`
- **Key findings**:
  - Double-prefix route mounting bug (mounting sub-apps at `/internal/v1/...` when routes inside sub-apps also include `/internal/v1/...`) causes 404 Not Found.
  - 404 errors during internal HTTP client calls are caught and raised as 503 Service Unavailable.
  - Sub-application `@asynccontextmanager lifespan` handlers are not executed when mounted via `desktop_app.mount(...)`, leaving `graph`, `governance_pool`, and `dashboard_repo` uninitialized (`None`).
  - `is_dev` check in `api_gateway` and `dashboard_bff` lifespans skips initializing `identity_store` and `dashboard_repo`, triggering 503 errors.
  - `DASHBOARD_BFF_URL` missing from `start_desktop.py`, causing DNS failure and 503 when calling dashboard overview proxies.
  - `SafetyProxyLLMClient` calls `/internal/v1/llm/chat/completions` which has no mount on `desktop_app`.
- **Unexplored areas**: None. Full investigation completed.

## Key Decisions Made
- Completed read-only investigation and synthesized fix strategy for Requirement R1.
- Written 5-component handoff report to `d:\Vadi Bhen\.agents\teamwork_preview_explorer_m1_1\handoff.md`.

## Artifact Index
- `d:\Vadi Bhen\.agents\teamwork_preview_explorer_m1_1\ORIGINAL_REQUEST.md` — Original request log
- `d:\Vadi Bhen\.agents\teamwork_preview_explorer_m1_1\BRIEFING.md` — Working memory index
- `d:\Vadi Bhen\.agents\teamwork_preview_explorer_m1_1\progress.md` — Heartbeat progress log
- `d:\Vadi Bhen\.agents\teamwork_preview_explorer_m1_1\handoff.md` — Comprehensive handoff report with observations, logic chain, caveats, conclusion, and R1 fix strategy
