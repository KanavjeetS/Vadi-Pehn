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

from contextlib import AsyncExitStack, asynccontextmanager

# Force local URLs when running single-process desktop mode so internal API requests route cleanly locally
os.environ["DASHBOARD_BFF_URL"] = "http://127.0.0.1:8080"
os.environ["ORCHESTRATION_URL"] = "http://127.0.0.1:8080"
os.environ["VOICE_GATEWAY_URL"] = "http://127.0.0.1:8080"
os.environ["GOVERNANCE_SERVICE_URL"] = "http://127.0.0.1:8080"
os.environ["PANEL_SERVICE_URL"] = "http://127.0.0.1:8080"
os.environ["SAFETY_PROXY_URL"] = "http://127.0.0.1:8080"
os.environ["INGESTION_SERVICE_URL"] = "http://127.0.0.1:8080"
os.environ["IS_DEV"] = "true"

from services.config import get_settings
from services.logging_config import configure_logging

configure_logging("desktop-app")
get_settings.cache_clear()

# Resolve internal service import paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "api-gateway", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "ingestion-service", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "dashboard-bff", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "orchestration", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "voice-gateway", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "memory-service", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "governance-service", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "panel-service", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "safety-proxy", "src")))

from api_gateway.main import app as api_gateway_app, lifespan as api_gateway_lifespan  # noqa: E402
from ingestion_service.main import app as ingestion_app  # noqa: E402
from dashboard_bff.main import app as dashboard_app, lifespan as dashboard_lifespan  # noqa: E402
from voice_gateway.main import app as voice_gateway_app  # noqa: E402
from orchestration.main import app as orchestration_app, lifespan as orchestration_lifespan  # noqa: E402
from governance_service.main import app as governance_app, lifespan as governance_lifespan  # noqa: E402
from panel_service.main import app as panel_app  # noqa: E402
from safety_proxy.main import app as safety_proxy_app  # noqa: E402
from memory_service.main import app as memory_app, lifespan as memory_lifespan  # noqa: E402


from db.seed_synthetic_data import seed_all  # noqa: E402


@asynccontextmanager
async def desktop_lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(orchestration_lifespan(orchestration_app))
        await stack.enter_async_context(governance_lifespan(governance_app))
        await stack.enter_async_context(dashboard_lifespan(dashboard_app))
        await stack.enter_async_context(api_gateway_lifespan(api_gateway_app))
        await stack.enter_async_context(memory_lifespan(memory_app))
        try:
            await seed_all()
        except Exception as exc:
            print(f"[Seeder] Startup synthetic data seeding note: {exc}")
        yield



# Main Desktop Application FastAPI server
desktop_app = FastAPI(
    title="Vadi-Pehn Desktop Application Server",
    description="Unified Desktop Server for Vadi-Pehn Platform",
    version="1.1.0",
    lifespan=desktop_lifespan,
)

OVERRIDDEN_PROXY_PATHS = {
    "/api/v1/guardian/overview",
    "/api/v1/admin/overview",
}

# Include all sub-application routes directly on desktop_app for local single-process development.
# dashboard_app is listed before api_gateway_app so that dashboard_app's direct endpoint handlers
# receive and process overview requests rather than api_gateway's outbound HTTP proxy routes.
sub_apps = [
    dashboard_app,
    api_gateway_app,
    orchestration_app,
    voice_gateway_app,
    governance_app,
    panel_app,
    safety_proxy_app,
    ingestion_app,
    memory_app,
]

for sub_app in sub_apps:
    for route in sub_app.routes:
        # Filter out api_gateway's outbound HTTP proxy routes for overview endpoints in desktop mode
        if sub_app == api_gateway_app and getattr(route, "path", None) in OVERRIDDEN_PROXY_PATHS:
            continue
        if route not in desktop_app.routes:
            desktop_app.routes.append(route)

# Mount static webapp paths
child_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "webapp", "child"))
guardian_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "webapp", "guardian"))
admin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "webapp", "admin"))
webapp_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "webapp"))

desktop_app.mount("/child", StaticFiles(directory=child_dir, html=True), name="child_app")
desktop_app.mount("/guardian", StaticFiles(directory=guardian_dir, html=True), name="guardian_app")
desktop_app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin_app")
desktop_app.mount("/", StaticFiles(directory=webapp_root, html=True), name="static_root")


def main() -> None:
    port = 8080
    url = f"http://127.0.0.1:{port}"
    print("===============================================================")
    print("  Vadi-Pehn Virtual Sibling-Mentor Platform — Desktop Server")
    print(f"  Child Companion App  : {url}/child/")
    print(f"  Guardian Governance  : {url}/guardian/")
    print(f"  Admin Observability  : {url}/admin/")
    print("===============================================================")
    
    # Auto-open Child app in default browser
    webbrowser.open(f"{url}/child/")
    uvicorn.run(desktop_app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
