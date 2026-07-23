## 2026-07-23T19:57:21Z
<USER_REQUEST>
You are the Lead Frontend Engineer & Product/UX Designer (@backend-engineer & @doc-keeper) for Milestone 4 of Vadi-Pehn Full MVP Refinement.
Working directory: d:\Vadi Bhen
Metadata directory: d:\Vadi Bhen\.agents\worker_m4_refine

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks for Milestone 4 (Divisions 6, 9, 11 - Web App UI Overhaul):
Rebuild all web application portals under `webapp/` into a 2026 world-class UI/UX:
1. `webapp/login.html`: Glassmorphism card, animated gradient mesh background, sliding role tabs (Child/Guardian/Admin), one-click demo login buttons, form validation, particle background effect. Smooth page transition to dashboard.
2. `webapp/signup.html`: Matching design language, step-by-step form wizard (role select -> account details -> profile setup), password strength meter, guardian linking code field, animated progress bar.
3. `webapp/child/index.html` + `child.js`:
   - Vadi avatar character with 3 animation states (idle, listening, speaking) using CSS sprites / Lottie / Canvas.
   - Chat bubbles with staggered slide-in animation.
   - Live audio waveform visualizer (Web Audio API canvas animation) during TTS audio playback.
   - XP progress bar, streak counter, level badge.
   - Mood selector emoji chips & topic chips.
   - Background particle animations & dark mode toggle.
   - Typing indicator & voice input pulsing visualizer.
4. `webapp/guardian/index.html` + `guardian.js`:
   - Real data from `/api/v1/guardian/overview` (no hardcoded zero numbers!).
   - Chart.js animated line chart for session frequency & donut chart for topic distribution.
   - Safety incident timeline with SLA severity badges.
   - Animated consent toggle switches & learner profile card.
5. `webapp/admin/index.html` + `admin.js`:
   - Real data from `/api/v1/admin/overview` and `/api/v1/admin/observability/metrics`.
   - KPI metric tiles with animated counters, Groq LLM status badge, recent incidents table.

Ensure all pages use Inter font, CSS custom properties, WCAG 2.1 AA accessibility, and responsive layouts.
Write a handoff report at `d:\Vadi Bhen\.agents\worker_m4_refine\handoff.md` detailing all frontend changes and UI verification.
</USER_REQUEST>
