FROM python:3.12-slim
WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx asyncpg pydantic pydantic-settings
ENV PYTHONPATH=/app:/app/services/ingestion-service/src
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn ingestion_service.main:app --host 0.0.0.0 --port ${PORT}"]
