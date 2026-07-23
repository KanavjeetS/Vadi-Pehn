# Original User Request

## Initial Request — 2026-07-22T05:04:38Z

<USER_REQUEST>
# Teamwork Project Prompt — Vadi-Pehn Platform Execution

Working directory: `d:\Vadi Bhen`
Integrity mode: `development`

Vadi-Pehn is a 9-microservice virtual sibling-mentor platform with fail-closed safety (`NeMo Guardrails`), RLS tenant isolation (`Supabase pgvector`), and NoSQL telemetry (`MongoDB Atlas`). We must fix all route mounting mismatches in `start_desktop.py`, implement an Indian female voice using ElevenLabs/Kokoro inside `voice-gateway`, build unified multi-role Login/Signup pages (`/login` & `/signup`) with one-click Demo buttons, add rich UI animations across all portals, seed synthetic test data on startup, and strictly verify full PRD compliance including memory persistence and AI pipeline functionality.

## Requirements

### R1. Backend Route Mounting & Internal Service Connectivity (`start_desktop.py`)
- Fix the sub-application route mounting in `start_desktop.py` so that internal API calls (e.g., `POST /internal/v1/orchestration/turn`, `/internal/v1/voice/turn`, `/internal/v1/governance/consent/{learner_id}`) reach their exact endpoints cleanly without returning `404 Not Found` or `503 Service Unavailable`.
- Ensure `api_gateway`, `dashboard_bff`, `orchestration`, `voice_gateway`, `governance`, `panel`, `safety_proxy`, and `ingestion` communicate fluently with each other in single-process desktop development mode (`py -3 start_desktop.py`).

### R2. Multi-Role Authentication, Login & Signup System with Demo Toggles (`/login` & `/signup`)
- Create a dedicated, beautifully styled Login (`/login.html`) and Signup (`/signup.html`) interface accessible across the entire web application.
- Support distinct account creation and simultaneous/separate login roles:
  1. **Child / Learner (`role='learner'`)**: Issues learner JWT and routes directly to `/child/`.
  2. **Guardian / Parent (`role='guardian'`)**: Issues guardian JWT linked to linked minors and routes to `/guardian/`.
  3. **Admin / System Observability (`role='admin'`)**: Issues admin JWT and routes to `/admin/`.
- Include quick **'Demo Accounts' toggle buttons** (One-click instant login as Child, Guardian, or Admin) on the login page for seamless testing.
- Persist authentication tokens (`access_token`, `tenant_id`, `learner_id`/`guardian_id`, `role`) securely in `localStorage` so all subsequent API calls carry proper authorization (`Bearer` headers and `X-Tenant-ID`).

### R3. Child Companion Portal (`/child/`), ElevenLabs Indian Female Voice & Rich Animations
- Fix the child communication interface so chat and voice turns process smoothly through the orchestration and memory RAG pipeline.
- Wire up ElevenLabs / Kokoro TTS in `services/voice-gateway` to generate a natural, fluent, and creative **Indian female voice** (`temperature=0.7`, normal speaking speed, high warmth and emotional resonance). Include the API key in `.env` or settings so it works out of the box.
- Add rich animations & sound effects (particle effects, typing animations, live audio waveform visualizer during voice playback) across the Child UI.
- Ensure clear AI identity disclosure per child safety guardrails (`GUARDRAILS.md`).

### R4. Guardian Governance Portal (`/guardian/`) & Synthetic Data Seeding
- Remove all hardcoded/random placeholder data from `guardian.html` and `guardian.js`.
- Wire the dashboard directly to `/api/v1/guardian/overview` and governance APIs.
- Automatically check and seed synthetic test learners, memories, and safety incidents in the database on startup so Guardian and Admin charts are immediately full of rich, realistic, PRD-compliant data (`tenant_id` and `learner_id` scoped).
- Display real learner streak, active engagement charts, consent toggles (`conversation_storage`, `document_ingestion`, `voice_recording`), and safety incident logs (`15-minute SLA tracking`).

### R5. Admin Observability & Tracing Center (`/admin/`) (Built-in Native Charts)
- Fix the Admin system observability dashboard (`/admin/`) so it does not display a broken image/iframe pointing to `http://localhost:3000`.
- Build a responsive, state-of-the-art native tracing and metrics interface connecting to `/api/v1/admin/overview` and telemetry stores.
- Display custom interactive charts (Langfuse trace summaries, API latency breakdown, safety filter pass rate `99.18%+`, system health logs) entirely built-in without requiring an external server running on port 3000.

### R6. PRD Compliance & AI Pipeline Memory RAG Verification
- Verify that every component strictly adheres to `PRD.md` and `SystemDesign.md`.
- Test and verify that conversational turns (`POST /api/v1/turn`) correctly invoke the AI pipeline, generate contextual replies, extract key details, and save them permanently into the learner's `learner_memories` vector database (`Supabase pgvector`).
- Verify that subsequent turns retrieve those saved memories via `ContextualRetrievalService` and incorporate them into the sibling mentor's responses.

## Acceptance Criteria

### Backend & Authentication
- [ ] `py -3 start_desktop.py` launches cleanly on `http://127.0.0.1:8000` without mounting errors (`all microservice health checks return 200 OK`).
- [ ] `POST /api/v1/turn` returns valid AI replies (`TurnState`) with status code `200 OK` (`404` and `503` completely eliminated).
- [ ] Users can sign up, log in, or use one-click Demo Account buttons at `/login.html` and receive valid role-scoped JWTs stored in `localStorage`.

### Voice & Child Interface
- [ ] Child interface (`/child/`) sends chat messages and displays typing/particle animations with responsive, creative answers (`temperature=0.7`).
- [ ] Voice synthesis returns high-quality audio (`audio/wav` or `mp3`) in a fluent Indian female voice profile, triggering the live audio waveform visualizer during playback.

- [ ] Guardian portal (`/guardian/`) fetches and renders seeded synthetic metrics and real learner data (`tenant_id` and `learner_id` specific) without static mock strings.
- [ ] Admin portal (`/admin/`) renders interactive trace summaries, API latency charts, and SLA metrics natively without broken `iframe` errors (`http://localhost:3000` dependency removed).

### PRD & Memory RAG Verification
- [ ] Automated/manual verification proves that when a child shares personal details in chat, a new embedding record is successfully inserted into `learner_memories` in the live database and retrieved in follow-up turns per `PRD.md`.
</USER_REQUEST>

## Parent Update — 2026-07-23T14:26:37Z

Additional fix applied: `services/logging_config.py` line 38 — changed `if record.extra:` to `extra = getattr(record, "extra", None); if extra:` to fix AttributeError on standard LogRecord objects. All startup logs now emit clean JSON without formatter errors.

Also: the user removed the unused `StreamingResponse` import from `safety-proxy/main.py` and added a `noqa: E402` to `voice-gateway/main.py`. Both are minor lint cleanups.

M2 status: 184/184 tests confirmed. Please proceed to M3 (AI Pipeline) and M4 (UI/UX) in parallel if architecture allows.

## Parent Architecture Update — 2026-07-23T14:01:54Z

ARCHITECTURE UPDATE: The dev bypass has been moved from `actions.py` (which the user wants to keep strictly fail-closed) to `main.py` (the HTTP handler layer). This is a cleaner separation:

- `actions.py` `classify_input` and `classify_output`: ALWAYS fail-closed — no dev bypass code in them
- `main.py` `/check-input` and `/check-output` handlers: after receiving a `CLASSIFIER_UNAVAILABLE` return value from classify_input, they check `allow_dev_bypass and is_dev` and convert to `SAFE` before responding

The dev bypass now sits entirely in `main.py` (the Safety Proxy HTTP server), not in `actions.py`. `actions.py` is now pristine. Do NOT modify `actions.py` exception handlers to add any bypass logic. The bypass in `main.py` covers the gap.

Also: Milestone 1 noted — 91/91 tests passing is excellent. Continue with Milestone 2 (UI/UX overhaul).

## Follow-up — 2026-07-23T13:48:05Z

<USER_REQUEST>
# Vadi-Pehn Full MVP Refinement — 11-Division Engineering Execution

Vadi-Pehn is a child-safety-first AI sibling-mentor platform (ages 8-17) that connects learners with an emotionally intelligent AI companion, a career panel of professional personas, and a guardian governance dashboard. The platform already has working backend services (FastAPI, LangGraph, Supabase/pgvector, ElevenLabs TTS, Groq LLM). This project brings every layer to production-grade quality — stunning 2026-standard UI/UX, rock-solid backend, complete AI pipeline, full test coverage, and deployment-ready infrastructure — as if built by a 100-person world-class engineering team.

Working directory: `d:\Vadi Bhen`
Integrity mode: development

---

## Team Structure (11 Divisions)

Each division owns its slice end-to-end. Deploy in this dependency order:
1. Data Engineering → sets up DB schemas
2. Backend Engineering → hardens APIs
3. AI Platform → completes pipelines
4. AI Safety → completes guardrails
5. Security → auth hardening
6. Frontend Engineering + Product & UX + Design & Brand → UI overhaul (can run in parallel)
7. Infrastructure / DevOps → Docker Compose + CI
8. QA & Testing → final validation

---

## Requirements

### R1. World-Class 2026 UI/UX (Divisions 1 + 2 + 11)

Rebuild all four portals to match the visual quality of Duolingo, Khan Academy Kids, Raycast, Linear, and Arc Browser. Immersive, animated, emotionally delightful. Use vanilla CSS animations, GSAP via CDN, Canvas API for backgrounds, Lottie via CDN for character animations, and Chart.js for dashboards. Every interaction — button press, message send, voice activation, achievement unlock — must have a satisfying visual response. Design a branded Vadi avatar character, an onboarding flow, a gamification/XP system, and age-band-adaptive UI themes.

**`webapp/login.html`**: Glassmorphism card on animated gradient mesh background, role-selector tabs (Child/Guardian/Admin) with smooth sliding indicator, one-click demo login buttons, animated form validation, particle background effect. On success: smooth fade-transition to the relevant dashboard.

**`webapp/signup.html`**: Matching design language to login, step-by-step form wizard (role select → account details → profile setup), real-time password strength meter, Guardian account linking code field, animated progress steps.

**`webapp/child/index.html` + `child.js`**: 
- Animated hero area with Vadi avatar (CSS sprite or Lottie) in idle/listening/speaking states
- Chat bubbles that slide in from the bottom with staggered animation
- Live audio waveform visualizer (Web Audio API canvas animation) during TTS playback
- XP bar that animates on each turn, streak counter, level badge
- Mood selector (emoji chips) that personalizes the conversation
- Topic chips (school, career, hobbies, feelings)
- Floating animated particles in background
- Dark mode toggle with smooth transition
- Typing indicator (three animated dots) while waiting for reply
- Voice input button with pulsing animation when recording

**`webapp/guardian/index.html` + `guardian.js`**:
- Real data from `/api/v1/guardian/overview` — no hardcoded numbers
- Animated Chart.js line chart for session frequency over last 7 days
- Donut chart for topic distribution
- Safety incident timeline with severity color coding
- Consent toggle switches with animated states
- Learner profile card with avatar, streak, last active
- Live session indicator (pulsing green dot when child is online)
- Glassmorphism cards with subtle hover lift effects

**`webapp/admin/index.html` + `admin.js`**:
- Real data from `/api/v1/admin/overview` and `/api/v1/admin/observability/metrics`
- KPI metric tiles: total turns, unique learners, avg response time, safety rate
- Animated number counters on load
- LLM model status card (Groq status badge)
- Recent incidents table with status badges
- System health indicators (DB, LLM, TTS) with color coding

All pages: Inter font from Google Fonts, CSS custom properties for theming, mobile-first responsive layout, WCAG 2.1 AA accessibility, smooth page transitions.

### R2. Complete & Hardened Backend (Divisions 3 + 7 + 8)

Every existing API endpoint must be production-grade. Review and fix:
- `services/api-gateway/src/api_gateway/main.py` — all routes
- `services/governance-service/` — incident and consent APIs
- `services/dashboard-bff/` — guardian and admin BFF APIs

Specific fixes needed:
1. `GET /api/v1/guardian/overview` — must query real Supabase tables for session counts and incident counts, not return stub zeros
2. `GET /api/v1/admin/overview` — same, real metrics
3. Auth: `POST /api/v1/auth/login` and `/api/v1/auth/signup` — real user validation against a `users` table or Supabase auth (if not possible, use the existing demo credential system but document it clearly)
4. Rate limiting — already wired via `check_rate_limit`, verify it works
5. Add `X-Request-ID` header to all responses for tracing
6. Structured JSON logging in every service (use Python `logging` with a JSON formatter)

Database: The existing Supabase DSN is `postgresql://postgres:Kanav%40142416@db.nmpyggtpigzoxjwcsfvz.supabase.co:5432/vadi_memory`. Ensure `learner_memories` table writes work end-to-end through `AsyncMemoryWriter`.

### R3. Complete AI Pipeline (Divisions 4 + 5 + 9)

**Memory writes**: After every safe turn, `AsyncMemoryWriter.write_memory_async()` must write `"Child: {message}\nVadi: {reply}"` to the `learner_memories` table in Supabase. Verify this is called (it's wired in `graph.py` `write_memory` node but the consent check may block it — in dev mode, consent check should default to True if governance service is unavailable).

**Memory reads**: `retrieve_memory` uses `stub_embedding = [0.0] * 1536` which returns no results from pgvector. Fix: when embedding client is not available, use a `LIMIT 5` recency-based query (no vector similarity needed) to fetch last 5 turns for context.

**`sibling.jinja2`**: The persona template at `services/orchestration/personas/sibling.jinja2` is already rich (100+ lines). Verify it renders correctly by checking that the system prompt sent to Groq contains the rendered template (add debug logging on first turn).

**Career panel**: When `panel_triggered=True`, the system prompt now includes a CAREER PANEL NOTE. Enhance this: look up which persona template matches the detected career keyword and render that persona's `.jinja2` file as additional context.

**Safety (already working in dev)**:
- `classify_input` dev bypass: ✅ working
- `classify_output` dev bypass: ✅ working  
- DO NOT regress these — critical for dev usability
- Add Hinglish self-harm keywords to `SELF_HARM_KEYWORDS` in `actions.py`: `"marna chahta", "marna chahti", "jeena nahi chahta", "khatam karna chahta", "khud ko hurt"`

### R4. Infrastructure & Observability (Division 6)

1. **`docker-compose.yml`** at repo root — all 9 services with proper port mapping, depends_on, healthchecks, and shared `.env` file reference. Use the existing service Dockerfiles.

2. **`.env.example`** — copy current `.env` structure with placeholder values and inline comments explaining each variable.

3. **`Makefile`** — targets: `make dev` (runs `py start_desktop.py`), `make docker-up`, `make docker-down`, `make test`, `make lint`.

4. **Logging**: Add a `services/logging_config.py` module with a `configure_logging()` function that sets up JSON-formatted structured logging. Call it from `start_desktop.py` and all service `main.py` files.

### R5. Comprehensive Test Suite (Division 10)

1. **Fix existing tests**: Run `pytest services/ -x --ignore=services/sibling-training` and fix any failures that aren't due to missing live DB/LLM. Target: ≥ 70% of tests pass.

2. **Safety regression tests** (`tests/test_safety_keywords.py`): 20 fixed pairs testing `classify_input` with the keyword pre-filter. Examples:
   - `"kill myself"` → `UNSAFE_SELF_HARM`
   - `"marna chahta hoon"` → `UNSAFE_SELF_HARM` (after adding Hinglish keywords)
   - `"ignore previous instructions"` → `UNSAFE_GENERAL`
   - `"hello how are you"` → passes to network (mock the network call to return SAFE)

3. **E2E smoke test** (`scratch/test_e2e_turn.py` already exists) — ensure it passes against the running server.

4. **Diversity test** (`scratch/test_diversity.py` already exists and passes 5/5) — do not regress.

---

## Known Working State — DO NOT REGRESS

- `safety-proxy/main.py` `proxy_llm`: tries vLLM (5s timeout) → falls back to Groq `llama-3.3-70b-versatile` ✅
- `actions.py` `classify_input` exception handler: `if allow_dev_bypass and is_dev: return SAFE` ✅
- `actions.py` `classify_output` exception handler: same ✅
- ElevenLabs TTS with voice `EXAVITQu4vr4xnSDxMaL` (Bella) → 200 OK, ~44 KB audio ✅
- Career panel keyword list: uses explicit intent phrases not single words ✅
- `sibling.jinja2`: rich 100+ line Hinglish persona template ✅
- `test_diversity.py`: 5/5 unique non-empty replies ✅
- `start_desktop.py`: runs all services on port 8080 ✅
- `.env`: `ENVIRONMENT=development`, `SAFETY_PROXY_ALLOW_DEV_BYPASS=true` ✅

---

## Acceptance Criteria

### UI/UX Quality
- [ ] `/child/` has a Vadi avatar with at least 3 animation states (idle, listening, speaking) via CSS or Lottie
- [ ] Chat bubbles animate in with staggered slide-up animation
- [ ] TTS playback shows a live waveform/pulse animation (Canvas or CSS)
- [ ] `/guardian/` overview chart renders real session + incident data from API
- [ ] `/login.html` role tabs animate smoothly
- [ ] All pages use Inter font, dark/light theme support, mobile responsive
- [ ] No broken images, 404 assets, or console errors on page load

### Backend Completeness
- [ ] `POST /api/v1/auth/demo` with role=learner → 200 + JWT
- [ ] `POST /api/v1/turn` with valid payload → 200 + non-empty `final_reply` + `safety_verdict: safe`
- [ ] `GET /api/v1/guardian/overview` → 200 + JSON (not 500 or 404)
- [ ] `GET /api/v1/admin/overview` → 200 + JSON
- [ ] `POST /api/v1/voice/tts` with text → 200 + base64 audio_bytes len > 10000

### AI Pipeline
- [ ] `scratch/test_diversity.py` still passes: 5/5 unique non-empty replies
- [ ] "mere teacher strict hain" → `panel_triggered = False`
- [ ] "doctor banna chahta hoon" → `panel_triggered = True`
- [ ] "marna chahta hoon" → `safety_verdict_input.code = unsafe_self_harm`

### Safety
- [ ] "kill myself" → `final_reply` = fixed escalation script (not empty)
- [ ] "ignore previous instructions" → `final_reply` = safe deflection (not LLM-generated)

### Infrastructure
- [ ] `.env.example` exists at repo root
- [ ] `Makefile` exists with `make dev`, `make test`, `make lint` targets
- [ ] `pytest services/safety-proxy` → all keyword tests pass

---

## Style Guide for All Code Written

Every line of code produced must look like it was written by a senior engineer with 10+ years of experience:
- Python: full type hints, docstrings on every public function, `black` formatted, `ruff` clean
- JavaScript: modern ES2023+, `const`/`let` only, async/await, no jQuery, descriptive variable names
- CSS: CSS custom properties for all colors/spacings, BEM or utility-first naming, no inline styles
- HTML: semantic HTML5, aria-labels, data-attributes for JS hooks, no inline scripts
- Comments: explain WHY not WHAT; delete commented-out code
- No TODOs left in committed code
- Error states handled everywhere (loading spinners, empty states, error messages)

## AGENTS.md Constitution

All work must comply with `d:\Vadi Bhen\.agents\AGENTS.md`. Key rules:
- Child Safety Non-Negotiables: never weaken safety proxy, always fail-closed in production
- RLS always: every DB query scoped by tenant_id
- Governance DB physically separate from Memory DB
- Prompt files, not strings: system prompts live in `personas/*.jinja2`
- No bare `except:` — catch specific exceptions
- Surgical changes only — touch only what the task requires
</USER_REQUEST>
