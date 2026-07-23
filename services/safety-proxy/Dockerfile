FROM python:3.12-slim

WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic pydantic-settings

ENV PYTHONPATH=/app:/app/services/safety-proxy/src
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn safety_proxy.main:app --host 0.0.0.0 --port ${PORT}"]
