"""
Vadi-Pehn Desktop Application Launcher & Unified Development Server.
Mounts all microservices (including voice-gateway) and serves separate Child (/child)
and Guardian (/guardian) web application routes.

Usage:
  py -3 start_desktop.py
"""
from __future__ import annotations

import os
import sys
import webbrowser
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Resolve internal service import paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "api-gateway", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "ingestion-service", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "dashboard-bff", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "orchestration", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "voice-gateway", "src")))

from api_gateway.main import app as api_gateway_app
from ingestion_service.main import app as ingestion_app
from dashboard_bff.main import app as dashboard_app
from voice_gateway.main import app as voice_gateway_app

# Main Desktop Application FastAPI server
desktop_app = FastAPI(
    title="Vadi-Pehn Desktop Application Server",
    description="Unified Desktop Server for Vadi-Pehn Platform",
    version="1.1.0",
)

# Mount internal service microservices
desktop_app.mount("/internal/v1/documents", ingestion_app)
desktop_app.mount("/api/v1/guardian/bff", dashboard_app)
desktop_app.mount("/api/v1/voice/gateway", voice_gateway_app)

# Include main Gateway routes directly on desktop_app
for route in api_gateway_app.routes:
    desktop_app.routes.append(route)

# Mount static webapp paths
child_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "webapp", "child"))
guardian_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "webapp", "guardian"))
webapp_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "webapp"))

desktop_app.mount("/child", StaticFiles(directory=child_dir, html=True), name="child_app")
desktop_app.mount("/guardian", StaticFiles(directory=guardian_dir, html=True), name="guardian_app")
desktop_app.mount("/", StaticFiles(directory=webapp_root, html=True), name="static_root")


def main() -> None:
    port = 8000
    url = f"http://127.0.0.1:{port}"
    print("===============================================================")
    print("  Vadi-Pehn Virtual Sibling-Mentor Platform — Desktop Server")
    print(f"  Child Companion App : {url}/child/")
    print(f"  Guardian Governance : {url}/guardian/")
    print("===============================================================")
    
    # Auto-open Child app in default browser
    webbrowser.open(f"{url}/child/")
    uvicorn.run(desktop_app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
