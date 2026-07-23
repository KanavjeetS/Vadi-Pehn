"""
Structured JSON Logging Module for Vadi-Pehn Platform.
Provides configure_logging() to set up Python structured JSON logging across all entry points.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects for structured log aggregation."""

    def __init__(self, service_name: str | None = None) -> None:
        super().__init__()
        self.service_name = service_name or os.environ.get("SERVICE_NAME", "vadi-pehn-service")

    def format(self, record: logging.LogRecord) -> str:
        log_object: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self.service_name,
            "message": record.getMessage(),
        }

        if hasattr(record, "request_id") and record.request_id:
            log_object["request_id"] = record.request_id

        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        extra = getattr(record, "extra", None)
        if extra:
            for key, val in extra.items():
                if key not in log_object and not key.startswith("_"):
                    log_object[key] = val

        return json.dumps(log_object)


def configure_logging(service_name: str | None = None, log_level: str | int | None = None) -> None:
    """Configures root logger with JSONFormatter writing to sys.stdout."""
    level_str = log_level or os.environ.get("LOG_LEVEL", "INFO")
    if isinstance(level_str, str):
        level = getattr(logging, level_str.upper(), logging.INFO)
    else:
        level = level_str

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicate log entries
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(JSONFormatter(service_name=service_name))
    root_logger.addHandler(stream_handler)
