"""
Analysis service for TrialGuard.

Provides the top-level entry point for running the deviation engine and risk
scorer against the live database, persisting results into the Deviation and
SiteRiskScore tables.

This module is the ONLY place that imports both the engine layer and the ORM.
It is NOT a FastAPI router — routers will call into this service in Phase 3.

DUPLICATE PREVENTION
--------------------
Before inserting a new Deviation row we check for an existing open deviation
with the same (patient_id, rule_id, visit_id).  If one exists we leave it
unchanged (it may have been updated by an investigator).

CAPA records are NOT created here.  They are generated on demand in Phase 4
via the watsonx CAPA generator.

IDEMPOTENCY
-----------
Running run_full_analysis() multiple times is safe.  Each run:
  * evaluates all patients fresh from the DB
  * skips deviations that already have an OPEN record
  * (re-)calculates and upserts site risk scores for today's date
"""
from __future__ import annotations

import json
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.db import SessionLocal
from src.backend.engine.deviation_engine import DeviationResult, evaluate_patient
from src.backend.engine.protocol_loader import Protocol, get_protocol
from src.backend.engine.risk_scorer import (
    SiteInputs,
    SiteRiskResult,
    compute_enrollment_deviation_pct,
    score_site,
)
from src.backend.models import (
    AdverseEvent,
    Deviation,
    DeviationSeverity,
    DeviationStatus,
    LabResult,
    Patient,
    RiskTier,
    Site,
    SiteRiskScore,
    Visit,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Deviation persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

def _existing_open_deviations(db: Session, patient_id: str) -> set[tuple]:
    """
    Return the set of (patient_id, rule_id, visit_id) tuples for all OPEN
    deviations belonging to *patient_id*.
    """
    rows = db.execute(
        select(Deviation.patient_id, Deviation.rule_id, Deviation.visit_id)
        .where(Deviation.patient_id == patient_id)
        .where(Deviation.status == DeviationStatus.OPEN)
    ).all()
    return {(r.patient_id, r.rule_id, r.visit_id) for r in rows}


def _persist_deviations(
    db: Session,
    results: list[DeviationResult],
    today: date,
    existing_open: set[tuple],
) -> int:
    """
    Insert new Deviation rows for results that are not already open.

    Returns the number of new rows inserted.
    """
    inserted = 0
    for result in results:
        key = result.dedup_key()
        if key in existing_open:
            continue  # Already have an open deviation for this violation

        deviation = Deviation(
            patient_id=result.patient_id,
            site_id=result.site_id,
            rule_id=result.rule_id,
            deviation_type=result.deviation_type,
            description=result.description,
            severity=result.severity,
            status=DeviationStatus.OPEN,
            detected_date=result.detected_date,
            evidence=result.evidence_json(),
            visit_id=result.visit_id,
        )
        db.add(deviation)
        existing_open.add(key)  # Prevent same-run duplicates
        inserted += 1

    return inserted


# ─────────────────────────────────────────────────────────────────────────────
# Risk score helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_site_inputs(db: Session, site: Site, today: date) -> SiteInputs:
    """
    Compute the SiteInputs for the risk scorer from live DB data.

    * Open deviation counts are counted directly from the Deviation table.
    * avg_capa_age_days is derived from open Deviation detected_dates
      (proxy for CAPA age until the CAPA table is populated in Phase 4).
    * data_query_rate_pct is approximated as % of patients with any open deviation.
    * enrollment_deviation_pct is computed from enrolled_count vs target.
    """
    from sqlalchemy import func

    # Count open deviations by severity for this site
    def _count(sev: DeviationSeverity) -> int:
        return db.execute(
            select(func.count())
            .select_from(Deviation)
            .where(Deviation.site_id == site.id)
            .where(Deviation.status == DeviationStatus.OPEN)
            .where(Deviation.severity == sev)
        ).scalar() or 0

    major = _count(DeviationSeverity.MAJOR)
    minor = _count(DeviationSeverity.MINOR)
    admin = _count(DeviationSeverity.ADMINISTRATIVE)

    # Average CAPA age proxy: average days since detection of open major/minor deviations
    open_detected_dates = db.execute(
        select(Deviation.detected_date)
        .where(Deviation.site_id == site.id)
        .where(Deviation.status == DeviationStatus.OPEN)
        .where(Deviation.severity.in_([DeviationSeverity.MAJOR, DeviationSeverity.MINOR]))
    ).scalars().all()

    if open_detected_dates:
        avg_age = sum((today - d).days for d in open_detected_dates) / len(open_detected_dates)
    else:
        avg_age = 0.0

    # Data query rate: % of patients at this site with >= 1 open deviation
    total_patients = db.execute(
        select(func.count()).select_from(Patient).where(Patient.site_id == site.id)
    ).scalar() or 0

    patients_with_deviation = db.execute(
        select(func.count(Deviation.patient_id.distinct()))
        .where(Deviation.site_id == site.id)
        .where(Deviation.status == DeviationStatus.OPEN)
    ).scalar() or 0

    dq_rate = (patients_with_deviation / total_patients * 100.0) if total_patients > 0 else 0.0

    enroll_dev = compute_enrollment_deviation_pct(site.enrolled_count, site.target_enrollment)

    return SiteInputs(
        site_id=site.id,
        major_open_count=major,
        minor_open_count=minor,
        admin_open_count=admin,
        avg_capa_age_days=round(avg_age, 1),
        data_query_rate_pct=round(dq_rate, 2),
        enrollment_deviation_pct=round(enroll_dev, 2),
    )


def _upsert_risk_score(db: Session, result: SiteRiskResult, today: date) -> None:
    """
    Insert or update the SiteRiskScore for today.

    If a score for (site_id, score_date=today) already exists, update it.
    Otherwise insert a new row.
    """
    existing = db.execute(
        select(SiteRiskScore)
        .where(SiteRiskScore.site_id == result.site_id)
        .where(SiteRiskScore.score_date == today)
    ).scalar_one_or_none()

    if existing:
        existing.total_score = result.total_score
        existing.risk_tier = result.risk_tier
        existing.major_open_count = result.major_open_count
        existing.minor_open_count = result.minor_open_count
        existing.admin_open_count = result.admin_open_count
        existing.avg_capa_age_days = result.avg_capa_age_days
        existing.data_query_rate_pct = result.data_query_rate_pct
        existing.enrollment_deviation_pct = result.enrollment_deviation_pct
    else:
        db.add(SiteRiskScore(
            site_id=result.site_id,
            score_date=today,
            total_score=result.total_score,
            risk_tier=result.risk_tier,
            major_open_count=result.major_open_count,
            minor_open_count=result.minor_open_count,
            admin_open_count=result.admin_open_count,
            avg_capa_age_days=result.avg_capa_age_days,
            data_query_rate_pct=result.data_query_rate_pct,
            enrollment_deviation_pct=result.enrollment_deviation_pct,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# Data loading helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_patient_data(db: Session, patient: Patient) -> dict:
    """
    Load all visits, lab results, and adverse events for a patient
    into plain dicts suitable for the pure engine functions.
    """
    visits_orm = db.execute(
        select(Visit)
        .where(Visit.patient_id == patient.id)
        .order_by(Visit.visit_number)
    ).scalars().all()

    visits = [
        {
            "id": v.id,
            "visit_number": v.visit_number,
            "visit_name": v.visit_name,
            "scheduled_date": v.scheduled_date,
            "actual_date": v.actual_date,
            "window_deviation_days": v.window_deviation_days,
            "completed_assessments_json": v.completed_assessments,
        }
        for v in visits_orm
    ]

    labs_orm = db.execute(
        select(LabResult).where(LabResult.patient_id == patient.id)
    ).scalars().all()

    lab_results = [
        {
            "visit_id": lr.visit_id,
            "test_name": lr.test_name,
            "value": lr.value,
            "collection_date": lr.collection_date,
        }
        for lr in labs_orm
    ]

    aes_orm = db.execute(
        select(AdverseEvent).where(AdverseEvent.patient_id == patient.id)
    ).scalars().all()

    adverse_events = [
        {
            "id": ae.id,
            "description": ae.description,
            "onset_date": ae.onset_date,
            "reported_date": ae.reported_date,
            "reporting_delay_hours": ae.reporting_delay_hours,
            "sae_flag": ae.sae_flag,
        }
        for ae in aes_orm
    ]

    return {
        "visits": visits,
        "lab_results": lab_results,
        "adverse_events": adverse_events,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Top-level analysis runner
# ─────────────────────────────────────────────────────────────────────────────

def run_full_analysis(
    protocol: Protocol | None = None,
    today: date | None = None,
    db: Session | None = None,
) -> dict:
    """
    Run the deviation engine and risk scorer against all data in the database.

    Parameters
    ----------
    protocol : Protocol, optional
        Explicit protocol instance.  Defaults to the cached protocol.
    today : date, optional
        Reference date for CAPA age and score_date.  Defaults to today.
    db : Session, optional
        SQLAlchemy session to use.  If None, a new session is created and
        closed at the end of the function.

    Returns
    -------
    dict
        Summary containing total_deviations_created, counts_by_severity,
        site_risk_scores.
    """
    proto = protocol or get_protocol()
    # Use a consistent reference date matching the seed data timeline (SEED_DATE)
    # to avoid artificially inflated CAPA age scores. This ensures the demo
    # risk scores are deterministic and reproducible regardless of when analysis runs.
    ref_date = today or date(2023, 5, 1)

    close_db = db is None
    if close_db:
        db = SessionLocal()

    try:
        # ── Step 1: Run deviation engine for every patient ────────────────────
        patients = db.execute(select(Patient)).scalars().all()

        total_created = 0
        for patient in patients:
            data = _load_patient_data(db, patient)
            existing_open = _existing_open_deviations(db, patient.id)

            results = evaluate_patient(
                patient_id=patient.id,
                site_id=patient.site_id,
                enrollment_date=patient.enrollment_date,
                age=patient.age,
                ecog_score=patient.ecog_score,
                diagnosis_confirmed=patient.diagnosis_confirmed,
                prior_egfr_alk_treatment_days=patient.prior_egfr_alk_treatment_days,
                active_infection=patient.active_infection,
                pregnant_or_breastfeeding=patient.pregnant_or_breastfeeding,
                consent_signed_before_procedure=patient.consent_signed_before_procedure,
                visits=data["visits"],
                lab_results=data["lab_results"],
                adverse_events=data["adverse_events"],
                protocol=proto,
            )

            created = _persist_deviations(db, results, ref_date, existing_open)
            total_created += created
            if created:
                logger.debug("Patient %s: %d new deviations", patient.id, created)

        db.commit()
        logger.info("Deviation engine complete: %d new deviations created", total_created)

        # ── Step 2: Score every site ──────────────────────────────────────────
        sites = db.execute(select(Site)).scalars().all()
        site_results: list[SiteRiskResult] = []

        for site in sites:
            inputs = _build_site_inputs(db, site, ref_date)
            result = score_site(inputs)
            _upsert_risk_score(db, result, ref_date)
            site_results.append(result)
            logger.debug(
                "Site %s: score=%.1f tier=%s",
                site.id, result.total_score, result.risk_tier.value,
            )

        db.commit()
        logger.info("Risk scoring complete: %d sites scored", len(site_results))

        # ── Step 3: Build summary ────────────────────────────────────────────
        from sqlalchemy import func

        severity_counts = {}
        for sev in DeviationSeverity:
            count = db.execute(
                select(func.count())
                .select_from(Deviation)
                .where(Deviation.status == DeviationStatus.OPEN)
                .where(Deviation.severity == sev)
            ).scalar() or 0
            severity_counts[sev.value] = count

        total_open = sum(severity_counts.values())

        return {
            "total_new_deviations_created": total_created,
            "total_open_deviations": total_open,
            "counts_by_severity": severity_counts,
            "site_risk_scores": [
                {
                    "site_id": r.site_id,
                    "total_score": r.total_score,
                    "risk_tier": r.risk_tier.value,
                    "major_open": r.major_open_count,
                    "minor_open": r.minor_open_count,
                    "admin_open": r.admin_open_count,
                }
                for r in sorted(site_results, key=lambda x: x.total_score, reverse=True)
            ],
        }

    except Exception:
        db.rollback()
        raise
    finally:
        if close_db:
            db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Single-patient analysis (used by POST /api/patients/{id}/analyse)
# ─────────────────────────────────────────────────────────────────────────────

def run_patient_analysis(db: Session, patient_id: str) -> int:
    """
    Run deviation detection for a single patient and persist new deviations.

    Returns the number of new Deviation rows created.
    """
    proto = get_protocol()
    # Use a consistent reference date matching the seed data timeline (SEED_DATE)
    # to avoid artificially inflated CAPA age scores. This ensures the demo
    # risk scores are deterministic and reproducible regardless of when analysis runs.
    ref_date = date(2023, 5, 1)

    patient = db.execute(
        select(Patient).where(Patient.id == patient_id)
    ).scalar_one_or_none()

    if patient is None:
        raise ValueError(f"Patient {patient_id} not found")

    data = _load_patient_data(db, patient)
    existing_open = _existing_open_deviations(db, patient_id)

    results = evaluate_patient(
        patient_id=patient.id,
        site_id=patient.site_id,
        enrollment_date=patient.enrollment_date,
        age=patient.age,
        ecog_score=patient.ecog_score,
        diagnosis_confirmed=patient.diagnosis_confirmed,
        prior_egfr_alk_treatment_days=patient.prior_egfr_alk_treatment_days,
        active_infection=patient.active_infection,
        pregnant_or_breastfeeding=patient.pregnant_or_breastfeeding,
        consent_signed_before_procedure=patient.consent_signed_before_procedure,
        visits=data["visits"],
        lab_results=data["lab_results"],
        adverse_events=data["adverse_events"],
        protocol=proto,
    )

    created = _persist_deviations(db, results, ref_date, existing_open)
    db.commit()
    return created
