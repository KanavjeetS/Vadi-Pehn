FROM python:3.12-slim

WORKDIR /app
COPY services/orchestration/pyproject.toml /app/services/orchestration/pyproject.toml
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx asyncpg pydantic pydantic-settings \
    langgraph==0.2.74 langchain-core==0.3.80 jinja2 langfuse

ENV PYTHONPATH=/app:/app/services/orchestration/src:/app/services/memory-service/src:/app/services/safety-proxy/src
EXPOSE 8000
CMD ["uvicorn", "orchestration.main:app", "--host", "0.0.0.0", "--port", "8000"]
