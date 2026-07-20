# Vadi-Pehn Sibling LLM Training & Alignment Audit Report (`Phase 3`)

**Date:** July 19, 2026  
**Auditor Personas:** `@backend-engineer`, `@researcher`, `@safety-engineer`, `@qa-auditor`  
**Milestone Status:** Phase 3 Complete (SFT + GRPO + Autoresearch + Replay Evaluation)

---

## 1. Executive Summary
We have built and verified the complete Sibling LLM Fine-Tuning (`SFT`) and RLHF (`GRPO`) alignment pipeline (`services/sibling-training/` and `scripts/corpus/`) following Karpathy's `nanochat` and `autoresearch` architectures, `PRD §8`, and `SystemDesign §10`.

Our evaluation suite verifies both automated unit metrics (**28 out of 28 passing unit tests across all services**) and end-to-end multi-turn conversation behavior (**100% pass rate on multi-turn replay scenarios** across all three child age bands).

---

## 2. Deliverables & Technical Compliance

### 2.1 Training Data Corpus Pipeline (`scripts/corpus/prepare.py` & `pii_scrubber.py`)
- **Mandatory PII Scrubbing (`RegexPIIScrubber`)**: Implements strict regex stripping for emails (`[REDACTED_EMAIL]`), Indian/Global phone numbers (`[REDACTED_PHONE]`), national IDs/Aadhaar/SSN (`[REDACTED_ID]`), and street addresses (`[REDACTED_ADDRESS]`).
- **Synthetic Conversation Seeds (`synthetic_conversations.json`)**: Curated developmentally appropriate seeds across:
  - Age Band 1 (8–10 years): Step-by-step math tutoring and celebrating independent achievement.
  - Age Band 2 (11–13 years): Biology tutoring, boundary enforcement against secrecy/dependency, and robotics career exploration.
  - Age Band 3 (14–17 years): Biotech/AI career pathways, exam schedule organization, and resisting sycophancy.
- **Deterministic Splitting**: Generated `data/train.jsonl` (8 samples) and `data/val.jsonl` (2 samples) with required `SYNTHETIC_CORPUS_V1` headers and 100% compliance checks.

### 2.2 Supervised Fine-Tuning (`SFT`) (`sft_trainer.py`)
- **Nanochat Architecture (`NanochatSFTTrainer` & `MockSFTTrainer`)**: Supports `Muon` and `AdamW` optimizer selection with FlashAttention-3 / GQA configurations for Llama-3.3-70B FP8.
- **Checkpointing SLA**: Enforces max 5-minute GPU checkpoint intervals (`vadi-pehn-sibling-sft-v<tag>.bin`).
- **Autoresearch Logging**: Emits step-by-step TSV metrics (`results.tsv`) tracking epoch, step, train/val loss, perplexity, safety score, and optimizer selection.

### 2.3 RLHF / GRPO Alignment & Reward Shaping (`grpo_trainer.py` & `reward.py`)
- **Group Relative Policy Optimization (`NanochatGRPOTrainer`)**: Samples $G=4$ candidate completions per prompt, computing normalized relative advantages $A_i = \frac{R_i - \bar{R}}{\sigma_R + \epsilon}$ without requiring a separate critic/value network.
- **Refusal-Aware Reward Shaping (`LlamaGuardRewardModel`)**:
  - `+1.0` base score + `+0.5` rapport bonus + `+0.5` developmental questioning bonus.
  - `-3.0` penalty for dependency-creating phrases (`"i am your only friend"`, `"keep secrets from your parents"`). Includes `_check_dependency_violation` prefix analysis (`cannot keep secrets`, `never keep secrets`) ensuring boundary setting is accurately rewarded rather than penalized.
  - `-2.0` penalty for unscrubbed PII leaks.
  - `-5.0` penalty when `Llama-Guard-3-8B` yields an `unsafe` classifier verdict.

### 2.4 Autoresearch Hyperparameter Exploration (`autoresearch.py`)
- **Safety Regression Gate**: `AutoresearchLoop` explores overnight grids across learning rates, optimizers (`Muon`/`AdamW`), and KL penalties. A candidate checkpoint is ONLY saved and accepted if it maintains **100% safety compliance (`safety_score >= 1.0`)** while improving validation loss.

---

## 3. Evaluation & Verification Results

### 3.1 Unit & Integration Suite (`28/28 PASSED`)
```
py -m pytest services/orchestration/tests/ services/memory-service/tests/ services/safety-proxy/tests/ services/sibling-training/tests/ -v
```
All 10 new tests in `services/sibling-training` and all 18 existing tests across orchestration, memory, and safety-proxy pass cleanly with zero errors.

### 3.2 Conversation Replay Suite (`eval/conversation_replay/replay_runner.py` — `100% PASS`)
Executed multi-turn replay scenarios across `REPLAY_AGE1_TUTORING`, `REPLAY_AGE2_BOUNDARIES`, and `REPLAY_AGE3_CAREER_PATH`.
- Total Scenarios: **3 / 3 PASSED**
- Total Conversation Turns Evaluated: **4 / 4 PASSED (100.0% Pass Rate)**
- Full Report Saved: `eval/conversation_replay/conversation_replay_report.json`

---

## 4. Sign-off & Human Gate
Phase 3 (`3A`, `3B`, `3C`, `3D`) is complete, verified, and audited. We are ready to proceed to **Phase 4 (Multi-Hybrid RAG Pipeline)** upon human approval (`⛔ HUMAN GATE`).
