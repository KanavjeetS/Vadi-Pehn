"""
FastAPI entry point for the Panel Service.
Implements: PRD §5 (Multi-Agent Career Panel), SD §4.4 (Panel Microservice).
"""
from __future__ import annotations

import sys
import os
from uuid import UUID

from fastapi import FastAPI, HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from panel_service.crew import CrewAIPanelRunner
from panel_service.diversity import PanelSelector
from panel_service.models import (
    OCRDocumentRequest,
    OCRDocumentResponse,
    PanelRequest,
    PanelResponse,
)
from panel_service.slm_ocr import QwenSLMOCRService


app = FastAPI(
    title="Vadi-Pehn Panel Service",
    description="Multi-Agent Career Panel (CrewAI + MoE + SLM OCR) service.",
    version="0.1.0",
)

selector = PanelSelector()
runner = CrewAIPanelRunner()
ocr_service = QwenSLMOCRService()


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "panel-service"}


@app.post("/internal/v1/panel/trigger", response_model=PanelResponse)
async def trigger_panel(request: PanelRequest) -> PanelResponse:
    """
    Triggers a 3-agent career exploration panel (SD §4.4).
    """
    try:
        personas, status = await selector.select_panel_personas(
            learner_id=request.learner_id,
            top_interests=request.top_interests,
            active_relationships=[],
        )
        return await runner.run_panel_turn(request=request, personas=personas)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/internal/v1/panel/ingest-document", response_model=OCRDocumentResponse)
async def ingest_document(request: OCRDocumentRequest) -> OCRDocumentResponse:
    """
    Processes academic document OCR with confidence gating (< 0.85 -> discrepancy queue).
    """
    try:
        return await ocr_service.process_document(request=request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
