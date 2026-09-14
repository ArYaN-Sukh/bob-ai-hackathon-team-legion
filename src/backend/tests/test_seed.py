"""
Tests for the synthetic data seed script.
Verifies correctness, determinism, and the specific demo story requirements.
"""
from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.backend.db import _make_engine, init_db as _init_db
from src.backend.models import (
    AdverseEvent,
    ClinicalTrial,
    LabResult,
    Patient,
    Site,
    Visit,
)
from src.backend.seed.synthetic_data import generate_all


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def seeded_db():
    """
    Create a temporary database, run the seed, and return a session.
    Scoped to module so seeding happens only once per test run.
    """
    import src.backend.db as db_module

    # Use a temp file (not :memory:) because seed.py checks paths
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_seed.db"
        test_url = f"sqlite:///{db_path}"

        # Swap the global engine
        original_engine = db_module.engine
        original_session = db_module.SessionLocal

        test_engine = _make_engine(test_url)
        from sqlalchemy.orm import sessionmaker
        TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

        db_module.engine = test_engine
        db_module.SessionLocal = TestSessionLocal

        # Also patch settings so seed.py resolves correct path
        import src.backend.config as cfg_module
        original_db_path = cfg_module.settings.database_path
        cfg_module.settings.database_path = str(db_path)

        try:
            _init_db(drop_existing=True)

            # Run seed logic inline (not subprocess) for test isolation
            from src.backend.seed.seed import seed
            seed()

            session = TestSessionLocal()
            yield session
            session.close()
        finally:
            db_module.engine = original_engine
            db_module.SessionLocal = original_session
            cfg_module.settings.database_path = original_db_path
            test_engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Generator tests (no DB required)
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntheticDataGenerator:
    def test_generate_all_returns_expected_keys(self):
        data = generate_all()
        assert set(data.keys()) == {"trial", "sites", "patients", "visits", "lab_results", "adverse_events"}

    def test_generates_one_trial(self):
        data = generate_all()
        assert data["trial"]["id"] == "TRIAL-TG-001"

    def test_generates_six_sites(self):
        data = generate_all()
        assert len(data["sites"]) == 6

    def test_site_003_exists(self):
        data = generate_all()
        site_ids = [s["id"] for s in data["sites"]]
        assert "SITE-003" in site_ids

    def test_site_005_exists(self):
        data = generate_all()
        site_ids = [s["id"] for s in data["sites"]]
        assert "SITE-005" in site_ids

    def test_generates_sixty_patients(self):
        data = generate_all()
        assert len(data["patients"]) == 60

    def test_pt_0042_exists(self):
        data = generate_all()
        pt_ids = [p["id"] for p in data["patients"]]
        assert "PT-0042" in pt_ids

    def test_pt_0042_age_is_76(self):
        """Core demo scenario requirement: PT-0042 must be age 76 (violates INC-01)."""
        data = generate_all()
        pt42 = next(p for p in data["patients"] if p["id"] == "PT-0042")
        assert pt42["age"] == 76, f"PT-0042 must be age 76, got {pt42['age']}"

    def test_pt_0042_at_site_003(self):
        data = generate_all()
        pt42 = next(p for p in data["patients"] if p["id"] == "PT-0042")
        assert pt42["site_id"] == "SITE-003"

    def test_generates_240_visits(self):
        """60 patients × 4 visits = 240 visits."""
        data = generate_all()
        assert len(data["visits"]) == 240

    def test_generates_lab_results(self):
        """5 lab tests × 240 visits = 1200 lab results."""
        data = generate_all()
        assert len(data["lab_results"]) == 1200

    def test_generates_adverse_events(self):
        data = generate_all()
        assert len(data["adverse_events"]) > 0

    def test_sae_records_exist(self):
        data = generate_all()
        saes = [ae for ae in data["adverse_events"] if ae["sae_flag"]]
        assert len(saes) >= 5, f"Expected >= 5 SAEs, got {len(saes)}"

    def test_pt_0042_has_sae(self):
        data = generate_all()
        pt42_saes = [ae for ae in data["adverse_events"]
                     if ae["patient_id"] == "PT-0042" and ae["sae_flag"]]
        assert len(pt42_saes) >= 1, "PT-0042 must have at least 1 SAE"

    def test_pt_0042_sae_is_delayed(self):
        """PT-0042's SAE must have a reporting delay > 24h (violates REP-01)."""
        data = generate_all()
        pt42_saes = [ae for ae in data["adverse_events"]
                     if ae["patient_id"] == "PT-0042" and ae["sae_flag"]]
        assert any(ae["reporting_delay_hours"] > 24 for ae in pt42_saes), \
            "PT-0042 must have at least 1 SAE with reporting_delay_hours > 24"

    def test_generator_is_deterministic(self):
        """Running generate_all() twice must produce identical patient data."""
        data1 = generate_all()
        data2 = generate_all()
        # Compare patient IDs and ages
        patients1 = {p["id"]: p["age"] for p in data1["patients"]}
        patients2 = {p["id"]: p["age"] for p in data2["patients"]}
        assert patients1 == patients2, "generate_all() must be deterministic"

    def test_no_internal_keys_in_sites(self):
        """_profile key must be stripped before returning."""
        data = generate_all()
        for site in data["sites"]:
            assert "_profile" not in site

    def test_no_internal_keys_in_patients(self):
        """_site_profile key must be stripped before returning."""
        data = generate_all()
        for patient in data["patients"]:
            assert "_site_profile" not in patient

    def test_pt_0042_visit_3_is_late(self):
        """PT-0042 Visit 3 should have a window deviation > 5 days (outside ±2 day window)."""
        data = generate_all()
        pt42_v3 = next(
            v for v in data["visits"]
            if v["patient_id"] == "PT-0042" and v["visit_number"] == 3
        )
        # The problematic profile sets Visit 3 offset to 8 days
        assert pt42_v3["window_deviation_days"] > 5, \
            f"PT-0042 Visit 3 should be > 5 days late, got {pt42_v3['window_deviation_days']}"

    def test_pt_0042_visit_4_missing_tumor_assessment(self):
        """PT-0042 Visit 4 must be missing tumor_assessment (primary endpoint deviation)."""
        import json
        data = generate_all()
        pt42_v4 = next(
            v for v in data["visits"]
            if v["patient_id"] == "PT-0042" and v["visit_number"] == 4
        )
        # Note: generate_all strips _id but keeps completed_assessments
        assessments = json.loads(pt42_v4["completed_assessments"])
        assert "tumor_assessment" not in assessments, \
            "PT-0042 Visit 4 must be missing tumor_assessment"


# ─────────────────────────────────────────────────────────────────────────────
# Seeded database tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSeededDatabase:
    def test_one_trial_in_db(self, seeded_db: Session):
        count = seeded_db.execute(select(func.count()).select_from(ClinicalTrial)).scalar()
        assert count == 1

    def test_six_sites_in_db(self, seeded_db: Session):
        count = seeded_db.execute(select(func.count()).select_from(Site)).scalar()
        assert count == 6

    def test_sixty_patients_in_db(self, seeded_db: Session):
        count = seeded_db.execute(select(func.count()).select_from(Patient)).scalar()
        assert count == 60

    def test_240_visits_in_db(self, seeded_db: Session):
        count = seeded_db.execute(select(func.count()).select_from(Visit)).scalar()
        assert count == 240

    def test_lab_results_in_db(self, seeded_db: Session):
        count = seeded_db.execute(select(func.count()).select_from(LabResult)).scalar()
        assert count == 1200

    def test_adverse_events_in_db(self, seeded_db: Session):
        count = seeded_db.execute(select(func.count()).select_from(AdverseEvent)).scalar()
        assert count > 0

    def test_pt_0042_in_db(self, seeded_db: Session):
        pt = seeded_db.get(Patient, "PT-0042")
        assert pt is not None, "PT-0042 must exist in the database"

    def test_pt_0042_age_76_in_db(self, seeded_db: Session):
        pt = seeded_db.get(Patient, "PT-0042")
        assert pt.age == 76

    def test_pt_0042_at_site_003_in_db(self, seeded_db: Session):
        pt = seeded_db.get(Patient, "PT-0042")
        assert pt.site_id == "SITE-003"

    def test_site_003_in_db(self, seeded_db: Session):
        site = seeded_db.get(Site, "SITE-003")
        assert site is not None
        assert "London" in site.city

    def test_site_005_in_db(self, seeded_db: Session):
        site = seeded_db.get(Site, "SITE-005")
        assert site is not None
        assert "Munich" in site.city

    def test_drop_existing_clears_data(self, tmp_path):
        """Verifies that init_db(drop_existing=True) clears all data.

        This tests the key mechanism that makes seed() idempotent: calling
        init_db(drop_existing=True) drops all tables before recreating them,
        so any subsequent insert starts from a clean state.
        """
        import src.backend.db as db_module
        from sqlalchemy.orm import sessionmaker
        from src.backend.db import init_db
        from src.backend.models import ClinicalTrial

        db_path = tmp_path / "drop_test.db"
        test_url = f"sqlite:///{db_path}"
        test_engine = _make_engine(test_url)
        TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

        original_engine = db_module.engine
        original_session = db_module.SessionLocal

        try:
            db_module.engine = test_engine
            db_module.SessionLocal = TestSession

            # Create schema and insert one row
            init_db(drop_existing=False)
            session = TestSession()
            session.add(ClinicalTrial(
                id="T-DROP-TEST",
                name="Drop Test (Synthetic)",
                protocol_version="1.0",
                sponsor="Test",
                phase="I",
                indication="Test",
                start_date=date(2023, 1, 1),
                target_enrollment=1,
            ))
            session.commit()

            count_before = session.execute(
                select(func.count()).select_from(ClinicalTrial)
            ).scalar()
            session.close()

            # Now drop and recreate — data should be gone
            init_db(drop_existing=True)

            session2 = TestSession()
            count_after = session2.execute(
                select(func.count()).select_from(ClinicalTrial)
            ).scalar()
            session2.close()

        finally:
            db_module.engine = original_engine
            db_module.SessionLocal = original_session
            test_engine.dispose()

        assert count_before == 1
        assert count_after == 0, "drop_existing=True must clear all data"
