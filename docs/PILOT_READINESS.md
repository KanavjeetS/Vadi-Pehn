# Vadi-Pehn pilot readiness gates

This document is the release checklist for a staging pilot. A green unit-test
run is necessary but does not prove that the external model, database, or
LiveKit services are healthy.

## Start staging

1. Copy `infra/.env.staging.example` into a secret manager; do not commit it.
2. Provide real vLLM main/classifier, embedding, Whisper, Kokoro, Piper, and
   LiveKit endpoints through the centralized settings in `services/config.py`.
   The compose file includes LiveKit and vLLM containers for a self-hosted
   pilot; use managed equivalents by setting the corresponding URLs.
3. Apply the memory migrations to `postgres-primary` and the governance
   migrations under `db/migrations/governance` to `postgres-governance`.
4. Start the stack with:

```text
docker compose --env-file infra/.env.staging -f infra/docker-compose.mvp.yml up -d --build
```

The stack must fail startup when JWT, LiveKit, or internal service secrets are
missing. `SAFETY_PROXY_ALLOW_DEV_BYPASS` must remain `false`.
Database passwords, MinIO credentials, model identifiers, and the embedding
endpoint are also required by the pilot compose file.

## Automated gates

```text
python -m black --check services eval
python -m ruff check services eval
python -m pytest -q
```

Required results:

- 100% safety red-team corpus pass rate.
- 100% tenant-isolation and forced-RLS tests pass.
- No LLM call when input safety is unsafe or unavailable.
- No unsafe sentence chunk reaches TTS or LiveKit.
- Voice p95 budgets: STT ≤500 ms, input safety ≤300 ms, first LLM chunk
  ≤1200 ms, output safety ≤300 ms, first TTS ≤500 ms, total ≤3700 ms.

## Failure drills

- Stop the classifier: the next turn must return `classifier_unavailable`,
  produce no LLM output, and create an auditable governance event for unsafe
  paths.
- Stop Governance: incident creation must invoke the configured on-call
  webhook and return `pending_manual_review`.
- Revoke conversation consent: subsequent memory writes must abort and the
  purge job must remove the learner's memory rows.
- Stop LiveKit: the voice request must fail visibly; it must not claim that
  audio was published.
- Send a learner token to guardian/admin routes and a mismatched tenant in a
  body: both must be rejected.

## Frontend integration contract

The exact frontend can be added without changing the service boundaries. It
should use the API gateway routes `/api/v1/guardian/enroll`,
`/api/v1/guardian/learners`, `/api/v1/guardian/consent`, `/api/v1/turn`,
`/api/v1/voice/turn`, and the LiveKit token route. Once the frontend source is
shared, browser tests must cover enrollment, learner provisioning, consent
revocation, text turn, voice connect, barge-in, and guardian isolation.
