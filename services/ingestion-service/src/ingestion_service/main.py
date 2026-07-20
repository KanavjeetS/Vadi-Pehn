"""
FastAPI application for ingestion-service.
Endpoints:
  POST /internal/v1/documents/upload
  GET  /internal/v1/discrepancies
"""
from __future__ import annotations

from typing import Any
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from .service import DocumentIngestionService, DocumentUploadRequest, ExtractedAcademicRecord

app = FastAPI(title="Vadi-Pehn Document Ingestion Service", version="0.1.0")
service = DocumentIngestionService()


@app.get("/healthz")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "ingestion-service"}


@app.post("/internal/v1/documents/upload", response_model=ExtractedAcademicRecord, status_code=status.HTTP_201_CREATED)
async def upload_document(request: DocumentUploadRequest) -> ExtractedAcademicRecord:
    try:
        record = await service.process_document_upload(request)
        return record
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {e}")


@app.get("/internal/v1/discrepancies")
async def get_discrepancies() -> list[dict[str, Any]]:
    return [d.model_dump() for d in service._discrepancy_db]
