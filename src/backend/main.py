"""
TrialGuard FastAPI application entry point.

Start with:
    uvicorn src.backend.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.backend.engine.protocol_loader import get_protocol
from src.backend.schemas import HealthResponse

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — runs once at startup and once at shutdown
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load and cache the protocol on startup so all requests share the same instance."""
    try:
        proto = get_protocol()
        logger.info(
            "Protocol loaded: %s v%s (%d rules)",
            proto.title,
            proto.version,
            len(proto.rules),
        )
    except Exception as exc:
        logger.warning("Protocol load failed at startup: %s", exc)

    yield  # Application runs here

    logger.info("TrialGuard shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# Application instance
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TrialGuard",
    description=(
        "Clinical Trial Risk Monitor & Protocol Deviation Detector. "
        "Deterministic rule engine for compliance decisions; "
        "watsonx.ai for CAPA narrative generation and risk explanation."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# CORS — allow Vite dev server and any localhost origin
# ─────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────────────────────

from src.backend.routers import (  # noqa: E402
    analysis,
    bob,
    capa,
    deviations,
    patients,
    reports,
    sites,
    trials,
)
from src.backend.routers.mcp import router as mcp_router  # noqa: E402

app.include_router(trials.router)
app.include_router(sites.router)
app.include_router(patients.router)
app.include_router(deviations.router)
app.include_router(capa.router)
app.include_router(analysis.router)
app.include_router(reports.router)
app.include_router(mcp_router)
app.include_router(bob.router)


# ─────────────────────────────────────────────────────────────────────────────
# Serve React frontend (production build)
# ─────────────────────────────────────────────────────────────────────────────

# Path to the frontend build directory
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

# Mount static files for assets (CSS, JS, images)
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["health"])
def health():
    try:
        get_protocol()
        protocol_ok = True
    except Exception:
        protocol_ok = False

    return HealthResponse(
        status="ok",
        version="1.0.0",
        protocol_loaded=protocol_ok,
    )


@app.get("/", tags=["health"])
def root():
    """Root endpoint - serves React frontend in production, JSON info in development."""
    if frontend_dist.exists():
        return FileResponse(frontend_dist / "index.html")
    return {
        "service": "TrialGuard",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Catch-all for React Router client-side routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/{full_path:path}", include_in_schema=False)
def serve_react_app(full_path: str):
    """
    Serve React index.html for all non-API routes.
    This enables client-side routing to work with React Router.
    
    API routes (/api/*, /mcp, /docs, /health, /openapi.json, etc.) are handled by 
    their respective routers and won't reach this handler due to FastAPI's route 
    matching priority (more specific routes are matched first).
    """
    # Skip API routes to avoid conflicts (shouldn't reach here due to route priority, but being defensive)
    if full_path.startswith("api/") or full_path.startswith("mcp") or full_path in ["docs", "health", "openapi.json"]:
        return {"error": "Route not found"}
    
    if frontend_dist.exists():
        # Check if the path is a static file
        requested_file = frontend_dist / full_path
        if requested_file.exists() and requested_file.is_file():
            return FileResponse(requested_file)
        # Otherwise serve index.html for client-side routing
        return FileResponse(frontend_dist / "index.html")
    
    # If frontend build doesn't exist, return 404
    return {"error": "Frontend build not found. Run `cd src/frontend && npm run build`"}
