"""
Ingestion Service package.
"""

from .service import (
    DocumentIngestionService,
    DocumentUploadRequest,
    ExtractedAcademicRecord,
    DiscrepancyRecord,
)

__all__ = [
    "DocumentIngestionService",
    "DocumentUploadRequest",
    "ExtractedAcademicRecord",
    "DiscrepancyRecord",
]
