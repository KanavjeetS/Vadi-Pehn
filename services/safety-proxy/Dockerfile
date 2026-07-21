FROM python:3.12-slim

WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic pydantic-settings

ENV PYTHONPATH=/app:/app/services/safety-proxy/src
EXPOSE 8080
CMD ["uvicorn", "safety_proxy.main:app", "--host", "0.0.0.0", "--port", "8080"]
