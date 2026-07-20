# Skill: Build Guardian & Admin Dashboard (BFF + Frontend)

## Objective
As the Backend/Frontend pairing, build the Dashboard Service (BFF) and a
minimal frontend implementing PRD §11's guardian/admin feature set,
sourcing read-aggregated data from Memory, Governance, and Ingestion
services — System Design §2.

## Rules of Engagement
- This service owns NO source-of-truth data (System Design §2's ownership
  table) — every field it shows is fetched from the service that owns it.
  Do not cache consent state or safety-incident status locally in a way
  that could go stale and mislead a guardian.
- Relationship-health view shows trend summaries (session frequency/
  duration), not raw transcripts, except where a safety incident has been
  raised (PRD §11) — enforce this distinction in the API response shape,
  not just the frontend rendering.
- The rapport score, if surfaced at all, is shown as a gate-status
  indicator ("career introductions: not yet unlocked / unlocked"), never
  as a raw engagement number a guardian could read as a target to push
  toward (ties to GUARDRAILS.md's engagement-metric rule).

## Instructions
1. Implement the six guardian-facing views from PRD §11: consent
   management, relationship health, safety incident notifications,
   academic sync status, data export/deletion request, plus the
   admin-only tenant-wide dashboard.
2. Build the BFF endpoints as thin aggregators calling the Consent
   (`GET /internal/v1/governance/consent/...`), Incident, and Memory-layer
   read APIs — no direct DB access from this service.
3. Implement the data export/deletion self-service trigger by calling the
   existing `PATCH /v1/consent/{learner_id}` and
   `delete_for_learner`-backed deletion path (System Design §5.5) — do not
   build a second deletion mechanism.
4. Build a minimal, accessible (WCAG 2.1 AA basics per PRD §6.5) frontend
   — plain, legible, no dark patterns around consent toggles.
5. Write tests asserting the BFF never returns raw conversational
   transcript content in the relationship-health endpoint unless the
   requesting guardian's learner has an active, acknowledged safety
   incident.
