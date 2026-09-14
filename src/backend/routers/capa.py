"""
CAPA router — GET /api/capa, GET /api/capa/{id}, PUT /api/capa/{id},
POST /api/capa/generate
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.models import CAPA, CAPAStatus, Deviation
from src.backend.schemas import (
    CapaGenerateRequest,
    CapaGenerateResponse,
    CapaOut,
    CapaUpdate,
)

router = APIRouter(prefix="/api/capa", tags=["capa"])


@router.get("", response_model=list[CapaOut])
def list_capas(
    site_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(CAPA)
    if site_id:
        q = q.filter(CAPA.site_id == site_id)
    if status:
        q = q.filter(CAPA.status == status.upper())
    return q.order_by(CAPA.id.desc()).all()


@router.get("/{capa_id}", response_model=CapaOut)
def get_capa(capa_id: int, db: Session = Depends(get_db)):
    capa = db.query(CAPA).filter(CAPA.id == capa_id).first()
    if not capa:
        raise HTTPException(status_code=404, detail=f"CAPA {capa_id} not found")
    return capa


@router.put("/{capa_id}", response_model=CapaOut)
def update_capa(capa_id: int, update: CapaUpdate, db: Session = Depends(get_db)):
    capa = db.query(CAPA).filter(CAPA.id == capa_id).first()
    if not capa:
        raise HTTPException(status_code=404, detail=f"CAPA {capa_id} not found")

    for field, value in update.model_dump(exclude_none=True).items():
        setattr(capa, field, value)

    db.commit()
    db.refresh(capa)
    return capa


@router.post("/generate", response_model=CapaGenerateResponse)
def generate_capa(
    req: CapaGenerateRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a CAPA narrative for the given deviation using watsonx.ai.

    If watsonx.ai is not configured, returns a deterministic fallback template.
    The narrative is stored in capa.watsonx_narrative for audit purposes.
    """
    dev = db.query(Deviation).filter(Deviation.id == req.deviation_id).first()
    if not dev:
        raise HTTPException(
            status_code=404, detail=f"Deviation {req.deviation_id} not found"
        )

    from src.backend.services.capa_generator import generate_capa_narrative

    narrative, source = generate_capa_narrative(db, dev)

    # Upsert CAPA record
    capa = db.query(CAPA).filter(CAPA.deviation_id == dev.id).first()
    if not capa:
        capa = CAPA(
            deviation_id=dev.id,
            site_id=dev.site_id,
            status=CAPAStatus.OPEN,
            watsonx_narrative=narrative,
            source=source,
        )
        db.add(capa)
    else:
        capa.watsonx_narrative = narrative
        capa.source = source
    db.commit()
    db.refresh(capa)

    return CapaGenerateResponse(
        capa_id=capa.id,
        deviation_id=dev.id,
        narrative=narrative,
        source=source,
    )
