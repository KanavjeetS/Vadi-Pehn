# Safety Proxy — NeMo Guardrails reverse proxy
# Phase 0: dev target returns SAFE for all requests (no GPU needed)
# Phase 2: prod target builds full NeMo Guardrails + Llama-Guard-3-8B
#
# GUARDRAILS G-001: This container is the ONLY network path to vllm-main.
# Orchestration container does NOT have a route to vllm-main directly.

ARG PYTHON_VERSION=3.12

# ── Dev target (Phase 0 stub — no GPU, always returns SAFE) ───────────────
FROM python:${PYTHON_VERSION}-slim AS dev

WORKDIR /app
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY src/ ./src/

EXPOSE 8080
ENV ENVIRONMENT=development

CMD ["uvicorn", "src.safety_proxy.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]

# ── Prod target (Phase 2 — NeMo Guardrails + vLLM classifier) ────────────
FROM python:${PYTHON_VERSION}-slim AS prod

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config.yml .
COPY rails/ ./rails/

EXPOSE 8080
ENV ENVIRONMENT=production

CMD ["uvicorn", "src.safety_proxy.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
