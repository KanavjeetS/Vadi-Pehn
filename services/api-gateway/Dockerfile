FROM python:3.12-slim
WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx asyncpg pydantic pydantic-settings python-jose[cryptography]
ENV PYTHONPATH=/app:/app/services/api-gateway/src
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api_gateway.main:app --host 0.0.0.0 --port ${PORT}"]
