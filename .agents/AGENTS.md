# Vadi-Pehn: Workspace Agent Rules & Development Constitution

This file governs every code generation, modification, and review action in this
workspace. It is inherited from `vadi-pehn-antigravity/.agents/` and extends it
with external repo learnings. All rules below are non-negotiable and override any
workflow, skill, or user request that conflicts with them.

---

## Part 1: Child Safety Non-Negotiables
*(Source: `vadi-pehn-antigravity/.agents/rules/child-safety-non-negotiables.md`)*

These apply regardless of which persona, skill, or slash command is active.

1. **No safety proxy bypass.** No agent may weaken, bypass, or feature-flag-disable
   the Safety Proxy call on either the input or output path of a conversation turn.
2. **Fail-closed always.** No agent may change `SafetyVerdict.blocks_generation` logic
   such that any verdict other than `SAFE` allows generation to proceed.
3. **No voice audio retention.** No agent may write code that stores raw voice audio
   beyond the transcription step (PRD §3.4).
4. **Synthetic fixtures only.** No agent may generate, in code, tests, fixtures, or
   docs, content that reads as a real child's personal disclosure, real report card data,
   or realistic self-harm/abuse transcript. Use clearly-labeled synthetic placeholders only.
5. **No training on live learner data.** No agent may introduce a data flow where the
   sibling persona's output is used to fine-tune anything on real learner conversation data
   without an explicit, human-approved, PRD-amending decision.
6. **Mandatory dual review on safety-critical files.** Any change touching `safety.py`,
   orchestration safety nodes, RLS policies, or the Consent Ledger schema requires
   `@safety-engineer` AND `@data-engineer` review before being considered done.

---

## Part 2: Architecture Non-Negotiables
*(Source: SystemDesign.md + AGENTS.md)*

- **RLS always.** Every database query against `learner_memories` or
  `learner_interest_profile` MUST issue `SET LOCAL app.current_tenant_id = $1`
  inside the transaction. Never trust application-level filtering alone.
- **Governance DB is physically separate.** The Governance Service (consent,
  incidents, logs) MUST use a different Postgres instance than the Memory Service.
  Never propose merging them.
- **Prompt files, not strings.** System prompts and persona templates live in
  versioned files under `services/orchestration/personas/`. Never hardcode them
  as Python strings.
- **Safety Proxy is a network-level reverse proxy.** Not a library. Not a sidecar.
  The network path to LLM generation does not exist without going through it.
- **3-second safety timeout = fail-closed.** A classifier timeout MUST produce a
  `classifier_unavailable` verdict and route to the manual review queue.
  It MUST NOT allow generation to proceed.

---

## Part 3: Coding Standards
*(Source: `vadi-pehn-antigravity/.agents/rules/coding-standards.md` + karpathy-skills)*

- **Python 3.10+**, full type hints on all public functions and dataclass fields.
- **Format with `black`, lint with `ruff`** before any change is considered complete.
- **Abstract-first.** Every module talking to an external system (LLM, DB, HTTP) must
  expose an abstract base class plus at least one mock implementation. Follow the pattern
  in `src/sibling/llm_client.py` and `src/sibling/safety.py`.
- **No bare `except:`.** Catch specific exceptions. On safety or memory-isolation paths,
  an unhandled exception must fail closed, never propagate as a swallowed 500.
- **`async def` on the request path.** Matches the existing FastAPI + LangGraph style.
- **Config centralized.** New env vars go in `config.py`'s `Settings` dataclass.
  Never read `os.environ` directly elsewhere.
- **Docstrings on every module** explaining: what it's a stand-in for (if a mock),
  which PRD/System Design section it implements, what it deliberately does NOT do.
- **THINK BEFORE CODING** (Karpathy principle 1): State assumptions explicitly.
  Present multiple interpretations. Stop when confused. Never silently assume.
- **SIMPLICITY FIRST** (Karpathy principle 2): Minimum code that solves the problem.
  No speculative abstractions. No flexibility that wasn't asked for.
- **SURGICAL CHANGES** (Karpathy principle 3): Touch only what the task requires.
  Do not "improve" adjacent code unless explicitly asked.
- **GOAL-DRIVEN** (Karpathy principle 4): Write or verify the test that proves the
  goal is achieved, not just that the code ran.
- **CONCISE COMMUNICATION** (caveman principle): In code comments, explanations, and
  tool output — maximum information density, zero filler. Code/commands/errors exact.

---

## Part 4: The 9 Agent Personas
*(Source: `vadi-pehn-antigravity/.agents/agents.md`)*

Use these persona designations in task decomposition and review routing:

| Persona | Owns | Does Not Do |
|---|---|---|
| `@architect` | PRD/SD compliance, task decomposition, open design decisions | Write application code |
| `@backend-engineer` | Orchestration Service (LangGraph), Memory Service, Panel Service | Skip interface-first pattern |
| `@voice-engineer` | Voice Gateway, LiveKit, VAD/STT/TTS, latency budget | Skip per-chunk output safety |
| `@safety-engineer` | Safety Proxy, Governance Service, NeMo/Aegis wiring, Consent Ledger | Weaken fail-closed behavior |
| `@data-engineer` | DB schema, RLS policies, pgvector, migrations, pgTAP tests | Merge governance and memory DBs |
| `@qa-auditor` | Test execution, safety audit, tenant isolation audit, GUARDRAILS.md | Fix judgment-call issues unilaterally |
| `@devops` | Docker Compose, K8s manifests, vLLM/GPU config, Langfuse/OTEL wiring | Commit credentials or .env files |
| `@researcher` | Stack improvement proposals, CVE scanning, dated sourced findings | Auto-apply safety-critical changes |
| `@doc-keeper` | PRD/SD/README drift correction after build segments | Change safety requirement meaning |

---

## Part 5: Slash Command Routing
*(Source: `vadi-pehn-antigravity/.agents/workflows/`)*

| Command | Workflow | What it does |
|---|---|---|
| `/build-segment <name>` | `build-segment.md` | Build one service end-to-end: spec-check → build → tests → QA audit → docs sync |
| `/qa-loop <target>` | `qa-loop.md` | Iterative find-and-fix loop (max 5 iterations, stops on clean) |
| `/full-cycle` | `full-cycle.md` | All remaining segments in dependency order with human approval gates on schema/safety segments |
| `/safety-audit` | `safety-audit.md` | `@qa-auditor` runs fail-closed and tenant isolation audits |
| `/research-loop` | `research-loop.md` | `@researcher` scans for stack updates, writes to `research/findings/` |

**Valid segment names for `/build-segment`:**
`orchestration` | `memory-service` | `safety-proxy` | `voice-gateway` |
`panel-service` | `governance-service` | `ingestion-service` | `guardian-dashboard`

---

## Part 6: External Repo Learnings
*(Consolidated from all referenced repositories)*

### CodeGraph (colbymchenry/codegraph)
Before touching any shared abstraction (a base class, a DB client, a message schema):
1. Trace all callers and dependents — understand the full call graph impact.
2. A "simple" rename or signature change in a shared module can break 8 downstream services.
3. Never refactor shared interfaces without checking every consumer.

### OpenHands
Tasks should be designed as discrete, sandboxable units of work with:
- Clear input contracts
- Verifiable success criteria (a test, a health check, a schema assertion)
- Explicit failure modes documented before starting

### Langfuse Integration Pattern (applies to all services)
Every LLM call must emit an OpenTelemetry trace with:
- `tenant_id` (hashed for non-incident telemetry)
- `learner_id` (hashed)
- `session_id`
- `safety_verdict` (input + output)
- `persona_name`
Use the `@observe` decorator or Langfuse callback handler — never manual span creation.

---

## Part 7: Model Training Plan
*(Applies to the 3-agent architecture: Sibling + Career Panel + Ingestion)*

| Agent | Model Type | Training Strategy |
|---|---|---|
| Sibling Mentor | Llama-3.3-70B fine-tuned | RLHF on child-safe conversation corpus, Aegis 2.0 safety alignment |
| Career Panel Personas | MoE (Mixture of Experts) | Domain-specific expert routing (career, geography, skill pathways) |
| Ingestion / OCR Classifier | SLM (Small Language Model, e.g. Qwen2-VL-7B) | olmOCR fine-tune on academic document layouts for the target region |

**Training rule:** No real learner data may be used for training without explicit
human approval documented as a PRD amendment (Child Safety Non-Negotiable #5).
