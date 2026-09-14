"""
Deterministic synthetic data generators for the TrialGuard demo dataset.

ALL DATA IS ENTIRELY FICTITIOUS.
No real patients, investigators, institutions, or clinical data are represented.
This module is used solely for the IBM Bob AI Hackathon demo.

Design principles:
- All randomness uses a fixed seed (random.seed(42)) so results are reproducible.
- The generated dataset tells a specific story to support the demo scenario:
    Site 003 (London) — deliberately problematic: eligibility breach, SAE delay,
                        visit window violations, missing assessments.
    Site 005 (Munich) — clean comparison site: all visits on time, all assessments
                        complete, no SAEs, one minor deviation only.
    Patient PT-0042   — at Site 003, age 76 (violates INC-01 which requires ≤75).
- Risk scores are NOT set here.  They are computed by the risk scorer engine.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from typing import Any

# Fixed seed for reproducibility
random.seed(42)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

TRIAL_START = date(2023, 1, 15)
SEED_DATE = date(2023, 5, 1)  # The "today" reference point for all derived dates

SITE_DEFINITIONS = [
    {
        "id": "SITE-001",
        "name": "Boston General Hospital Research Center",
        "city": "Boston",
        "country": "USA",
        "pi": "Dr. James Harrison",
        "target": 20,
        "profile": "normal",
    },
    {
        "id": "SITE-002",
        "name": "New York Medical Center — Oncology Trials Unit",
        "city": "New York",
        "country": "USA",
        "pi": "Dr. Susan Park",
        "target": 20,
        "profile": "normal",
    },
    {
        "id": "SITE-003",
        "name": "Royal London Hospital — Phase II Oncology Unit",
        "city": "London",
        "country": "UK",
        "pi": "Dr. Michael Thornton",
        "target": 20,
        "profile": "problematic",  # Designed to produce High risk score
    },
    {
        "id": "SITE-004",
        "name": "Toronto University Hospital — Clinical Trials Centre",
        "city": "Toronto",
        "country": "Canada",
        "pi": "Dr. Priya Sharma",
        "target": 20,
        "profile": "elevated",  # Medium risk
    },
    {
        "id": "SITE-005",
        "name": "Munich University Clinic — Thoracic Oncology",
        "city": "Munich",
        "country": "Germany",
        "pi": "Dr. Klaus Weber",
        "target": 20,
        "profile": "clean",  # Designed to produce Low risk score
    },
    {
        "id": "SITE-006",
        "name": "Sydney Cancer Research Institute",
        "city": "Sydney",
        "country": "Australia",
        "pi": "Dr. Fiona Chen",
        "target": 20,
        "profile": "normal",
    },
]

# Visit schedule mirrors protocol.json
VISIT_SCHEDULE = [
    {"visit_number": 1, "name": "Screening", "nominal_day": -14, "window_before": 0, "window_after": 3},
    {"visit_number": 2, "name": "Baseline / Day 1", "nominal_day": 0, "window_before": 1, "window_after": 1},
    {"visit_number": 3, "name": "Cycle 1 Day 15", "nominal_day": 14, "window_before": 2, "window_after": 2},
    {"visit_number": 4, "name": "Cycle 1 End / Efficacy Assessment", "nominal_day": 28, "window_before": 3, "window_after": 3},
]

# Required assessments per visit (mirrors protocol.json)
REQUIRED_ASSESSMENTS = {
    1: ["informed_consent", "medical_history", "demographics", "vitals", "physical_exam",
        "ecog_score", "labs_hematology", "labs_chemistry", "ecg", "pregnancy_test", "tumor_assessment"],
    2: ["vitals", "physical_exam", "ecog_score", "labs_hematology", "labs_chemistry",
        "ecg", "dosing_cycle1_day1", "concomitant_medications"],
    3: ["vitals", "physical_exam", "labs_hematology", "labs_chemistry",
        "adverse_event_review", "concomitant_medications"],
    4: ["vitals", "physical_exam", "ecog_score", "labs_hematology", "labs_chemistry",
        "ecg", "tumor_assessment", "adverse_event_review", "concomitant_medications",
        "dosing_compliance_review"],
}

# Lab tests generated per visit
LAB_TESTS = [
    {"test_name": "hemoglobin",  "display_name": "Hemoglobin",             "unit": "g/dL",     "normal_mean": 13.5, "normal_std": 1.5, "rule_id": "LAB-01", "min": 8.0,  "max": None},
    {"test_name": "anc",         "display_name": "Absolute Neutrophil Count","unit": "x10^9/L", "normal_mean": 3.5,  "normal_std": 1.0, "rule_id": "LAB-02", "min": 1.0,  "max": None},
    {"test_name": "platelets",   "display_name": "Platelet Count",          "unit": "x10^9/L", "normal_mean": 220.0,"normal_std": 50.0,"rule_id": "LAB-05", "min": 75.0, "max": None},
    {"test_name": "creatinine",  "display_name": "Serum Creatinine",        "unit": "mg/dL",    "normal_mean": 0.9,  "normal_std": 0.2, "rule_id": "LAB-03", "min": None, "max": 1.5},
    {"test_name": "alt",         "display_name": "ALT",                     "unit": "U/L",      "normal_mean": 30.0, "normal_std": 15.0,"rule_id": "LAB-04", "min": None, "max": 80.0},
]

AE_DESCRIPTIONS = [
    "Fatigue — Grade 2",
    "Nausea — Grade 1",
    "Alopecia — Grade 1",
    "Peripheral neuropathy — Grade 2",
    "Anaemia — Grade 2",
    "Elevated liver enzymes — Grade 1",
    "Decreased appetite — Grade 1",
    "Diarrhoea — Grade 1",
    "Rash — Grade 1",
    "Dyspnoea — Grade 2",
]

SAE_DESCRIPTIONS = [
    "Febrile neutropenia — Grade 3 — Hospitalisation required",
    "Pulmonary embolism — Grade 4 — Life-threatening",
    "Severe pneumonitis — Grade 3 — Related to study drug",
    "Cardiac arrhythmia — Grade 3 — Dose held",
    "Sepsis — Grade 4 — ICU admission",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────────────────

def _days(n: int) -> timedelta:
    return timedelta(days=n)


def _normal(mean: float, std: float, min_val: float | None = None, max_val: float | None = None) -> float:
    """Return a normally-distributed random float, optionally clamped."""
    v = random.gauss(mean, std)
    if min_val is not None:
        v = max(v, min_val)
    if max_val is not None:
        v = min(v, max_val)
    return round(v, 2)


def _jitter(base_date: date, min_days: int, max_days: int) -> date:
    return base_date + _days(random.randint(min_days, max_days))


def _is_out_of_range(value: float, min_val: float | None, max_val: float | None) -> bool:
    if min_val is not None and value < min_val:
        return True
    if max_val is not None and value > max_val:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Trial
# ─────────────────────────────────────────────────────────────────────────────

def generate_trial() -> dict[str, Any]:
    return {
        "id": "TRIAL-TG-001",
        "name": "Phase II Study of Compound XR-447 in Advanced Non-Small Cell Lung Cancer (SYNTHETIC)",
        "protocol_version": "2.1",
        "sponsor": "TrialGuard Demo Sponsor Corp. (SYNTHETIC)",
        "phase": "II",
        "indication": "Advanced Non-Small Cell Lung Cancer (NSCLC)",
        "start_date": TRIAL_START,
        "end_date": date(2025, 6, 30),
        "target_enrollment": 120,
        "primary_endpoint": "Progression-Free Survival at 6 months",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Sites
# ─────────────────────────────────────────────────────────────────────────────

def generate_sites(trial_id: str) -> list[dict[str, Any]]:
    sites = []
    for defn in SITE_DEFINITIONS:
        activation = _jitter(TRIAL_START, 0, 30)
        enrolled = 10  # All sites have 10 patients in this demo
        sites.append({
            "id": defn["id"],
            "trial_id": trial_id,
            "name": defn["name"],
            "city": defn["city"],
            "country": defn["country"],
            "principal_investigator": defn["pi"],
            "status": "Active",
            "enrolled_count": enrolled,
            "target_enrollment": defn["target"],
            "activation_date": activation,
            "_profile": defn["profile"],  # Used by patient/visit generators; not stored in DB
        })
    return sites


# ─────────────────────────────────────────────────────────────────────────────
# Patients
# ─────────────────────────────────────────────────────────────────────────────

def _patient_id(site_index: int, patient_index: int) -> str:
    """Generate a zero-padded patient ID.  Site 003 patients start at PT-0031."""
    # Global counter: site_index * 10 + patient_index + 1 (1-based)
    global_index = site_index * 10 + patient_index + 1
    return f"PT-{global_index:04d}"


def generate_patients(sites: list[dict[str, Any]], trial_id: str) -> list[dict[str, Any]]:
    """
    Generate 10 patients per site.

    Special cases (Site 003 = index 2):
      - Patient at local index 2 → global PT-0023 is the first Site-003 patient.
        Wait: Site-003 is SITE_DEFINITIONS index 2 → global index starts at 2*10+1 = 21.
        So Site-003 patients are PT-0021 through PT-0030.
        PT-0042 does not belong to Site-003 with straight sequential numbering.

    CORRECTION: We want PT-0042 at Site 003.  To achieve this we assign patient IDs
    by a manual offset: Site-003 is site index 2, so patients start at global seq 41
    (to give PT-0041 … PT-0050).  Specifically patient index 1 (0-based) → PT-0042.

    ID assignment scheme:
      SITE-001 → PT-0001 … PT-0010
      SITE-002 → PT-0011 … PT-0020
      SITE-003 → PT-0041 … PT-0050   (offset to land PT-0042 at index 1)
      SITE-004 → PT-0051 … PT-0060
      SITE-005 → PT-0061 … PT-0070
      SITE-006 → PT-0071 … PT-0080
    """
    site_offsets = {
        "SITE-001": 0,
        "SITE-002": 10,
        "SITE-003": 40,   # ← offset so patient index 1 = PT-0042
        "SITE-004": 50,
        "SITE-005": 60,
        "SITE-006": 70,
    }

    patients = []
    for site in sites:
        site_id = site["id"]
        profile = site["_profile"]
        offset = site_offsets[site_id]

        for i in range(10):
            global_num = offset + i + 1
            patient_id = f"PT-{global_num:04d}"
            enrollment_date = _jitter(site["activation_date"] + _days(7), 0, 60)

            # Default: eligible patient
            age = random.randint(45, 70)
            ecog = random.randint(0, 2)
            diagnosis_confirmed = True
            prior_egfr_alk = None
            active_infection = False
            pregnant = False
            consent_ok = True

            # ── Site 003 — PT-0042 (i==1) — ELIGIBILITY BREACH ───────────────
            if site_id == "SITE-003" and i == 1:
                age = 76  # Violates INC-01 (must be 18–75)

            # ── Site 003 — other patients: some extra issues ──────────────────
            elif site_id == "SITE-003":
                if i == 4:
                    # Missing consent before procedure (INC-05)
                    consent_ok = False
                elif i == 7:
                    # EXC-02: active infection at enrollment
                    active_infection = True

            # ── Site 005 — all patients clean ─────────────────────────────────
            # No special overrides; defaults are all valid.

            # ── Site 004 — one borderline case ────────────────────────────────
            elif site_id == "SITE-004" and i == 3:
                ecog = 3  # Violates INC-02

            patients.append({
                "id": patient_id,
                "site_id": site_id,
                "trial_id": trial_id,
                "age": age,
                "sex": random.choice(["M", "F"]),
                "ecog_score": ecog,
                "diagnosis_confirmed": diagnosis_confirmed,
                "prior_egfr_alk_treatment_days": prior_egfr_alk,
                "active_infection": active_infection,
                "pregnant_or_breastfeeding": pregnant,
                "consent_signed_before_procedure": consent_ok,
                "enrollment_date": enrollment_date,
                "status": "Enrolled",
                "_site_profile": profile,
            })

    return patients


# ─────────────────────────────────────────────────────────────────────────────
# Visits
# ─────────────────────────────────────────────────────────────────────────────

def _compute_scheduled_date(enrollment_date: date, nominal_day: int) -> date:
    """Screening is nominally Day -14 from Day 1 (enrollment_date)."""
    return enrollment_date + _days(nominal_day)


def _add_visit_window_deviation(
    scheduled: date,
    profile: str,
    visit_number: int,
    is_pt0042: bool,
) -> date:
    """
    Return the actual visit date, applying site-profile-specific timing patterns.
    """
    if profile == "clean":
        # Site 005: always exactly on time (no visit window violations)
        offset = 0
    elif profile == "problematic":
        if is_pt0042 and visit_number == 3:
            # PT-0042 Visit 3 is deliberately 8 days late (window ±2 days → deviation = 6 days late)
            offset = 8
        elif visit_number in (3, 4):
            # Site 003: visits 3 and 4 tend to be late
            offset = random.choice([0, 0, 3, 5, 6, 7])
        else:
            offset = random.choice([-1, 0, 0, 1])
    elif profile == "elevated":
        offset = random.choice([0, 0, 0, 2, 4])
    else:
        # normal: mostly on time, occasional 1–3 day shift
        offset = random.choice([-1, -1, 0, 0, 0, 1, 1, 2])
    return scheduled + _days(offset)


def generate_visits(patients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visits = []
    visit_id_counter = 1

    for patient in patients:
        profile = patient["_site_profile"]
        enrollment_date = patient["enrollment_date"]
        is_pt0042 = patient["id"] == "PT-0042"

        for vs in VISIT_SCHEDULE:
            vnum = vs["visit_number"]
            scheduled = _compute_scheduled_date(enrollment_date, vs["nominal_day"])
            actual = _add_visit_window_deviation(scheduled, profile, vnum, is_pt0042)

            # Build assessment list
            required = list(REQUIRED_ASSESSMENTS[vnum])

            # Drop assessments based on site profile
            completed = list(required)  # start with all
            if profile == "problematic":
                if is_pt0042 and vnum == 4:
                    # PT-0042 missing tumor_assessment at Visit 4 (primary endpoint!)
                    completed = [a for a in completed if a != "tumor_assessment"]
                elif not is_pt0042 and vnum == 3 and patient["id"] in ["PT-0043", "PT-0046"]:
                    # Two other Site-003 patients missing AE review at Visit 3
                    completed = [a for a in completed if a != "adverse_event_review"]
            elif profile == "elevated" and vnum == 3 and patient["id"] == "PT-0054":
                completed = [a for a in completed if a != "labs_chemistry"]

            # Compute window deviation in days (positive = late, negative = early)
            window_deviation = (actual - scheduled).days

            visits.append({
                "_id": visit_id_counter,
                "patient_id": patient["id"],
                "site_id": patient["site_id"],
                "visit_number": vnum,
                "visit_name": vs["name"],
                "visit_type": "Scheduled",
                "scheduled_date": scheduled,
                "actual_date": actual,
                "window_deviation_days": window_deviation,
                "completed_assessments": json.dumps(completed),
                "notes": None,
            })
            visit_id_counter += 1

    return visits


# ─────────────────────────────────────────────────────────────────────────────
# Lab Results
# ─────────────────────────────────────────────────────────────────────────────

def generate_lab_results(
    patients: list[dict[str, Any]],
    visits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Generate approximately 5 lab tests per visit (one per test in LAB_TESTS).
    ~8% of results are intentionally out of range.
    Site 003 has a slightly higher out-of-range rate (~15%) for realism.
    """
    # Build visit lookup: patient_id + visit_number → visit dict
    visit_lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for v in visits:
        visit_lookup[(v["patient_id"], v["visit_number"])] = v

    results = []
    for patient in patients:
        profile = patient["_site_profile"]
        # Site 005 (clean) should have minimal lab deviations for demo contrast
        if profile == "clean":
            out_of_range_rate = 0.005  # 0.5% out-of-range (almost none)
        elif profile == "problematic":
            out_of_range_rate = 0.15  # 15% out-of-range (as designed)
        else:
            out_of_range_rate = 0.08  # 8% out-of-range (normal sites)

        for visit in [v for v in visits if v["patient_id"] == patient["id"]]:
            for lab in LAB_TESTS:
                # Decide if this result should be out of range
                force_oob = random.random() < out_of_range_rate

                if force_oob:
                    # Generate a value clearly outside the threshold
                    if lab["min"] is not None:
                        value = round(lab["min"] * random.uniform(0.5, 0.9), 2)
                    elif lab["max"] is not None:
                        value = round(lab["max"] * random.uniform(1.1, 1.5), 2)
                    else:
                        value = _normal(lab["normal_mean"], lab["normal_std"])
                else:
                    value = _normal(
                        lab["normal_mean"],
                        lab["normal_std"] * 0.5,  # tighter std for in-range values
                        min_val=lab["min"],
                        max_val=lab["max"],
                    )
                    # Ensure value is genuinely within range
                    if lab["min"] is not None:
                        value = max(value, lab["min"] + 0.1)
                    if lab["max"] is not None:
                        value = min(value, lab["max"] - 0.1)

                is_oob = _is_out_of_range(value, lab["min"], lab["max"])

                results.append({
                    "patient_id": patient["id"],
                    "visit_id": visit["_id"],
                    "test_name": lab["test_name"],
                    "display_name": lab["display_name"],
                    "value": value,
                    "unit": lab["unit"],
                    "reference_low": lab["min"],
                    "reference_high": lab["max"],
                    "collection_date": visit["actual_date"],
                    "is_out_of_range": is_oob,
                })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Adverse Events
# ─────────────────────────────────────────────────────────────────────────────

def generate_adverse_events(
    patients: list[dict[str, Any]],
    visits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Generate approximately 30 adverse events across all patients.
    Includes ~5 SAEs, with 2 having reporting delays > 24 hours.

    Site 003 deliberately has 2 SAEs with late reporting (violating REP-01).
    """
    events = []

    # Patients with SAEs (by patient_id and whether reporting is delayed)
    sae_patients = {
        "PT-0042": {"delayed": True,  "delay_hours": 36.0, "desc": SAE_DESCRIPTIONS[0]},
        "PT-0045": {"delayed": True,  "delay_hours": 48.0, "desc": SAE_DESCRIPTIONS[2]},
        "PT-0053": {"delayed": False, "delay_hours": 12.0, "desc": SAE_DESCRIPTIONS[1]},
        "PT-0017": {"delayed": False, "delay_hours": 6.0,  "desc": SAE_DESCRIPTIONS[3]},
        "PT-0063": {"delayed": False, "delay_hours": 18.0, "desc": SAE_DESCRIPTIONS[4]},
    }

    # Build a visit lookup for onset dates
    first_visit_date: dict[str, date] = {}
    for v in visits:
        pid = v["patient_id"]
        if pid not in first_visit_date:
            first_visit_date[pid] = v["actual_date"]
        else:
            first_visit_date[pid] = min(first_visit_date[pid], v["actual_date"])

    for patient in patients:
        pid = patient["id"]
        profile = patient["_site_profile"]

        # SAE records
        if pid in sae_patients:
            sae_info = sae_patients[pid]
            onset = _jitter(first_visit_date.get(pid, TRIAL_START + _days(30)), 10, 60)
            if sae_info["delayed"]:
                delay_h = sae_info["delay_hours"]
                reported = onset + _days(int(delay_h // 24) + 1)
            else:
                delay_h = sae_info["delay_hours"]
                reported = onset  # Same day

            events.append({
                "patient_id": pid,
                "site_id": patient["site_id"],
                "description": sae_info["desc"],
                "onset_date": onset,
                "sae_flag": True,
                "expected_flag": False,
                "reported_date": reported,
                "reporting_delay_hours": delay_h,
                "severity_grade": 3,
                "outcome": "Ongoing" if sae_info["delayed"] else "Resolved",
            })

        # Non-SAE AEs — roughly 3 per patient in problematic sites, 2 elsewhere
        ae_count = 3 if profile == "problematic" else (2 if profile in ("elevated", "normal") else 1)
        for _ in range(ae_count):
            onset = _jitter(first_visit_date.get(pid, TRIAL_START + _days(30)), 5, 90)
            events.append({
                "patient_id": pid,
                "site_id": patient["site_id"],
                "description": random.choice(AE_DESCRIPTIONS),
                "onset_date": onset,
                "sae_flag": False,
                "expected_flag": True,
                "reported_date": onset + _days(random.randint(0, 3)),
                "reporting_delay_hours": float(random.randint(1, 48)),
                "severity_grade": random.randint(1, 2),
                "outcome": random.choice(["Resolved", "Ongoing", "Resolved with sequelae"]),
            })

    return events


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_all() -> dict[str, Any]:
    """
    Generate the complete synthetic dataset.
    Returns a dict with keys: trial, sites, patients, visits, lab_results, adverse_events.
    Risk scores and deviations are NOT generated here — they are computed by the engine.
    """
    # Reset seed each time for full reproducibility
    random.seed(42)

    trial = generate_trial()
    sites = generate_sites(trial["id"])
    patients = generate_patients(sites, trial["id"])
    visits = generate_visits(patients)
    lab_results = generate_lab_results(patients, visits)
    adverse_events = generate_adverse_events(patients, visits)

    # Strip internal-only keys before returning
    for s in sites:
        s.pop("_profile", None)
    for p in patients:
        p.pop("_site_profile", None)
    for v in visits:
        v.pop("_id", None)  # Will be auto-assigned by DB

    return {
        "trial": trial,
        "sites": sites,
        "patients": patients,
        "visits": visits,
        "lab_results": lab_results,
        "adverse_events": adverse_events,
    }
