"""
Trials router — GET /api/trials, GET /api/trials/{id}/protocol
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.models import ClinicalTrial
from src.backend.schemas import TrialOut

router = APIRouter(prefix="/api/trials", tags=["trials"])


@router.get("", response_model=list[TrialOut])
def list_trials(db: Session = Depends(get_db)):
    return db.query(ClinicalTrial).all()


@router.get("/{trial_id}", response_model=TrialOut)
def get_trial(trial_id: str, db: Session = Depends(get_db)):
    trial = db.query(ClinicalTrial).filter(ClinicalTrial.id == trial_id).first()
    if not trial:
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")
    return trial


@router.get("/{trial_id}/protocol")
def get_protocol(trial_id: str, db: Session = Depends(get_db)):
    """Return the raw protocol JSON for the trial."""
    trial = db.query(ClinicalTrial).filter(ClinicalTrial.id == trial_id).first()
    if not trial:
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")

    # Load from disk — the canonical source of truth
    from src.backend.config import settings
    protocol_path = Path(settings.protocol_path)
    if not protocol_path.exists():
        raise HTTPException(status_code=500, detail="Protocol file not found on server")

    with open(protocol_path, encoding="utf-8") as f:
        return json.load(f)
