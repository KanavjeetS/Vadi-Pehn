FROM python:3.12-slim
WORKDIR /app
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn httpx asyncpg pydantic pydantic-settings jinja2
ENV PYTHONPATH=/app:/app/services/panel-service/src:/app/services/sibling-training/src
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn panel_service.main:app --host 0.0.0.0 --port ${PORT}"]
