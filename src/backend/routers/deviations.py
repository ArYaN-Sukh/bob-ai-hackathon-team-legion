"""
Deviations router — GET /api/deviations, GET /api/deviations/{id},
PATCH /api/deviations/{id}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.models import Deviation
from src.backend.schemas import DeviationOut, DeviationUpdate

router = APIRouter(prefix="/api/deviations", tags=["deviations"])


# Map case-insensitive input to actual enum values
_SEVERITY_MAP = {
    "major": "Major",
    "minor": "Minor",
    "administrative": "Administrative",
}

_STATUS_MAP = {
    "open": "Open",
    "closed": "Closed",
    "pending_review": "Pending Review",
    "pending review": "Pending Review",
}


@router.get("", response_model=list[DeviationOut])
def list_deviations(
    site_id: str | None = None,
    patient_id: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    Return deviations with optional filters.

    severity: MAJOR | MINOR | ADMINISTRATIVE (case-insensitive)
    status: OPEN | CLOSED | PENDING_REVIEW (case-insensitive)
    """
    q = db.query(Deviation)
    if site_id:
        q = q.filter(Deviation.site_id == site_id)
    if patient_id:
        q = q.filter(Deviation.patient_id == patient_id)
    if severity:
        sev_val = _SEVERITY_MAP.get(severity.lower(), severity)
        q = q.filter(Deviation.severity == sev_val)
    if status:
        stat_val = _STATUS_MAP.get(status.lower(), status)
        q = q.filter(Deviation.status == stat_val)
    return q.order_by(Deviation.detected_date.desc()).limit(limit).all()


@router.get("/{deviation_id}", response_model=DeviationOut)
def get_deviation(deviation_id: int, db: Session = Depends(get_db)):
    dev = db.query(Deviation).filter(Deviation.id == deviation_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail=f"Deviation {deviation_id} not found")
    return dev


@router.patch("/{deviation_id}", response_model=DeviationOut)
def update_deviation(
    deviation_id: int,
    update: DeviationUpdate,
    db: Session = Depends(get_db),
):
    dev = db.query(Deviation).filter(Deviation.id == deviation_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail=f"Deviation {deviation_id} not found")

    if update.status is not None:
        new_status = _STATUS_MAP.get(update.status.lower(), update.status)
        if new_status not in _STATUS_MAP.values():
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status '{update.status}'. Must be one of: Open, Closed, Pending Review",
            )
        dev.status = new_status

    db.commit()
    db.refresh(dev)
    return dev
