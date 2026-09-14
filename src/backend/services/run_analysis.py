"""
Quick analysis runner — executes run_full_analysis() against the seeded DB
and prints a detailed report.  Run from repo root:

    python -m src.backend.services.run_analysis
"""
from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[4]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import logging
logging.basicConfig(level=logging.WARNING)

from src.backend.services.analysis_service import run_full_analysis
from src.backend.db import SessionLocal
from src.backend.models import Deviation, Patient, DeviationStatus
from sqlalchemy import select

def main():
    print("=" * 60)
    print("TrialGuard -- Running Full Analysis")
    print("=" * 60)

    summary = run_full_analysis()

    print(f"\nNew deviations created  : {summary['total_new_deviations_created']}")
    print(f"Total open deviations   : {summary['total_open_deviations']}")
    print("\nCounts by severity:")
    for sev, count in summary["counts_by_severity"].items():
        print(f"  {sev:<20} {count}")

    print("\nSite risk scores (highest first):")
    print(f"  {'Site':<12} {'Score':>8}  {'Tier':<10}  Major  Minor  Admin")
    print(f"  {'-'*12}  {'-'*8}  {'-'*10}  {'-'*5}  {'-'*5}  {'-'*5}")
    for sr in summary["site_risk_scores"]:
        print(
            f"  {sr['site_id']:<12}  {sr['total_score']:>7.1f}  "
            f"{sr['risk_tier']:<10}  {sr['major_open']:>5}  "
            f"{sr['minor_open']:>5}  {sr['admin_open']:>5}"
        )

    # PT-0042 detailed deviations
    print("\nPT-0042 deviations:")
    db = SessionLocal()
    try:
        devs = db.execute(
            select(Deviation)
            .where(Deviation.patient_id == "PT-0042")
            .where(Deviation.status == DeviationStatus.OPEN)
            .order_by(Deviation.detected_date)
        ).scalars().all()

        if not devs:
            print("  (none)")
        for d in devs:
            print(f"  [{d.severity.value:<14}] {d.rule_id:<32} {d.deviation_type}")
            print(f"           {d.description[:100]}")
    finally:
        db.close()

    # Duplicate check
    db2 = SessionLocal()
    try:
        from sqlalchemy import func
        dup_check = db2.execute(
            select(
                Deviation.patient_id,
                Deviation.rule_id,
                Deviation.visit_id,
                func.count().label("cnt")
            )
            .where(Deviation.status == DeviationStatus.OPEN)
            .group_by(Deviation.patient_id, Deviation.rule_id, Deviation.visit_id)
            .having(func.count() > 1)
        ).all()

        print(f"\nDuplicate open deviations (patient_id, rule_id, visit_id): {len(dup_check)}")
        if dup_check:
            for row in dup_check:
                print(f"  DUPLICATE: {row.patient_id} / {row.rule_id} / {row.visit_id} x{row.cnt}")
        else:
            print("  None found -- deduplication working correctly.")
    finally:
        db2.close()

    print("\n" + "=" * 60)
    print("Analysis complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
