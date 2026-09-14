"""
Analysis router — POST /api/analysis/run
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.schemas import AnalysisRunResponse

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/run", response_model=AnalysisRunResponse)
def run_analysis(db: Session = Depends(get_db)):
    """
    Execute full deviation detection + risk scoring across all patients.

    This is the same logic as services/run_analysis.py but exposed as an
    HTTP endpoint so the dashboard "Run Analysis" button can trigger it.
    """
    from src.backend.services.analysis_service import run_full_analysis

    summary = run_full_analysis(db=db)

    site_summary = [
        {
            "site_id": r["site_id"],
            "total_score": r["total_score"],
            "risk_tier": r["risk_tier"],
            "major_open_count": r["major_open"],
            "minor_open_count": r["minor_open"],
            "admin_open_count": r["admin_open"],
        }
        for r in summary["site_risk_scores"]
    ]

    return AnalysisRunResponse(
        deviations_created=summary["total_new_deviations_created"],
        total_open_deviations=summary["total_open_deviations"],
        sites_scored=len(site_summary),
        site_risk_summary=site_summary,
    )
