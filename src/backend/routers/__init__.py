"""
Routers package — exposes all FastAPI routers.
"""
from src.backend.routers import (
    analysis,
    capa,
    deviations,
    mcp,
    patients,
    reports,
    sites,
    trials,
)

__all__ = [
    "analysis",
    "capa",
    "deviations",
    "mcp",
    "patients",
    "reports",
    "sites",
    "trials",
]
