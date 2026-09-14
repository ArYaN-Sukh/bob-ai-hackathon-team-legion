"""Initialize a persistent TrialGuard database exactly once.

Run this deliberately with DATABASE_URL set to the managed PostgreSQL URL:
    python -m src.backend.scripts.initialize_production
"""
from __future__ import annotations

from sqlalchemy import func, select

from src.backend.db import SessionLocal
from src.backend.models import AdverseEvent, ClinicalTrial, LabResult, Patient, Site, Visit
from src.backend.seed.seed import seed_if_empty
from src.backend.services.analysis_service import run_full_analysis


def main() -> None:
    seeded = seed_if_empty()
    if seeded:
        summary = run_full_analysis()
        print(f"Analysis completed: {summary['total_open_deviations']} open deviations.")
    else:
        print("Analysis skipped because the persistent dataset already exists.")

    db = SessionLocal()
    try:
        counts = {
            "trials": db.scalar(select(func.count()).select_from(ClinicalTrial)),
            "sites": db.scalar(select(func.count()).select_from(Site)),
            "patients": db.scalar(select(func.count()).select_from(Patient)),
            "visits": db.scalar(select(func.count()).select_from(Visit)),
            "lab_results": db.scalar(select(func.count()).select_from(LabResult)),
            "adverse_events": db.scalar(select(func.count()).select_from(AdverseEvent)),
        }
    finally:
        db.close()

    expected = {
        "trials": 1, "sites": 6, "patients": 60, "visits": 240,
        "lab_results": 1200, "adverse_events": 125,
    }
    print(f"Database counts: {counts}")
    if counts != expected:
        raise SystemExit(f"Unexpected TrialGuard demo data counts: {counts}")


if __name__ == "__main__":
    main()
