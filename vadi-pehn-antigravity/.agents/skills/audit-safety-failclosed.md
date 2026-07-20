# Skill: Audit Safety Fail-Closed Behavior

## Objective
As the QA & Security Auditor (with @safety-engineer as required
co-reviewer for any finding here), verify that every path capable of
producing text a child will see has a genuine, untamperable safety gate,
and that every failure mode of that gate resolves closed, not open.

## Rules of Engagement
- This skill has authority to block a segment from being marked complete.
  A single bypass path found here outweighs any number of passing
  feature tests elsewhere.
- Read GUARDRAILS.md G-001 and G-004 first; this skill exists specifically
  to keep re-finding variants of those two problems before they ship.

## Instructions
1. Trace every code path that can call `llm_client.stream_reply()` or
   equivalent generation call. For each, confirm:
   a. It is reachable only after `check_input_safety` returned `SAFE`.
   b. Every chunk/sentence it produces passes `check_output` before being
      included in any response the child receives (text or voice).
2. Deliberately inject failures and confirm fail-closed behavior:
   - Force `SafetyClient.check_input`/`check_output` to raise, return a
     malformed payload, or hang past the timeout — confirm the system
     blocks generation and does not fall back to "safe" in any of these
     cases (extend `tests/test_safety.py`'s pattern to any new call site).
   - Confirm a `classifier_unavailable` verdict actually routes to human
     review (an incident/log entry is produced), not just a generic error
     message with no downstream trace.
3. Check the Voice Gateway specifically (once built) for the historical
   gap this project already found once: output safety silently skipped on
   the streamed voice path (GUARDRAILS.md G-004). Re-check this every time
   the voice pipeline changes, not just once.
4. Check that self-harm-flagged turns never reach ordinary RAG memory
   (GUARDRAILS.md G-003) — query the memory store after a simulated
   self-harm turn and assert it's empty for that turn.
5. Any finding gets logged as a new GUARDRAILS.md entry (using the
   template at the bottom of that file) once fixed and tested, so it
   doesn't recur in a future segment.
