# Build Segment Reference Guide

Full reference for all 14 build skills and their usage.
This file is for the agent — the source skills are in
`d:\Vadi Bhen\vadi-pehn-antigravity\.agents\skills\`.

## Skill → Segment → Persona Quick Reference

| Skill File | Segment | Persona | PRD/SD Section |
|---|---|---|---|
| `bootstrap-workspace.md` | (pre-build) | `@architect` | SD §9 |
| `build-orchestration-graph.md` | orchestration | `@backend-engineer` | SD §2, §5.1 |
| `build-memory-service.md` | memory-service | `@data-engineer` | SD §3.2, §7.1 |
| `build-safety-proxy.md` | safety-proxy | `@safety-engineer` | SD §2, §4.3, PRD §8 |
| `build-voice-gateway.md` | voice-gateway | `@voice-engineer` | SD §2, §5.2, PRD §6 |
| `build-panel-service.md` | panel-service | `@backend-engineer` | SD §2, §4.4, §5.4 |
| `build-governance-service.md` | governance-service | `@safety-engineer + @data-engineer` | SD §3.4, §5.3 |
| `build-ingestion-service.md` | ingestion-service | `@data-engineer` | SD §2, §3.5 |
| `build-guardian-dashboard.md` | guardian-dashboard | `@backend-engineer` | SD §2 |
| `audit-safety-failclosed.md` | (QA) | `@qa-auditor` | PRD §8.1 |
| `audit-tenant-isolation.md` | (QA) | `@qa-auditor` | SD §7.2, PRD §7 |
| `write-tests.md` | (QA) | `@backend-engineer` | PRD §14 |
| `research-and-propose.md` | (Research) | `@researcher` | SD §10 |
| `sync-docs-with-code.md` | (Docs) | `@doc-keeper` | — |

## Segment Dependency Order (from `/full-cycle` workflow)

Build in this order. Each service depends on all services above it:

1. **memory-service** → real Postgres/RLS (everything else depends on real persistence)
2. **safety-proxy** → real NeMo Guardrails (all conversation paths depend on this)
3. **voice-gateway**
4. **governance-service**
5. **panel-service**
6. **ingestion-service**
7. **guardian-dashboard**

`orchestration` graph extensions build incrementally on top of the foundation,
not as a separate segment in the dependency chain.

## Human Approval Gates

Stop and wait for explicit approval before the next segment when completing:
- `memory-service` (schema/RLS)
- `safety-proxy` (safety-critical path)
- `governance-service` (consent + incident schema)

## Key Invariants to Check in Every Segment

**For any segment touching per-learner data:**
→ Run `audit-tenant-isolation.md`
→ Confirm `SET LOCAL app.current_tenant_id` in every DB transaction

**For any segment touching LLM generation:**
→ Run `audit-safety-failclosed.md`
→ Confirm safety proxy is called before AND after LLM call
→ Confirm classifier timeout → `classifier_unavailable` → fail closed

**For voice path specifically:**
→ Confirm per-chunk output safety check (GUARDRAILS G-004)
→ Measure and assert p95 latency budget (SD §5.2, PRD §6.2)
