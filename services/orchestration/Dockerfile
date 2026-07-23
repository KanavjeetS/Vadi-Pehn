FROM python:3.12-slim

WORKDIR /app
COPY services/orchestration/pyproject.toml /app/services/orchestration/pyproject.toml
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx asyncpg pydantic pydantic-settings \
    langgraph==0.2.74 langchain-core==0.3.80 jinja2 langfuse groq

ENV PYTHONPATH=/app:/app/services/orchestration/src:/app/services/memory-service/src:/app/services/safety-proxy/src
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn orchestration.main:app --host 0.0.0.0 --port ${PORT}"]
