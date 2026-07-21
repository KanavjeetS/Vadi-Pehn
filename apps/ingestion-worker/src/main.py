"""
Document Ingestion Worker Entrypoint for Vadi-Pehn (Service C).
Asynchronous queue-driven processing for academic records, report cards,
spatial PII redaction, Curator Agent fact verification, and pgvector embeddings.
"""

from __future__ import annotations

import logging
from fastapi import FastAPI

logger = logging.getLogger("ingestion-worker")

app = FastAPI(
    title="Vadi-Pehn Document Ingestion Worker",
    description="Service C — Queue Consumer, OCR, Spatial PII Redaction, Embeddings",
    version="2.0.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "ingestion-worker", "version": "2.0.0"}
