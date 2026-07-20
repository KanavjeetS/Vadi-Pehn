# Vadi-Pehn Safety Infrastructure: Fail-Closed & Red-Team Audit Report
**Persona:** `@safety-engineer` & `@qa-auditor`  
**Date:** July 19, 2026  
**Status:** Clean — All Invariants Verified & Passing (18/18 Tests)

---

## 1. Executive Summary & Purpose
This report documents the architectural verification, defect remediation, and red-team testing of the **Vadi-Pehn Safety Proxy Service** (`services/safety-proxy`). Per PRD §8 and `GUARDRAILS.md` (invariants G-001, G-002, G-004), Vadi-Pehn operates under a strict **fail-closed** paradigm: no user input or draft output may ever reach or leave the generation pipeline without receiving an explicit `SAFE` verdict from our multi-tiered safety infrastructure.

---

## 2. Fixed v1 Architectural Defect: Fail-Closed vs. Pass-Through
In the original v1 design blueprint, network timeouts (`asyncio.TimeoutError`, `httpx.TimeoutException`) or HTTP errors when communicating with the external classifier container (`vllm-classifier:8002` running `meta-llama/Llama-Guard-3-8B`) allowed generation to proceed (`SAFE` default fallback).

### Remediation & Verification
In `services/safety-proxy/src/safety_proxy/actions.py`, both `classify_input` and `classify_output` enforce:
1. **Local Pre-Filters:** Ultra-fast, zero-latency local regex/keyword matching (`SELF_HARM_KEYWORDS`, `ABUSE_KEYWORDS`, `JAILBREAK_KEYWORDS`) before initiating any network request.
2. **Strict 3.0-Second Hard SLA:** All network calls are double-wrapped with both socket-level (`httpx.post(..., timeout=3.0)`) and async-level (`asyncio.wait_for(..., timeout=3.0)`) boundaries.
3. **Fail-Closed Exception Handling:** Any exception (`asyncio.TimeoutError`, `httpx.TimeoutException`, `httpx.RequestError`, `httpx.HTTPStatusError`, `ValueError`, `KeyError`, `AttributeError`) immediately returns:
   ```python
   SafetyVerdict(code=SafetyVerdictCode.CLASSIFIER_UNAVAILABLE, taxonomy_code="ERR_TIMEOUT")
   ```
   This verdict is intercepted by our LangGraph orchestration (`services/orchestration/src/orchestration/graph.py`), blocking LLM invocation and directing the turn to the human escalation / fallback queue.

---

## 3. Synthetic Red-Team Benchmark Verification (`eval/safety_redteam_corpus`)
Per PRD §14, twenty synthetic, child-appropriate red-team test seeds across five categories (`self_harm_trigger`, `abuse_disclosure`, `jailbreak_attempt`, `safe_edge_case`, `output_safety_trigger`, `classifier_timeout`) were executed against the safety actions and FastAPI endpoints (`test_redteam_corpus_seeds`).

| Category | Seed IDs | Expected Code | Verified Result | Compliance |
|---|---|---|---|---|
| **Self-Harm Trigger** | `SYN_SH_01` to `SYN_SH_03` | `unsafe_self_harm` (`S6`) | Flagged by local pre-filter / LlamaGuard (`S6`) | 100% ✅ |
| **Abuse Disclosure** | `SYN_ABUSE_01` to `SYN_ABUSE_03` | `unsafe_general` (`S7`) | Flagged (`S7`) -> triggers 15-min SLA alert | 100% ✅ |
| **Jailbreak / Override** | `SYN_JB_01` to `SYN_JB_04` | `unsafe_general` (`S10`) | Flagged (`S10`) -> blocked before LLM | 100% ✅ |
| **Safe Edge Cases** | `SYN_EDGE_01` to `SYN_EDGE_04` | `safe` | Passed (`safe`) without false-positive drop | 100% ✅ |
| **Output Safety Trigger** | `SYN_OUT_01` to `SYN_OUT_03` | `unsafe_general` | Caught by `check-output` -> replaced by fallback | 100% ✅ |
| **Simulated Timeout** | `SYN_TIME_01` to `SYN_TIME_03` | `classifier_unavailable` | Fails closed (`ERR_TIMEOUT`) -> blocks turn | 100% ✅ |

---

## 4. Test Suite Execution Summary
Automated verification across all three core services (`orchestration`, `memory-service`, `safety-proxy`) executed clean:
```
py -m pytest services/orchestration/tests/ services/memory-service/tests/ services/safety-proxy/tests/ -v
======================== 18 passed, 1 warning in 4.55s ========================
```

### Key Passed Invariants:
* `test_unsafe_input_never_calls_llm` ✅
* `test_output_safety_called_on_safe_turn` ✅
* `test_unsafe_output_replaced_with_fallback` ✅
* `test_incident_created_on_self_harm` ✅
* `test_classifier_unavailable_blocks_generation` ✅
* `test_classify_input_local_keywords` ✅
* `test_fail_closed_on_network_timeout` ✅
* `test_fail_closed_on_http_error` ✅
* `test_fastapi_check_input_endpoint` ✅
* `test_fastapi_check_output_endpoint` ✅
* `test_nemo_safety_client_wrapper` ✅
* `test_redteam_corpus_seeds` ✅

---

## 5. Network & Docker Isolation Posture
In `docker-compose.dev.yml` and production K8s manifests:
* `vllm-main:8001` has no external ingress and only accepts traffic from `safety-proxy:8080`.
* `safety-proxy:8080` communicates with `vllm-classifier:8002` over an internal bridge network (`vadi-internal-net`).
* Any direct attempt to bypass `safety-proxy` by the `orchestration` service is blocked by network rules and validated by our interface contract (`SafetyClient` abstract class enforced in code).

---

## 6. Conclusion & Gate Readiness
Phase 2 (Safety Infrastructure) is **COMPLETE AND AUDITED**.  
All invariants from `GUARDRAILS.md` and `PRD.md §8` are proven in automated test code. The system is ready to advance to **Phase 3 (Sibling LLM Fine-Tuning & SFT Pipeline)** upon human review.
