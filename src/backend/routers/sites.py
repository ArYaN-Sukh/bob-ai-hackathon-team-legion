"""
Sites router — GET /api/sites, GET /api/sites/{id}, GET /api/sites/{id}/risk-history
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.models import Deviation, DeviationSeverity, DeviationStatus, Site, SiteRiskScore
from src.backend.schemas import SiteRiskScoreOut, SiteWithRisk

router = APIRouter(prefix="/api/sites", tags=["sites"])


def _enrich_site(site: Site, db: Session) -> SiteWithRisk:
    """Attach latest risk score and open deviation counts to a site object."""
    # Latest risk score
    latest = (
        db.query(SiteRiskScore)
        .filter(SiteRiskScore.site_id == site.id)
        .order_by(SiteRiskScore.score_date.desc(), SiteRiskScore.id.desc())
        .first()
    )

    # Open deviation counts by severity
    counts = (
        db.query(Deviation.severity, func.count(Deviation.id))
        .filter(Deviation.site_id == site.id, Deviation.status == DeviationStatus.OPEN)
        .group_by(Deviation.severity)
        .all()
    )
    count_map = {sev: cnt for sev, cnt in counts}

    return SiteWithRisk(
        id=site.id,
        trial_id=site.trial_id,
        name=site.name,
        city=site.city,
        country=site.country,
        principal_investigator=site.principal_investigator,
        status=site.status,
        enrolled_count=site.enrolled_count,
        target_enrollment=site.target_enrollment,
        activation_date=site.activation_date,
        created_at=site.created_at,
        latest_risk_score=latest.total_score if latest else None,
        latest_risk_tier=latest.risk_tier if latest else None,
        open_major_count=count_map.get(DeviationSeverity.MAJOR, 0),
        open_minor_count=count_map.get(DeviationSeverity.MINOR, 0),
        open_admin_count=count_map.get(DeviationSeverity.ADMINISTRATIVE, 0),
    )


@router.get("", response_model=list[SiteWithRisk])
def list_sites(db: Session = Depends(get_db)):
    sites = db.query(Site).order_by(Site.id).all()
    return [_enrich_site(s, db) for s in sites]


@router.get("/{site_id}", response_model=SiteWithRisk)
def get_site(site_id: str, db: Session = Depends(get_db)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return _enrich_site(site, db)


@router.get("/{site_id}/risk-history", response_model=list[SiteRiskScoreOut])
def get_site_risk_history(
    site_id: str,
    limit: int = 30,
    db: Session = Depends(get_db),
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")

    scores = (
        db.query(SiteRiskScore)
        .filter(SiteRiskScore.site_id == site_id)
        .order_by(SiteRiskScore.score_date.desc(), SiteRiskScore.id.desc())
        .limit(limit)
        .all()
    )
    return scores
