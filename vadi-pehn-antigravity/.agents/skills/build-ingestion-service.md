# Skill: Build Ingestion Service (olmOCR Report Card Pipeline)

## Objective
As the Backend/Data Engineer pairing, build the Ingestion Service: MinIO
upload, PII redaction, olmOCR extraction, confidence gating, and the
discrepancy reconciliation queue — System Design §2, §3.5; PRD §9.

## Rules of Engagement
- Redaction happens BEFORE the image reaches the olmOCR vision-language
  model — a VLM that "sees" an unredacted image has already processed
  that third party's data regardless of downstream handling (PRD §9.2).
  Verify this ordering is real in the pipeline, not just documented.
- Confidence gate at 0.85 is a hard threshold — anything below routes to
  `discrepancy_log`, never auto-writes to the learner profile.
- Reviewer access to flagged records must be scoped to the specific
  record, not free browsing, and logged to `reviewer_access_log` (System
  Design §3.4) — this applies here even though that table lives in the
  Governance DB; call across service boundaries rather than duplicating it.

## Instructions
1. Implement `document_uploads` and `discrepancy_log` schema per System
   Design §3.5.
2. Implement `POST /v1/documents/upload` and
   `GET /v1/documents/{document_id}/status` per System Design §4.1.
3. Build the redaction step (spatial-masking + regex for third-party
   names/rankings, PRD §9.1) with a secondary automated verification pass
   before the image is handed to olmOCR (PRD §9.2's "second check" gap
   closure).
4. Wire the olmOCR (Qwen2-VL-7B) extraction call, producing linearized
   markdown output, and implement the confidence-gate branch.
5. Implement the reconciliation comparison against in-app performance
   metrics, writing discrepancies to `discrepancy_log` with `status=open`.
6. Every reviewer read of a flagged document must call the Governance
   Service to log a `reviewer_access_log` entry first — implement this as
   a required pre-check, not optional telemetry.
7. Write tests using synthetic report-card fixtures ONLY (see
   `.agents/rules/child-safety-non-negotiables.md` rule 4) covering:
   below-threshold routing, redaction-before-OCR ordering, and the
   reviewer-access-log requirement.
