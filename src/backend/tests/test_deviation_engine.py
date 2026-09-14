"""
Tests for the deviation engine.

Covers each rule category, clean record → no false positive, PT-0042 known
violations, evidence structure, and deduplication.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.backend.engine.deviation_engine import (
    DeviationResult,
    _PRIMARY_ENDPOINT_SEVERITY,
    _VISIT_WINDOW_RULE_ID,
    evaluate_eligibility,
    evaluate_inc04_anc,
    evaluate_lab_result,
    evaluate_missing_assessments,
    evaluate_patient,
    evaluate_sae_reporting,
    evaluate_visit_window,
)
from src.backend.engine.protocol_loader import Protocol, load_protocol, reset_protocol_cache
from src.backend.models import DeviationSeverity

PROTOCOL_PATH = Path("src/backend/data/protocol.json")


@pytest.fixture(scope="module")
def protocol() -> Protocol:
    reset_protocol_cache()
    return load_protocol(PROTOCOL_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

ENROLL = date(2023, 2, 1)
DAY0 = ENROLL  # Baseline / Day 1
SCREENING_DATE = DAY0 - timedelta(days=14)


def _clean_patient_kwargs(protocol):
    """Keyword arguments for a fully eligible, clean patient."""
    return dict(
        patient_id="PT-CLEAN",
        site_id="SITE-001",
        enrollment_date=ENROLL,
        age=50,
        ecog_score=1,
        diagnosis_confirmed=True,
        prior_egfr_alk_treatment_days=None,
        active_infection=False,
        pregnant_or_breastfeeding=False,
        consent_signed_before_procedure=True,
        visits=[
            {
                "id": 1, "visit_number": 1, "visit_name": "Screening",
                "scheduled_date": SCREENING_DATE, "actual_date": SCREENING_DATE,
                "window_deviation_days": 0,
                "completed_assessments_json": json.dumps([
                    "informed_consent", "medical_history", "demographics", "vitals",
                    "physical_exam", "ecog_score", "labs_hematology", "labs_chemistry",
                    "ecg", "pregnancy_test", "tumor_assessment",
                ]),
            },
            {
                "id": 2, "visit_number": 2, "visit_name": "Baseline / Day 1",
                "scheduled_date": DAY0, "actual_date": DAY0,
                "window_deviation_days": 0,
                "completed_assessments_json": json.dumps([
                    "vitals", "physical_exam", "ecog_score", "labs_hematology",
                    "labs_chemistry", "ecg", "dosing_cycle1_day1", "concomitant_medications",
                ]),
            },
            {
                "id": 3, "visit_number": 3, "visit_name": "Cycle 1 Day 15",
                "scheduled_date": DAY0 + timedelta(days=14),
                "actual_date": DAY0 + timedelta(days=14),
                "window_deviation_days": 0,
                "completed_assessments_json": json.dumps([
                    "vitals", "physical_exam", "labs_hematology", "labs_chemistry",
                    "adverse_event_review", "concomitant_medications",
                ]),
            },
            {
                "id": 4, "visit_number": 4, "visit_name": "Cycle 1 End / Efficacy Assessment",
                "scheduled_date": DAY0 + timedelta(days=28),
                "actual_date": DAY0 + timedelta(days=28),
                "window_deviation_days": 0,
                "completed_assessments_json": json.dumps([
                    "vitals", "physical_exam", "ecog_score", "labs_hematology",
                    "labs_chemistry", "ecg", "tumor_assessment", "adverse_event_review",
                    "concomitant_medications", "dosing_compliance_review",
                ]),
            },
        ],
        lab_results=[
            {"visit_id": 1, "test_name": "hemoglobin", "value": 13.5, "collection_date": SCREENING_DATE},
            {"visit_id": 1, "test_name": "anc", "value": 3.5, "collection_date": SCREENING_DATE},
            {"visit_id": 1, "test_name": "platelets", "value": 220.0, "collection_date": SCREENING_DATE},
            {"visit_id": 1, "test_name": "creatinine", "value": 0.9, "collection_date": SCREENING_DATE},
            {"visit_id": 1, "test_name": "alt", "value": 25.0, "collection_date": SCREENING_DATE},
        ],
        adverse_events=[],
        protocol=protocol,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Clean patient → no false positives
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanPatientNoFalsePositives:
    def test_no_deviations_for_clean_patient(self, protocol):
        results = evaluate_patient(**_clean_patient_kwargs(protocol))
        rule_ids = [r.rule_id for r in results]
        eligibility = [r for r in results if r.deviation_type.startswith("Eligibility")]
        assert not eligibility, f"Clean patient has eligibility deviations: {rule_ids}"

    def test_no_visit_window_deviations(self, protocol):
        results = evaluate_patient(**_clean_patient_kwargs(protocol))
        window_devs = [r for r in results if r.rule_id == _VISIT_WINDOW_RULE_ID]
        assert not window_devs

    def test_no_missing_assessments(self, protocol):
        results = evaluate_patient(**_clean_patient_kwargs(protocol))
        missing = [r for r in results if r.deviation_type == "Missing Assessment"]
        assert not missing


# ─────────────────────────────────────────────────────────────────────────────
# 1. Visit window evaluator
# ─────────────────────────────────────────────────────────────────────────────

class TestVisitWindowEvaluator:
    def test_no_deviation_when_on_time(self, protocol):
        sched = date(2023, 2, 15)
        results = evaluate_visit_window(
            "PT-001", "SITE-001", 10, 3, "Cycle 1 Day 15",
            sched, sched, protocol
        )
        assert results == []

    def test_no_deviation_at_window_boundary(self, protocol):
        sched = date(2023, 2, 15)
        # Visit 3 allows +2 days
        actual = sched + timedelta(days=2)
        results = evaluate_visit_window(
            "PT-001", "SITE-001", 10, 3, "Cycle 1 Day 15",
            sched, actual, protocol
        )
        assert results == []

    def test_deviation_outside_window(self, protocol):
        sched = date(2023, 2, 15)
        actual = sched + timedelta(days=8)  # PT-0042's visit 3 offset
        results = evaluate_visit_window(
            "PT-0042", "SITE-003", 10, 3, "Cycle 1 Day 15",
            sched, actual, protocol
        )
        assert len(results) == 1
        r = results[0]
        assert r.rule_id == _VISIT_WINDOW_RULE_ID
        assert r.severity == DeviationSeverity.MINOR
        assert "late" in r.description.lower()

    def test_evidence_contains_deviation_days(self, protocol):
        sched = date(2023, 2, 15)
        actual = sched + timedelta(days=8)
        results = evaluate_visit_window(
            "PT-0042", "SITE-003", 10, 3, "Cycle 1 Day 15",
            sched, actual, protocol
        )
        assert results[0].evidence["deviation_days"] == 8

    def test_no_actual_date_returns_empty(self, protocol):
        results = evaluate_visit_window(
            "PT-001", "SITE-001", 10, 2, "Baseline",
            date(2023, 2, 1), None, protocol
        )
        assert results == []

    def test_early_visit_detected(self, protocol):
        sched = date(2023, 2, 15)
        # Visit 3 allows -2 days before; -3 should trigger
        actual = sched - timedelta(days=3)
        results = evaluate_visit_window(
            "PT-001", "SITE-001", 10, 3, "Cycle 1 Day 15",
            sched, actual, protocol
        )
        assert len(results) == 1
        assert "early" in results[0].description.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Missing assessment evaluator
# ─────────────────────────────────────────────────────────────────────────────

class TestMissingAssessmentEvaluator:
    def test_no_deviation_all_present(self, protocol):
        all_req = ["vitals", "physical_exam", "labs_hematology", "labs_chemistry",
                   "adverse_event_review", "concomitant_medications"]
        results = evaluate_missing_assessments(
            "PT-001", "SITE-001", 10, 3, "Cycle 1 Day 15",
            date(2023, 3, 1), json.dumps(all_req), protocol
        )
        assert results == []

    def test_detects_missing_assessment(self, protocol):
        completed = ["vitals", "physical_exam", "labs_hematology", "labs_chemistry",
                     "concomitant_medications"]  # missing adverse_event_review
        results = evaluate_missing_assessments(
            "PT-001", "SITE-001", 10, 3, "Cycle 1 Day 15",
            date(2023, 3, 1), json.dumps(completed), protocol
        )
        assert len(results) == 1
        assert "adverse_event_review" in results[0].description.lower()

    def test_primary_endpoint_missing_is_major(self, protocol):
        """PT-0042 Visit 4: missing tumor_assessment → Major."""
        completed = ["vitals", "physical_exam", "ecog_score", "labs_hematology",
                     "labs_chemistry", "ecg", "adverse_event_review",
                     "concomitant_medications", "dosing_compliance_review"]
        # tumor_assessment is intentionally absent
        results = evaluate_missing_assessments(
            "PT-0042", "SITE-003", 20, 4, "Cycle 1 End / Efficacy Assessment",
            date(2023, 4, 1), json.dumps(completed), protocol
        )
        tumor_devs = [r for r in results if "tumor_assessment" in r.evidence.get("missing_assessment", "")]
        assert tumor_devs, "Should detect missing tumor_assessment"
        assert tumor_devs[0].severity == _PRIMARY_ENDPOINT_SEVERITY
        assert tumor_devs[0].severity == DeviationSeverity.MAJOR

    def test_primary_endpoint_missing_description_mentions_primary(self, protocol):
        completed = ["vitals", "physical_exam"]
        results = evaluate_missing_assessments(
            "PT-0042", "SITE-003", 20, 4, "Cycle 1 End",
            date(2023, 4, 1), json.dumps(completed), protocol
        )
        tumor_devs = [r for r in results if "tumor_assessment" in r.evidence.get("missing_assessment", "")]
        assert any("primary endpoint" in r.description.lower() for r in tumor_devs)

    def test_no_actual_date_returns_empty(self, protocol):
        results = evaluate_missing_assessments(
            "PT-001", "SITE-001", 10, 1, "Screening",
            None, json.dumps(["vitals"]), protocol
        )
        assert results == []

    def test_evidence_contains_required_assessments(self, protocol):
        completed = ["vitals"]
        results = evaluate_missing_assessments(
            "PT-001", "SITE-001", 10, 1, "Screening",
            date(2023, 2, 1), json.dumps(completed), protocol
        )
        assert results
        assert "required_assessments" in results[0].evidence


# ─────────────────────────────────────────────────────────────────────────────
# 3. Lab threshold evaluator
# ─────────────────────────────────────────────────────────────────────────────

class TestLabThresholdEvaluator:
    def test_no_deviation_normal_lab(self, protocol):
        results = evaluate_lab_result(
            "PT-001", "SITE-001", 1, "hemoglobin", 13.5, date(2023, 2, 1), protocol
        )
        assert results == []

    def test_low_hemoglobin_detected(self, protocol):
        results = evaluate_lab_result(
            "PT-001", "SITE-001", 1, "hemoglobin", 6.0, date(2023, 2, 1), protocol
        )
        assert len(results) == 1
        assert results[0].rule_id == "LAB-01"
        assert results[0].severity == DeviationSeverity.MAJOR

    def test_high_creatinine_detected(self, protocol):
        results = evaluate_lab_result(
            "PT-001", "SITE-001", 1, "creatinine", 2.0, date(2023, 2, 1), protocol
        )
        assert len(results) == 1
        assert results[0].rule_id == "LAB-03"
        assert results[0].severity == DeviationSeverity.MINOR

    def test_evidence_has_threshold_info(self, protocol):
        results = evaluate_lab_result(
            "PT-001", "SITE-001", 1, "hemoglobin", 6.0, date(2023, 2, 1), protocol
        )
        ev = results[0].evidence
        assert ev["value"] == 6.0
        assert ev["min_threshold"] == 8.0

    def test_unknown_lab_test_returns_empty(self, protocol):
        """Tests not in the protocol threshold list produce no deviations."""
        results = evaluate_lab_result(
            "PT-001", "SITE-001", 1, "fibrinogen", 3.0, date(2023, 2, 1), protocol
        )
        assert results == []

    def test_normal_alt_no_deviation(self, protocol):
        results = evaluate_lab_result(
            "PT-001", "SITE-001", 1, "alt", 30.0, date(2023, 2, 1), protocol
        )
        assert results == []

    def test_high_alt_is_minor(self, protocol):
        results = evaluate_lab_result(
            "PT-001", "SITE-001", 1, "alt", 100.0, date(2023, 2, 1), protocol
        )
        assert results and results[0].severity == DeviationSeverity.MINOR

    def test_low_platelets_is_major(self, protocol):
        results = evaluate_lab_result(
            "PT-001", "SITE-001", 1, "platelets", 50.0, date(2023, 2, 1), protocol
        )
        assert results and results[0].severity == DeviationSeverity.MAJOR


# ─────────────────────────────────────────────────────────────────────────────
# 4. Eligibility evaluator
# ─────────────────────────────────────────────────────────────────────────────

class TestEligibilityEvaluator:
    def test_clean_patient_no_violations(self, protocol):
        results = evaluate_eligibility(
            patient_id="PT-CLEAN", site_id="SITE-001",
            enrollment_date=ENROLL, age=50, ecog_score=1,
            diagnosis_confirmed=True, prior_egfr_alk_treatment_days=None,
            active_infection=False, pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True, protocol=protocol,
        )
        assert results == []

    def test_pt0042_age76_violates_inc01(self, protocol):
        """The critical PT-0042 scenario: age 76 must produce a Major INC-01 violation."""
        results = evaluate_eligibility(
            patient_id="PT-0042", site_id="SITE-003",
            enrollment_date=ENROLL, age=76, ecog_score=1,
            diagnosis_confirmed=True, prior_egfr_alk_treatment_days=None,
            active_infection=False, pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True, protocol=protocol,
        )
        inc01 = [r for r in results if r.rule_id == "INC-01"]
        assert inc01, "PT-0042 age 76 must produce an INC-01 deviation"
        assert inc01[0].severity == DeviationSeverity.MAJOR
        assert inc01[0].patient_id == "PT-0042"

    def test_inc01_evidence_has_age(self, protocol):
        results = evaluate_eligibility(
            patient_id="PT-0042", site_id="SITE-003",
            enrollment_date=ENROLL, age=76, ecog_score=1,
            diagnosis_confirmed=True, prior_egfr_alk_treatment_days=None,
            active_infection=False, pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True, protocol=protocol,
        )
        inc01 = next(r for r in results if r.rule_id == "INC-01")
        assert inc01.evidence["patient_age"] == 76

    def test_age_18_boundary_no_violation(self, protocol):
        results = evaluate_eligibility(
            patient_id="PT-X", site_id="SITE-001",
            enrollment_date=ENROLL, age=18, ecog_score=1,
            diagnosis_confirmed=True, prior_egfr_alk_treatment_days=None,
            active_infection=False, pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True, protocol=protocol,
        )
        assert not [r for r in results if r.rule_id == "INC-01"]

    def test_age_75_boundary_no_violation(self, protocol):
        results = evaluate_eligibility(
            patient_id="PT-X", site_id="SITE-001",
            enrollment_date=ENROLL, age=75, ecog_score=1,
            diagnosis_confirmed=True, prior_egfr_alk_treatment_days=None,
            active_infection=False, pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True, protocol=protocol,
        )
        assert not [r for r in results if r.rule_id == "INC-01"]

    def test_age_17_violates_inc01(self, protocol):
        results = evaluate_eligibility(
            patient_id="PT-X", site_id="SITE-001",
            enrollment_date=ENROLL, age=17, ecog_score=1,
            diagnosis_confirmed=True, prior_egfr_alk_treatment_days=None,
            active_infection=False, pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True, protocol=protocol,
        )
        assert any(r.rule_id == "INC-01" for r in results)

    def test_ecog3_violates_inc02(self, protocol):
        results = evaluate_eligibility(
            patient_id="PT-004", site_id="SITE-004",
            enrollment_date=ENROLL, age=50, ecog_score=3,
            diagnosis_confirmed=True, prior_egfr_alk_treatment_days=None,
            active_infection=False, pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True, protocol=protocol,
        )
        inc02 = [r for r in results if r.rule_id == "INC-02"]
        assert inc02
        assert inc02[0].severity == DeviationSeverity.MAJOR

    def test_active_infection_violates_exc02(self, protocol):
        results = evaluate_eligibility(
            patient_id="PT-007", site_id="SITE-003",
            enrollment_date=ENROLL, age=50, ecog_score=1,
            diagnosis_confirmed=True, prior_egfr_alk_treatment_days=None,
            active_infection=True, pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True, protocol=protocol,
        )
        exc02 = [r for r in results if r.rule_id == "EXC-02"]
        assert exc02
        assert exc02[0].severity == DeviationSeverity.MAJOR

    def test_no_consent_violates_inc05(self, protocol):
        results = evaluate_eligibility(
            patient_id="PT-005", site_id="SITE-003",
            enrollment_date=ENROLL, age=50, ecog_score=1,
            diagnosis_confirmed=True, prior_egfr_alk_treatment_days=None,
            active_infection=False, pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=False, protocol=protocol,
        )
        inc05 = [r for r in results if r.rule_id == "INC-05"]
        assert inc05
        assert inc05[0].deviation_type == "Consent / Procedure Order"


# ─────────────────────────────────────────────────────────────────────────────
# 5. SAE reporting evaluator
# ─────────────────────────────────────────────────────────────────────────────

class TestSAEReportingEvaluator:
    def test_no_deviation_within_24h(self, protocol):
        results = evaluate_sae_reporting(
            patient_id="PT-001", site_id="SITE-001", ae_id=1,
            description="Febrile neutropenia",
            onset_date=date(2023, 3, 10),
            reported_date=date(2023, 3, 10),
            reporting_delay_hours=12.0,
            sae_flag=True, protocol=protocol,
        )
        assert results == []

    def test_no_deviation_for_non_sae(self, protocol):
        results = evaluate_sae_reporting(
            patient_id="PT-001", site_id="SITE-001", ae_id=2,
            description="Nausea Grade 1",
            onset_date=date(2023, 3, 10),
            reported_date=date(2023, 3, 12),
            reporting_delay_hours=48.0,
            sae_flag=False, protocol=protocol,  # NOT an SAE
        )
        assert results == []

    def test_pt0042_sae_36h_delay_is_major(self, protocol):
        """PT-0042's SAE was reported 36 hours late — must be Major."""
        results = evaluate_sae_reporting(
            patient_id="PT-0042", site_id="SITE-003", ae_id=1,
            description="Febrile neutropenia — Grade 3 — Hospitalisation required",
            onset_date=date(2023, 3, 10),
            reported_date=date(2023, 3, 11),
            reporting_delay_hours=36.0,
            sae_flag=True, protocol=protocol,
        )
        assert len(results) == 1
        assert results[0].rule_id == "REP-01"
        assert results[0].severity == DeviationSeverity.MAJOR
        assert results[0].patient_id == "PT-0042"

    def test_evidence_has_delay_hours(self, protocol):
        results = evaluate_sae_reporting(
            patient_id="PT-0042", site_id="SITE-003", ae_id=1,
            description="SAE",
            onset_date=date(2023, 3, 10),
            reported_date=date(2023, 3, 11),
            reporting_delay_hours=36.0,
            sae_flag=True, protocol=protocol,
        )
        ev = results[0].evidence
        assert ev["reporting_delay_hours"] == 36.0
        assert ev["max_allowed_hours"] == 24

    def test_unreported_sae_is_deviation(self, protocol):
        """SAE with no reported_date is also a violation."""
        results = evaluate_sae_reporting(
            patient_id="PT-001", site_id="SITE-001", ae_id=3,
            description="Pulmonary embolism",
            onset_date=date(2023, 3, 10),
            reported_date=None,
            reporting_delay_hours=None,
            sae_flag=True, protocol=protocol,
        )
        assert len(results) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────────────────────────────────────────

class TestDeduplication:
    def test_dedup_key_uniqueness(self):
        d1 = DeviationResult(
            patient_id="PT-001", site_id="SITE-001", rule_id="INC-01",
            deviation_type="Eligibility", description="Test",
            severity=DeviationSeverity.MAJOR, detected_date=date(2023, 2, 1),
        )
        d2 = DeviationResult(
            patient_id="PT-001", site_id="SITE-001", rule_id="INC-01",
            deviation_type="Eligibility", description="Duplicate",
            severity=DeviationSeverity.MAJOR, detected_date=date(2023, 2, 1),
        )
        assert d1.dedup_key() == d2.dedup_key()

    def test_evaluate_patient_deduplicates(self, protocol):
        """Same patient evaluated twice should not produce double results."""
        kwargs = _clean_patient_kwargs(protocol)
        results1 = evaluate_patient(**kwargs)
        results2 = evaluate_patient(**kwargs)
        assert len(results1) == len(results2)
        keys1 = {r.dedup_key() for r in results1}
        keys2 = {r.dedup_key() for r in results2}
        assert keys1 == keys2


# ─────────────────────────────────────────────────────────────────────────────
# PT-0042 end-to-end
# ─────────────────────────────────────────────────────────────────────────────

class TestPT0042Violations:
    """
    Verify that the engine detects all four known PT-0042 violations.
    Uses synthetic data that mirrors the seeded database values.
    """

    @pytest.fixture
    def pt0042_results(self, protocol):
        enroll = date(2023, 2, 20)
        sched_v3 = enroll + timedelta(days=14)
        actual_v3 = sched_v3 + timedelta(days=8)  # 8 days late
        sched_v4 = enroll + timedelta(days=28)

        return evaluate_patient(
            patient_id="PT-0042",
            site_id="SITE-003",
            enrollment_date=enroll,
            age=76,
            ecog_score=1,
            diagnosis_confirmed=True,
            prior_egfr_alk_treatment_days=None,
            active_infection=False,
            pregnant_or_breastfeeding=False,
            consent_signed_before_procedure=True,
            visits=[
                {
                    "id": 1, "visit_number": 1, "visit_name": "Screening",
                    "scheduled_date": enroll - timedelta(days=14),
                    "actual_date": enroll - timedelta(days=14),
                    "window_deviation_days": 0,
                    "completed_assessments_json": json.dumps([
                        "informed_consent", "medical_history", "demographics", "vitals",
                        "physical_exam", "ecog_score", "labs_hematology", "labs_chemistry",
                        "ecg", "pregnancy_test", "tumor_assessment",
                    ]),
                },
                {
                    "id": 2, "visit_number": 2, "visit_name": "Baseline / Day 1",
                    "scheduled_date": enroll, "actual_date": enroll,
                    "window_deviation_days": 0,
                    "completed_assessments_json": json.dumps([
                        "vitals", "physical_exam", "ecog_score", "labs_hematology",
                        "labs_chemistry", "ecg", "dosing_cycle1_day1", "concomitant_medications",
                    ]),
                },
                {
                    "id": 3, "visit_number": 3, "visit_name": "Cycle 1 Day 15",
                    "scheduled_date": sched_v3,
                    "actual_date": actual_v3,  # 8 days late
                    "window_deviation_days": 8,
                    "completed_assessments_json": json.dumps([
                        "vitals", "physical_exam", "labs_hematology", "labs_chemistry",
                        "adverse_event_review", "concomitant_medications",
                    ]),
                },
                {
                    "id": 4, "visit_number": 4, "visit_name": "Cycle 1 End / Efficacy Assessment",
                    "scheduled_date": sched_v4,
                    "actual_date": sched_v4,
                    "window_deviation_days": 0,
                    # tumor_assessment intentionally missing
                    "completed_assessments_json": json.dumps([
                        "vitals", "physical_exam", "ecog_score", "labs_hematology",
                        "labs_chemistry", "ecg", "adverse_event_review",
                        "concomitant_medications", "dosing_compliance_review",
                    ]),
                },
            ],
            lab_results=[
                {"visit_id": 1, "test_name": "hemoglobin", "value": 13.0, "collection_date": enroll - timedelta(days=14)},
                {"visit_id": 1, "test_name": "anc", "value": 3.0, "collection_date": enroll - timedelta(days=14)},
                {"visit_id": 1, "test_name": "platelets", "value": 200.0, "collection_date": enroll - timedelta(days=14)},
                {"visit_id": 1, "test_name": "creatinine", "value": 0.9, "collection_date": enroll - timedelta(days=14)},
                {"visit_id": 1, "test_name": "alt", "value": 25.0, "collection_date": enroll - timedelta(days=14)},
            ],
            adverse_events=[{
                "id": 1,
                "description": "Febrile neutropenia — Grade 3",
                "onset_date": date(2023, 4, 1),
                "reported_date": date(2023, 4, 2),
                "reporting_delay_hours": 36.0,
                "sae_flag": True,
            }],
            protocol=protocol,
        )

    def test_inc01_detected(self, pt0042_results):
        rule_ids = [r.rule_id for r in pt0042_results]
        assert "INC-01" in rule_ids, f"Expected INC-01 in {rule_ids}"

    def test_inc01_is_major(self, pt0042_results):
        inc01 = next(r for r in pt0042_results if r.rule_id == "INC-01")
        assert inc01.severity == DeviationSeverity.MAJOR

    def test_visit3_window_violation_detected(self, pt0042_results):
        window_devs = [r for r in pt0042_results if r.rule_id == _VISIT_WINDOW_RULE_ID and r.visit_id == 3]
        assert window_devs, "Visit 3 window violation (8 days late) should be detected"

    def test_tumor_assessment_missing_detected(self, pt0042_results):
        missing = [r for r in pt0042_results
                   if r.deviation_type == "Missing Assessment"
                   and "tumor_assessment" in r.evidence.get("missing_assessment", "")]
        assert missing, "Missing tumor_assessment at Visit 4 should be detected"

    def test_tumor_assessment_missing_is_major(self, pt0042_results):
        missing = next(r for r in pt0042_results
                       if r.deviation_type == "Missing Assessment"
                       and "tumor_assessment" in r.evidence.get("missing_assessment", ""))
        assert missing.severity == DeviationSeverity.MAJOR

    def test_sae_reporting_delay_detected(self, pt0042_results):
        sae_devs = [r for r in pt0042_results if r.rule_id == "REP-01"]
        assert sae_devs, "SAE 36h reporting delay should be detected"

    def test_sae_reporting_delay_is_major(self, pt0042_results):
        sae = next(r for r in pt0042_results if r.rule_id == "REP-01")
        assert sae.severity == DeviationSeverity.MAJOR

    def test_all_four_known_violations_detected(self, pt0042_results):
        """The four primary PT-0042 violations must all be present."""
        rule_ids = {r.rule_id for r in pt0042_results}
        assert "INC-01" in rule_ids, "Missing INC-01"
        assert _VISIT_WINDOW_RULE_ID in rule_ids, "Missing VISIT-WINDOW"
        assert "REP-01" in rule_ids, "Missing REP-01"
        # tumor_assessment missing
        has_tumor = any(
            "tumor_assessment" in r.evidence.get("missing_assessment", "")
            for r in pt0042_results
        )
        assert has_tumor, "Missing tumor_assessment deviation"
