# Skill: Bootstrap Workspace

## Objective
As the Lead Architect, ensure the repository matches the target layout in
`docs/system-design.md` §9 before any build segment starts, and confirm
which segments already exist vs. which are stubs.

## Rules of Engagement
- Never overwrite an existing implemented file — this skill only creates
  missing structure and reports status, it does not build features.
- Treat `sibling-voice-rag/` (the foundation segment: orchestration,
  memory, safety client, voice interfaces, API) as already built and
  tested. Do not re-scaffold it.

## Instructions
1. Compare the actual repo tree against System Design §9's target layout.
2. Report, per service (`api-gateway`, `orchestration`, `voice-gateway`,
   `safety-proxy`, `panel-service`, `memory-service`, `governance-service`,
   `ingestion-service`, `dashboard-bff`): **implemented** / **stub
   interface only** / **not started**.
3. Create any missing top-level directories (`services/`, `infra/`, `db/`,
   `eval/`, `docs/`, `research/findings/`) with a `.gitkeep` and a one-line
   `README.md` stating what belongs there and which System Design section
   governs it.
4. Confirm `docs/PRD-v2.md` and `docs/system-design.md` are present at the
   paths `AGENTS.md` references. If missing, halt and ask the human to add
   them — do not proceed to build from memory of their contents.
5. Output a short status table (service → status → next recommended
   skill/workflow to run) and stop. Do not start building anything in this
   skill.
