# Vadi-Pehn Development Skill (Local Copy)

Refer to full skill file at: d:\Vadi Bhen\.agents\skills\vadi-pehn-development\SKILL.md
Core methodology:
- Follow child safety non-negotiables strictly.
- Strict architecture rules: RLS always, Safety Proxy fail-closed (3-sec timeout = classifier_unavailable -> manual review / unsafe), prompt files not strings, Governance DB separate.
- General project integrity rules: NO hardcoded test results, NO facade implementations, NO fabricated verification outputs, NO bypassed safety checks.
