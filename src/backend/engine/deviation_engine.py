"""
Deterministic deviation engine for TrialGuard.

This module compares patient/visit/lab/adverse-event records against the
protocol rules and produces structured DeviationResult objects.

ARCHITECTURAL PRINCIPLE
-----------------------
No LLM, no AI, no probabilistic logic.  Every deviation is the result of
a deterministic rule check.  Severity comes from the protocol rule definition,
never from inference.

RULE CATEGORIES SUPPORTED
--------------------------
1. Visit window violations      (VISIT-WINDOW)
2. Missing required assessments (MISSING-ASSESSMENT)
3. Laboratory threshold         (LAB-THRESHOLD)
4. Eligibility inclusion        (ELIGIBILITY-INCLUSION)
5. Eligibility exclusion        (ELIGIBILITY-EXCLUSION)
6. SAE reporting delay          (SAE-REPORTING)
7. Consent / procedure ordering (CONSENT-ORDER)

DESIGN NOTES
------------
* Each evaluator is a pure function: (patient|visit|lab|ae, protocol) -> list[DeviationResult]
* The top-level run_analysis() function is the only place that touches the DB.
* DeviationResult is a dataclass (not an ORM object) so evaluators are testable
  without a database.
* Duplicate prevention: a (patient_id, rule_id, visit_id) triple that already
  has an OPEN deviation in the DB is skipped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.backend.engine.protocol_loader import Protocol, ProtocolRule, get_protocol
from src.backend.engine.severity_classifier import classify
from src.backend.models import DeviationSeverity


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DeviationResult:
    """
    A single detected protocol deviation.

    This is a pure-Python dataclass and does NOT extend any ORM model.
    It is converted to an ORM Deviation object by the persistence layer.
    """

    patient_id: str
    site_id: str
    rule_id: str
    deviation_type: str
    """Category label: e.g. 'Eligibility - Inclusion', 'Visit Window', 'Lab Threshold'."""
    description: str
    """Human-readable explanation of the specific deviation detected."""
    severity: DeviationSeverity
    detected_date: date
    visit_id: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    """Structured evidence: actual vs. expected values, thresholds, etc."""

    def evidence_json(self) -> str:
        """Serialise evidence to a JSON string for DB storage."""
        return json.dumps(self.evidence, default=str)

    def dedup_key(self) -> tuple[str, str, int | None]:
        """
        Uniqueness key for duplicate prevention.

        Two results with the same (patient_id, rule_id, visit_id) represent
        the same violation instance and should not create a second open
        Deviation row.
        """
        return (self.patient_id, self.rule_id, self.visit_id)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Visit window evaluator
# ─────────────────────────────────────────────────────────────────────────────

#  Synthetic rule_id for visit-window deviations (not in protocol.json because
#  visit windows are defined as VisitSpec attributes, not as named rules).
_VISIT_WINDOW_RULE_ID = "VISIT-WINDOW"
_VISIT_WINDOW_SEVERITY = DeviationSeverity.MINOR  # pragmatic default for window violations
_VISIT_WINDOW_DESCRIPTION_TEMPLATE = (
    "Visit {visit_name} (#{visit_number}) occurred {deviation_days} day(s) "
    "{direction} the allowed window of ±{window_before}/{window_after} day(s) "
    "from the scheduled date."
)


def evaluate_visit_window(
    patient_id: str,
    site_id: str,
    visit_id: int,
    visit_number: int,
    visit_name: str,
    scheduled_date: date,
    actual_date: date | None,
    protocol: Protocol,
) -> list[DeviationResult]:
    """
    Detect whether a visit occurred outside its allowed window.

    Returns an empty list if the visit is within window or has no actual date.
    """
    if actual_date is None:
        return []

    try:
        spec = protocol.visit(visit_number)
    except KeyError:
        # Visit number not in protocol — cannot evaluate window
        return []

    deviation_days = (actual_date - scheduled_date).days
    if spec.within_window(deviation_days):
        return []

    direction = "late" if deviation_days > 0 else "early"
    abs_days = abs(deviation_days)

    return [DeviationResult(
        patient_id=patient_id,
        site_id=site_id,
        rule_id=_VISIT_WINDOW_RULE_ID,
        deviation_type="Visit Window",
        description=_VISIT_WINDOW_DESCRIPTION_TEMPLATE.format(
            visit_name=visit_name,
            visit_number=visit_number,
            deviation_days=abs_days,
            direction=direction,
            window_before=spec.window_days_before,
            window_after=spec.window_days_after,
        ),
        severity=_VISIT_WINDOW_SEVERITY,
        detected_date=actual_date,
        visit_id=visit_id,
        evidence={
            "visit_number": visit_number,
            "visit_name": visit_name,
            "scheduled_date": str(scheduled_date),
            "actual_date": str(actual_date),
            "deviation_days": deviation_days,
            "window_days_before": spec.window_days_before,
            "window_days_after": spec.window_days_after,
        },
    )]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Missing required assessments evaluator
# ─────────────────────────────────────────────────────────────────────────────

_MISSING_ASSESSMENT_RULE_ID = "MISSING-ASSESSMENT"
_MISSING_ASSESSMENT_SEVERITY = DeviationSeverity.MINOR

# Visit 4's tumor_assessment is the primary endpoint — escalate to Major
_PRIMARY_ENDPOINT_ASSESSMENT = "tumor_assessment"
_PRIMARY_ENDPOINT_VISIT = 4
_PRIMARY_ENDPOINT_SEVERITY = DeviationSeverity.MAJOR


def evaluate_missing_assessments(
    patient_id: str,
    site_id: str,
    visit_id: int,
    visit_number: int,
    visit_name: str,
    actual_date: date | None,
    completed_assessments_json: str | None,
    protocol: Protocol,
) -> list[DeviationResult]:
    """
    Detect missing required assessments at a completed visit.

    Returns one DeviationResult per missing assessment.
    Returns empty list if the visit has no actual_date (not yet occurred).
    """
    if actual_date is None:
        return []

    try:
        spec = protocol.visit(visit_number)
    except KeyError:
        return []

    try:
        completed: list[str] = json.loads(completed_assessments_json or "[]")
    except (json.JSONDecodeError, TypeError):
        completed = []

    completed_set = set(completed)
    results: list[DeviationResult] = []

    for assessment in spec.required_assessments:
        if assessment not in completed_set:
            # Escalate severity if this is the primary endpoint assessment
            is_primary = (
                assessment == _PRIMARY_ENDPOINT_ASSESSMENT
                and visit_number == _PRIMARY_ENDPOINT_VISIT
            )
            severity = (
                _PRIMARY_ENDPOINT_SEVERITY if is_primary else _MISSING_ASSESSMENT_SEVERITY
            )
            rule_id = f"{_MISSING_ASSESSMENT_RULE_ID}-{assessment.upper().replace('_', '-')}"

            results.append(DeviationResult(
                patient_id=patient_id,
                site_id=site_id,
                rule_id=rule_id,
                deviation_type="Missing Assessment",
                description=(
                    f"Required assessment '{assessment}' was not completed at "
                    f"Visit {visit_number} ({visit_name})."
                    + (" This is the primary endpoint assessment." if is_primary else "")
                ),
                severity=severity,
                detected_date=actual_date,
                visit_id=visit_id,
                evidence={
                    "visit_number": visit_number,
                    "visit_name": visit_name,
                    "missing_assessment": assessment,
                    "completed_assessments": sorted(completed_set),
                    "required_assessments": list(spec.required_assessments),
                    "is_primary_endpoint": is_primary,
                },
            ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 3. Laboratory threshold evaluator
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_lab_result(
    patient_id: str,
    site_id: str,
    visit_id: int,
    test_name: str,
    value: float,
    collection_date: date,
    protocol: Protocol,
) -> list[DeviationResult]:
    """
    Detect a lab value that violates a protocol threshold.

    Matches against protocol lab rules by test_name.
    Returns at most one DeviationResult per test_name (one rule per test).
    """
    # Find the matching lab rule by test_name
    lab_rules = protocol.rules_by_category("lab")
    matching = [r for r in lab_rules if r.extra.get("test_name") == test_name]

    results: list[DeviationResult] = []
    for rule in matching:
        min_val = rule.extra.get("min_value")
        max_val = rule.extra.get("max_value")
        unit = rule.extra.get("unit", "")
        display_name = rule.extra.get("display_name", test_name)

        violated = False
        violation_detail = ""
        if min_val is not None and value < min_val:
            violated = True
            violation_detail = f"{value} {unit} is below minimum threshold of {min_val} {unit}"
        elif max_val is not None and value > max_val:
            violated = True
            violation_detail = f"{value} {unit} exceeds maximum threshold of {max_val} {unit}"

        if violated:
            severity = classify(rule.rule_id, protocol)
            results.append(DeviationResult(
                patient_id=patient_id,
                site_id=site_id,
                rule_id=rule.rule_id,
                deviation_type="Lab Threshold",
                description=(
                    f"{display_name} threshold violation: {violation_detail}. "
                    f"Action required: {rule.extra.get('action_required', 'Document and escalate.')}"
                ),
                severity=severity,
                detected_date=collection_date,
                visit_id=visit_id,
                evidence={
                    "test_name": test_name,
                    "display_name": display_name,
                    "value": value,
                    "unit": unit,
                    "min_threshold": min_val,
                    "max_threshold": max_val,
                    "violation_detail": violation_detail,
                },
            ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 4. Eligibility evaluator (inclusion and exclusion)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_eligibility(
    patient_id: str,
    site_id: str,
    enrollment_date: date,
    age: int,
    ecog_score: int | None,
    diagnosis_confirmed: bool,
    prior_egfr_alk_treatment_days: int | None,
    active_infection: bool,
    pregnant_or_breastfeeding: bool,
    consent_signed_before_procedure: bool,
    protocol: Protocol,
) -> list[DeviationResult]:
    """
    Evaluate all inclusion and exclusion criteria for a patient.

    Each rule is checked individually.  Multiple violations produce multiple
    DeviationResults.
    """
    results: list[DeviationResult] = []

    # ── Inclusion rules ───────────────────────────────────────────────────────

    # INC-01: age between 18 and 75
    inc_01 = protocol.rules.get("INC-01")
    if inc_01:
        low, high = inc_01.extra["values"][0], inc_01.extra["values"][1]
        if not (low <= age <= high):
            results.append(DeviationResult(
                patient_id=patient_id,
                site_id=site_id,
                rule_id="INC-01",
                deviation_type="Eligibility - Inclusion",
                description=(
                    f"Patient age {age} violates INC-01: age must be between "
                    f"{low} and {high} years (inclusive) at enrollment."
                ),
                severity=classify("INC-01", protocol),
                detected_date=enrollment_date,
                visit_id=None,
                evidence={
                    "rule": "INC-01",
                    "patient_age": age,
                    "required_min": low,
                    "required_max": high,
                },
            ))

    # INC-02: ECOG score <= 2
    inc_02 = protocol.rules.get("INC-02")
    if inc_02 and ecog_score is not None:
        max_ecog = inc_02.extra["value"]
        if ecog_score > max_ecog:
            results.append(DeviationResult(
                patient_id=patient_id,
                site_id=site_id,
                rule_id="INC-02",
                deviation_type="Eligibility - Inclusion",
                description=(
                    f"Patient ECOG Performance Status {ecog_score} violates INC-02: "
                    f"must be <= {max_ecog} at screening."
                ),
                severity=classify("INC-02", protocol),
                detected_date=enrollment_date,
                visit_id=None,
                evidence={
                    "rule": "INC-02",
                    "patient_ecog": ecog_score,
                    "required_max": max_ecog,
                },
            ))

    # INC-03: diagnosis confirmed
    inc_03 = protocol.rules.get("INC-03")
    if inc_03 and not diagnosis_confirmed:
        results.append(DeviationResult(
            patient_id=patient_id,
            site_id=site_id,
            rule_id="INC-03",
            deviation_type="Eligibility - Inclusion",
            description=(
                "Patient enrolled without confirmed NSCLC diagnosis (INC-03). "
                "Histological or cytological confirmation is required."
            ),
            severity=classify("INC-03", protocol),
            detected_date=enrollment_date,
            visit_id=None,
            evidence={"rule": "INC-03", "diagnosis_confirmed": diagnosis_confirmed},
        ))

    # INC-05: consent signed before procedure
    inc_05 = protocol.rules.get("INC-05")
    if inc_05 and not consent_signed_before_procedure:
        results.append(DeviationResult(
            patient_id=patient_id,
            site_id=site_id,
            rule_id="INC-05",
            deviation_type="Consent / Procedure Order",
            description=(
                "Informed Consent Form was not signed prior to first study-related "
                "procedure (INC-05 / GCP ICH E6 requirement)."
            ),
            severity=classify("INC-05", protocol),
            detected_date=enrollment_date,
            visit_id=None,
            evidence={
                "rule": "INC-05",
                "consent_signed_before_procedure": consent_signed_before_procedure,
            },
        ))

    # ── Exclusion rules ───────────────────────────────────────────────────────

    # EXC-02: active infection at enrollment
    exc_02 = protocol.rules.get("EXC-02")
    if exc_02 and active_infection:
        results.append(DeviationResult(
            patient_id=patient_id,
            site_id=site_id,
            rule_id="EXC-02",
            deviation_type="Eligibility - Exclusion",
            description=(
                "Patient enrolled with an active uncontrolled systemic infection "
                "(EXC-02). This is a protocol exclusion criterion."
            ),
            severity=classify("EXC-02", protocol),
            detected_date=enrollment_date,
            visit_id=None,
            evidence={"rule": "EXC-02", "active_infection": active_infection},
        ))

    # EXC-03: pregnancy / breastfeeding
    exc_03 = protocol.rules.get("EXC-03")
    if exc_03 and pregnant_or_breastfeeding:
        results.append(DeviationResult(
            patient_id=patient_id,
            site_id=site_id,
            rule_id="EXC-03",
            deviation_type="Eligibility - Exclusion",
            description=(
                "Patient enrolled while pregnant or breastfeeding (EXC-03). "
                "Compound XR-447 is teratogenic; this is a protocol exclusion criterion."
            ),
            severity=classify("EXC-03", protocol),
            detected_date=enrollment_date,
            visit_id=None,
            evidence={
                "rule": "EXC-03",
                "pregnant_or_breastfeeding": pregnant_or_breastfeeding,
            },
        ))

    # EXC-01: prior EGFR/ALK treatment within 28 days
    exc_01 = protocol.rules.get("EXC-01")
    if exc_01 and prior_egfr_alk_treatment_days is not None:
        # The exclusion is: patient should NOT have had treatment within 28 days
        # i.e., prior_egfr_alk_treatment_days < 28 means they had recent treatment
        # The rule says "operator: gte, value: 28" meaning enrolled is a violation
        # if their last treatment was >= 28 days ago? That appears inverted in the
        # protocol JSON. Re-reading: "Prior treatment within 28 days before enrollment"
        # is the EXCLUSION — so if days_since_last_treatment < 28 → violation.
        # The JSON has operator "gte" value 28 on the field "prior_egfr_alk_treatment_days"
        # which we interpret as: if the gap (days since last treatment) < 28 → excluded.
        # In the seed data prior_egfr_alk_treatment_days is None for all clean patients,
        # so we only flag when it is set AND < 28.
        min_days = exc_01.extra.get("value", 28)
        if prior_egfr_alk_treatment_days < min_days:
            results.append(DeviationResult(
                patient_id=patient_id,
                site_id=site_id,
                rule_id="EXC-01",
                deviation_type="Eligibility - Exclusion",
                description=(
                    f"Patient had EGFR/ALK inhibitor treatment "
                    f"{prior_egfr_alk_treatment_days} day(s) before enrollment; "
                    f"EXC-01 requires a washout of at least {min_days} days."
                ),
                severity=classify("EXC-01", protocol),
                detected_date=enrollment_date,
                visit_id=None,
                evidence={
                    "rule": "EXC-01",
                    "days_since_last_treatment": prior_egfr_alk_treatment_days,
                    "required_washout_days": min_days,
                },
            ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 5. SAE reporting delay evaluator
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_sae_reporting(
    patient_id: str,
    site_id: str,
    ae_id: int,
    description: str,
    onset_date: date,
    reported_date: date | None,
    reporting_delay_hours: float | None,
    sae_flag: bool,
    protocol: Protocol,
) -> list[DeviationResult]:
    """
    Detect late SAE reporting (REP-01: must report within 24 hours).

    Only evaluates records with sae_flag=True and a known reporting delay.
    """
    if not sae_flag:
        return []

    rep_01 = protocol.rules.get("REP-01")
    if rep_01 is None:
        return []

    max_hours = rep_01.extra.get("value", 24)

    # If not yet reported, that itself is a violation
    if reported_date is None:
        delay = None
        violation_desc = "SAE has not been reported to the Sponsor (reporting_date is null)."
    elif reporting_delay_hours is not None and reporting_delay_hours > max_hours:
        delay = reporting_delay_hours
        violation_desc = (
            f"SAE reported {reporting_delay_hours:.1f} hours after onset; "
            f"REP-01 requires reporting within {max_hours} hours."
        )
    else:
        return []  # Within window

    return [DeviationResult(
        patient_id=patient_id,
        site_id=site_id,
        rule_id="REP-01",
        deviation_type="SAE Reporting",
        description=violation_desc,
        severity=classify("REP-01", protocol),
        detected_date=onset_date,
        visit_id=None,
        evidence={
            "ae_description": description,
            "onset_date": str(onset_date),
            "reported_date": str(reported_date) if reported_date else None,
            "reporting_delay_hours": delay,
            "max_allowed_hours": max_hours,
        },
    )]


# ─────────────────────────────────────────────────────────────────────────────
# 6. Dosing evaluator (INC-04 ANC at screening)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_inc04_anc(
    patient_id: str,
    site_id: str,
    visit_id: int,
    anc_value: float,
    collection_date: date,
    protocol: Protocol,
) -> list[DeviationResult]:
    """
    INC-04: ANC must be >= 1.5 x10^9/L at screening.

    This is evaluated separately from general lab thresholds because INC-04
    is an eligibility rule, not a safety threshold rule (LAB-02 covers
    the on-treatment ANC threshold of 1.0).
    """
    inc_04 = protocol.rules.get("INC-04")
    if inc_04 is None:
        return []

    min_anc = inc_04.extra.get("value", 1.5)
    if anc_value >= min_anc:
        return []

    return [DeviationResult(
        patient_id=patient_id,
        site_id=site_id,
        rule_id="INC-04",
        deviation_type="Eligibility - Inclusion",
        description=(
            f"Screening ANC {anc_value} x10^9/L is below the eligibility threshold "
            f"of {min_anc} x10^9/L (INC-04). Patient may have been enrolled with "
            f"inadequate bone marrow function."
        ),
        severity=classify("INC-04", protocol),
        detected_date=collection_date,
        visit_id=visit_id,
        evidence={
            "rule": "INC-04",
            "anc_value": anc_value,
            "required_min": min_anc,
            "unit": "x10^9/L",
        },
    )]


# ─────────────────────────────────────────────────────────────────────────────
# Facade: evaluate a single patient (pure, no DB)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_patient(
    *,
    # Patient scalar fields
    patient_id: str,
    site_id: str,
    enrollment_date: date,
    age: int,
    ecog_score: int | None,
    diagnosis_confirmed: bool,
    prior_egfr_alk_treatment_days: int | None,
    active_infection: bool,
    pregnant_or_breastfeeding: bool,
    consent_signed_before_procedure: bool,
    # Visits: list of dicts with keys: id, number, name, scheduled_date, actual_date,
    #         window_deviation_days, completed_assessments_json
    visits: list[dict],
    # Lab results: list of dicts with keys: visit_id, test_name, value, collection_date
    lab_results: list[dict],
    # Adverse events: list of dicts with keys: id, description, onset_date,
    #                 reported_date, reporting_delay_hours, sae_flag
    adverse_events: list[dict],
    protocol: Protocol,
) -> list[DeviationResult]:
    """
    Evaluate all rule categories for a single patient.

    This function is pure (no side effects).  It calls all individual evaluators
    and returns a deduplicated list of DeviationResult objects.

    Deduplication uses the (patient_id, rule_id, visit_id) key; within a single
    evaluation pass duplicates should not occur, but this guards against
    accidental double-evaluation.
    """
    all_results: list[DeviationResult] = []

    # 1. Eligibility
    all_results.extend(evaluate_eligibility(
        patient_id=patient_id,
        site_id=site_id,
        enrollment_date=enrollment_date,
        age=age,
        ecog_score=ecog_score,
        diagnosis_confirmed=diagnosis_confirmed,
        prior_egfr_alk_treatment_days=prior_egfr_alk_treatment_days,
        active_infection=active_infection,
        pregnant_or_breastfeeding=pregnant_or_breastfeeding,
        consent_signed_before_procedure=consent_signed_before_procedure,
        protocol=protocol,
    ))

    # 2. Visit window + missing assessments + lab thresholds
    visit_ids_with_screening: set[int] = set()
    for v in visits:
        vnum = v["visit_number"]
        vid = v["id"]
        sched = v["scheduled_date"]
        actual = v["actual_date"]
        vname = v["visit_name"]

        all_results.extend(evaluate_visit_window(
            patient_id=patient_id,
            site_id=site_id,
            visit_id=vid,
            visit_number=vnum,
            visit_name=vname,
            scheduled_date=sched,
            actual_date=actual,
            protocol=protocol,
        ))

        all_results.extend(evaluate_missing_assessments(
            patient_id=patient_id,
            site_id=site_id,
            visit_id=vid,
            visit_number=vnum,
            visit_name=vname,
            actual_date=actual,
            completed_assessments_json=v.get("completed_assessments_json"),
            protocol=protocol,
        ))

        if vnum == 1:
            visit_ids_with_screening.add(vid)

    # 3. Lab results
    for lr in lab_results:
        all_results.extend(evaluate_lab_result(
            patient_id=patient_id,
            site_id=site_id,
            visit_id=lr["visit_id"],
            test_name=lr["test_name"],
            value=lr["value"],
            collection_date=lr["collection_date"],
            protocol=protocol,
        ))

        # INC-04: ANC at screening visit
        if lr["test_name"] == "anc" and lr["visit_id"] in visit_ids_with_screening:
            all_results.extend(evaluate_inc04_anc(
                patient_id=patient_id,
                site_id=site_id,
                visit_id=lr["visit_id"],
                anc_value=lr["value"],
                collection_date=lr["collection_date"],
                protocol=protocol,
            ))

    # 4. SAE reporting
    for ae in adverse_events:
        all_results.extend(evaluate_sae_reporting(
            patient_id=patient_id,
            site_id=site_id,
            ae_id=ae["id"],
            description=ae["description"],
            onset_date=ae["onset_date"],
            reported_date=ae["reported_date"],
            reporting_delay_hours=ae["reporting_delay_hours"],
            sae_flag=ae["sae_flag"],
            protocol=protocol,
        ))

    # Deduplicate within this evaluation pass
    seen: set[tuple] = set()
    deduped: list[DeviationResult] = []
    for result in all_results:
        key = result.dedup_key()
        if key not in seen:
            seen.add(key)
            deduped.append(result)

    return deduped
