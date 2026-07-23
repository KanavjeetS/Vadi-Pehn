FROM python:3.12-slim
WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx asyncpg pydantic pydantic-settings numpy
ENV PYTHONPATH=/app:/app/services/memory-service/src
EXPOSE 8003
CMD ["uvicorn", "memory_service.main:app", "--host", "0.0.0.0", "--port", "8003"]
