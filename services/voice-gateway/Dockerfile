FROM python:3.12-slim

WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic pydantic-settings livekit-api livekit

ENV PYTHONPATH=/app:/app/services/voice-gateway/src:/app/services/safety-proxy/src
EXPOSE 8000
CMD ["uvicorn", "voice_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
