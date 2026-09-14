"""
Patients router — GET /api/patients, GET /api/patients/{id},
GET /api/patients/{id}/timeline, POST /api/patients/{id}/analyse
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.backend.db import get_db
from src.backend.models import AdverseEvent, Deviation, DeviationStatus, LabResult, Patient, Visit
from src.backend.schemas import (
    AdverseEventOut,
    DeviationOut,
    LabResultOut,
    PatientAnalyseResponse,
    PatientOut,
    PatientSummary,
    PatientTimeline,
    TimelineVisit,
    VisitOut,
)

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("", response_model=list[PatientSummary])
def list_patients(
    site_id: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Patient)
    if site_id:
        q = q.filter(Patient.site_id == site_id)
    patients = q.order_by(Patient.id).all()

    results = []
    for p in patients:
        dev_count = (
            db.query(func.count(Deviation.id))
            .filter(Deviation.patient_id == p.id, Deviation.status == DeviationStatus.OPEN)
            .scalar()
        )
        results.append(
            PatientSummary(
                id=p.id,
                site_id=p.site_id,
                age=p.age,
                sex=p.sex,
                status=p.status,
                enrollment_date=p.enrollment_date,
                open_deviation_count=dev_count or 0,
            )
        )
    return results


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return patient


@router.get("/{patient_id}/timeline", response_model=PatientTimeline)
def get_patient_timeline(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    visits = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_number)
        .all()
    )

    all_deviations = (
        db.query(Deviation)
        .filter(Deviation.patient_id == patient_id)
        .order_by(Deviation.detected_date)
        .all()
    )

    adverse_events = (
        db.query(AdverseEvent)
        .filter(AdverseEvent.patient_id == patient_id)
        .order_by(AdverseEvent.onset_date)
        .all()
    )

    # Map deviations and lab results to each visit
    dev_by_visit: dict[int | None, list] = {}
    for dev in all_deviations:
        dev_by_visit.setdefault(dev.visit_id, []).append(dev)

    timeline_visits = []
    for v in visits:
        labs = (
            db.query(LabResult)
            .filter(LabResult.visit_id == v.id)
            .all()
        )
        timeline_visits.append(
            TimelineVisit(
                visit_id=v.id,
                visit_number=v.visit_number,
                visit_name=v.visit_name,
                scheduled_date=v.scheduled_date,
                actual_date=v.actual_date,
                window_deviation_days=v.window_deviation_days,
                deviations=[DeviationOut.model_validate(d) for d in dev_by_visit.get(v.id, [])],
                lab_results=[LabResultOut.model_validate(lr) for lr in labs],
            )
        )

    return PatientTimeline(
        patient=PatientOut.model_validate(patient),
        visits=timeline_visits,
        all_deviations=[DeviationOut.model_validate(d) for d in all_deviations],
        adverse_events=[AdverseEventOut.model_validate(ae) for ae in adverse_events],
    )


@router.post("/{patient_id}/analyse", response_model=PatientAnalyseResponse)
def analyse_patient(patient_id: str, db: Session = Depends(get_db)):
    """Run deviation detection for a single patient and return results."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    from src.backend.services.analysis_service import run_patient_analysis
    created = run_patient_analysis(db, patient_id)

    total_open = (
        db.query(func.count(Deviation.id))
        .filter(Deviation.patient_id == patient_id, Deviation.status == DeviationStatus.OPEN)
        .scalar()
    )

    return PatientAnalyseResponse(
        patient_id=patient_id,
        deviations_created=created,
        total_open_deviations=total_open or 0,
    )
