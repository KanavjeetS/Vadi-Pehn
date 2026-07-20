# Safety Red-Team Corpus

Adversarial test cases for the Safety Proxy (PRD §8.4), used by
`.agents/skills/build-safety-proxy.md` and `/safety-audit`.

**Every example in this directory must be synthetic** — written to
resemble a category of harmful input, never copied or adapted from a real
conversation, real transcript, or real incident. See
`.agents/rules/child-safety-non-negotiables.md` rule 4.

## Format

One YAML file per category (`self_harm.yaml`, `jailbreak.yaml`,
`general_unsafe.yaml`, ...). Each entry:

```yaml
- id: sh-001
  input: "<synthetic example text>"
  expected_verdict: unsafe_self_harm
  expected_taxonomy_code: S6
  notes: "why this phrasing is a meaningful test, e.g. indirect phrasing, code-switched language, etc."
```

This directory starts empty. Populating it with an initial ~20 examples
across self-harm, jailbreak, and general-unsafe categories is the first
task in `.agents/skills/build-safety-proxy.md` — do that as part of
building the real Safety Proxy service, informed by the Aegis 2.0
taxonomy categories referenced in PRD §8.
