"""
Tests for ORM model creation and relationships.
Uses an in-memory SQLite database so no side effects on real data.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import inspect

from src.backend.db import _make_engine, Base
from src.backend.models import (
    CAPA,
    AdverseEvent,
    CAPAStatus,
    ClinicalTrial,
    Deviation,
    DeviationSeverity,
    DeviationStatus,
    LabResult,
    Patient,
    PatientStatus,
    RiskTier,
    Site,
    SiteRiskScore,
    SiteStatus,
    Visit,
    VisitType,
)
from sqlalchemy.orm import Session


@pytest.fixture(scope="module")
def engine():
    eng = _make_engine("sqlite:///:memory:")
    import src.backend.db as db_module
    original = db_module.engine
    db_module.engine = eng

    from src.backend.db import init_db
    init_db(drop_existing=False)

    yield eng

    db_module.engine = original
    eng.dispose()


@pytest.fixture()
def db(engine):
    session = Session(engine)
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def sample_trial(db):
    t = ClinicalTrial(
        id="TRIAL-TEST-001",
        name="Test Trial (Synthetic)",
        protocol_version="1.0",
        sponsor="Test Sponsor",
        phase="II",
        indication="Test Indication",
        start_date=date(2023, 1, 1),
        target_enrollment=10,
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture()
def sample_site(db, sample_trial):
    s = Site(
        id="SITE-TEST",
        trial_id=sample_trial.id,
        name="Test Site",
        country="USA",
        principal_investigator="Dr. Test",
        status=SiteStatus.ACTIVE,
        enrolled_count=0,
        target_enrollment=10,
    )
    db.add(s)
    db.flush()
    return s


@pytest.fixture()
def sample_patient(db, sample_site, sample_trial):
    p = Patient(
        id="PT-TEST-001",
        site_id=sample_site.id,
        trial_id=sample_trial.id,
        age=45,
        sex="F",
        ecog_score=1,
        diagnosis_confirmed=True,
        active_infection=False,
        pregnant_or_breastfeeding=False,
        consent_signed_before_procedure=True,
        enrollment_date=date(2023, 2, 1),
        status=PatientStatus.ENROLLED,
    )
    db.add(p)
    db.flush()
    return p


class TestTableNames:
    def test_all_nine_tables_exist(self, engine):
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "clinical_trials", "sites", "patients", "visits",
            "lab_results", "adverse_events", "deviations", "capas", "site_risk_scores",
        }
        assert expected.issubset(tables)


class TestClinicalTrialModel:
    def test_create_and_retrieve(self, db):
        t = ClinicalTrial(
            id="TRIAL-MODEL-TEST",
            name="Model Test Trial (Synthetic)",
            protocol_version="1.0",
            sponsor="Synthetic Sponsor",
            phase="II",
            indication="Test Indication",
            start_date=date(2023, 1, 1),
            target_enrollment=50,
        )
        db.add(t)
        db.flush()
        retrieved = db.get(ClinicalTrial, "TRIAL-MODEL-TEST")
        assert retrieved is not None
        assert retrieved.name == "Model Test Trial (Synthetic)"
        assert retrieved.target_enrollment == 50


class TestSiteModel:
    def test_create_with_foreign_key(self, db, sample_trial):
        s = Site(
            id="SITE-MODEL-TEST",
            trial_id=sample_trial.id,
            name="Model Test Site",
            country="UK",
            principal_investigator="Dr. Model",
            status=SiteStatus.ACTIVE,
            enrolled_count=5,
            target_enrollment=20,
        )
        db.add(s)
        db.flush()
        retrieved = db.get(Site, "SITE-MODEL-TEST")
        assert retrieved.country == "UK"
        assert retrieved.status == SiteStatus.ACTIVE


class TestPatientModel:
    def test_create_patient(self, db, sample_patient):
        retrieved = db.get(Patient, "PT-TEST-001")
        assert retrieved is not None
        assert retrieved.age == 45
        assert retrieved.status == PatientStatus.ENROLLED

    def test_patient_age_76_for_demo_scenario(self, db, sample_site, sample_trial):
        """Verify that a patient with age 76 can be stored (for PT-0042 demo scenario)."""
        p = Patient(
            id="PT-AGE-TEST",
            site_id=sample_site.id,
            trial_id=sample_trial.id,
            age=76,
            sex="M",
            ecog_score=1,
            diagnosis_confirmed=True,
            active_infection=False,
            pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True,
            enrollment_date=date(2023, 3, 1),
            status=PatientStatus.ENROLLED,
        )
        db.add(p)
        db.flush()
        retrieved = db.get(Patient, "PT-AGE-TEST")
        assert retrieved.age == 76


class TestVisitModel:
    def test_create_visit(self, db, sample_patient):
        v = Visit(
            patient_id=sample_patient.id,
            site_id=sample_patient.site_id,
            visit_number=1,
            visit_name="Screening",
            visit_type=VisitType.SCHEDULED,
            scheduled_date=date(2023, 2, 1),
            actual_date=date(2023, 2, 2),
            window_deviation_days=1,
        )
        db.add(v)
        db.flush()
        assert v.id is not None
        assert v.window_deviation_days == 1


class TestLabResultModel:
    def test_create_lab_result(self, db, sample_patient):
        visit = Visit(
            patient_id=sample_patient.id,
            site_id=sample_patient.site_id,
            visit_number=2,
            visit_name="Baseline",
            visit_type=VisitType.SCHEDULED,
            scheduled_date=date(2023, 2, 15),
            actual_date=date(2023, 2, 15),
            window_deviation_days=0,
        )
        db.add(visit)
        db.flush()

        lr = LabResult(
            patient_id=sample_patient.id,
            visit_id=visit.id,
            test_name="hemoglobin",
            display_name="Hemoglobin",
            value=7.5,
            unit="g/dL",
            reference_low=8.0,
            reference_high=None,
            collection_date=date(2023, 2, 15),
            is_out_of_range=True,
        )
        db.add(lr)
        db.flush()
        assert lr.id is not None
        assert lr.is_out_of_range is True


class TestAdverseEventModel:
    def test_create_sae(self, db, sample_patient):
        ae = AdverseEvent(
            patient_id=sample_patient.id,
            site_id=sample_patient.site_id,
            description="Febrile neutropenia — Grade 3 (Synthetic)",
            onset_date=date(2023, 3, 10),
            sae_flag=True,
            expected_flag=False,
            reported_date=date(2023, 3, 12),
            reporting_delay_hours=48.0,
            severity_grade=3,
            outcome="Resolved",
        )
        db.add(ae)
        db.flush()
        assert ae.id is not None
        assert ae.sae_flag is True
        assert ae.reporting_delay_hours == 48.0


class TestDeviationModel:
    def test_create_deviation(self, db, sample_patient):
        dev = Deviation(
            patient_id=sample_patient.id,
            site_id=sample_patient.site_id,
            rule_id="INC-01",
            deviation_type="Eligibility",
            description="Patient age 76 violates INC-01 (requires 18–75)",
            severity=DeviationSeverity.MAJOR,
            status=DeviationStatus.OPEN,
            detected_date=date(2023, 2, 1),
        )
        db.add(dev)
        db.flush()
        assert dev.id is not None
        assert dev.severity == DeviationSeverity.MAJOR

    def test_severity_enum_values(self):
        assert DeviationSeverity.MAJOR.value == "Major"
        assert DeviationSeverity.MINOR.value == "Minor"
        assert DeviationSeverity.ADMINISTRATIVE.value == "Administrative"


class TestCAPAModel:
    def test_create_capa(self, db, sample_patient):
        dev = Deviation(
            patient_id=sample_patient.id,
            site_id=sample_patient.site_id,
            rule_id="REP-01",
            deviation_type="SAE Reporting",
            description="SAE reported 48h after onset (REP-01 requires ≤24h)",
            severity=DeviationSeverity.MAJOR,
            status=DeviationStatus.OPEN,
            detected_date=date(2023, 3, 12),
        )
        db.add(dev)
        db.flush()

        capa = CAPA(
            deviation_id=dev.id,
            site_id=sample_patient.site_id,
            status=CAPAStatus.OPEN,
            root_cause="Staff not aware of SAE reporting timeline",
            corrective_action="Immediate PI notification and training",
            preventive_action="Add SAE reporting reminder to SOP checklist",
            due_date=date(2023, 4, 12),
        )
        db.add(capa)
        db.flush()
        assert capa.id is not None
        assert capa.watsonx_narrative is None  # Not generated until Phase 4


class TestSiteRiskScoreModel:
    def test_create_risk_score(self, db, sample_site):
        rs = SiteRiskScore(
            site_id=sample_site.id,
            score_date=date(2024, 3, 1),
            major_open_count=3,
            minor_open_count=2,
            admin_open_count=1,
            avg_capa_age_days=47.0,
            data_query_rate_pct=15.0,
            enrollment_deviation_pct=5.0,
            total_score=74.0,
            risk_tier=RiskTier.HIGH,
        )
        db.add(rs)
        db.flush()
        assert rs.id is not None
        assert rs.risk_tier == RiskTier.HIGH

    def test_risk_tier_enum_values(self):
        assert RiskTier.HIGH.value == "High"
        assert RiskTier.MEDIUM.value == "Medium"
        assert RiskTier.LOW.value == "Low"
