FROM python:3.12-slim
WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx asyncpg pydantic pydantic-settings
ENV PYTHONPATH=/app:/app/services/api-gateway/src
EXPOSE 8000
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
