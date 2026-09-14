"""
Pydantic response/request schemas for the TrialGuard API.

These are separate from the SQLAlchemy ORM models (models.py) so that the
API shapes can evolve independently from the database layout.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ─────────────────────────────────────────────────────────────────────────────
# Shared config mixin
# ─────────────────────────────────────────────────────────────────────────────

class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# Trial
# ─────────────────────────────────────────────────────────────────────────────

class TrialOut(_Base):
    id: str
    name: str
    protocol_version: str
    sponsor: str
    phase: str
    indication: str
    start_date: date
    end_date: Optional[date]
    target_enrollment: int
    primary_endpoint: Optional[str]
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Site
# ─────────────────────────────────────────────────────────────────────────────

class SiteOut(_Base):
    id: str
    trial_id: str
    name: str
    city: Optional[str]
    country: str
    principal_investigator: str
    status: str
    enrolled_count: int
    target_enrollment: int
    activation_date: Optional[date]
    created_at: datetime


class SiteWithRisk(SiteOut):
    """Site summary including latest risk score data."""
    latest_risk_score: Optional[float] = None
    latest_risk_tier: Optional[str] = None
    open_major_count: int = 0
    open_minor_count: int = 0
    open_admin_count: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# SiteRiskScore
# ─────────────────────────────────────────────────────────────────────────────

class SiteRiskScoreOut(_Base):
    id: int
    site_id: str
    score_date: date
    major_open_count: int
    minor_open_count: int
    admin_open_count: int
    avg_capa_age_days: float
    data_query_rate_pct: float
    enrollment_deviation_pct: float
    total_score: float
    risk_tier: str
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Patient
# ─────────────────────────────────────────────────────────────────────────────

class PatientOut(_Base):
    id: str
    site_id: str
    trial_id: str
    age: int
    sex: str
    ecog_score: Optional[int]
    diagnosis_confirmed: bool
    prior_egfr_alk_treatment_days: Optional[int]
    active_infection: bool
    pregnant_or_breastfeeding: bool
    consent_signed_before_procedure: bool
    enrollment_date: date
    status: str
    created_at: datetime


class PatientSummary(_Base):
    """Lightweight patient card used in site detail views."""
    id: str
    site_id: str
    age: int
    sex: str
    status: str
    enrollment_date: date
    open_deviation_count: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Visit
# ─────────────────────────────────────────────────────────────────────────────

class VisitOut(_Base):
    id: int
    patient_id: str
    site_id: str
    visit_number: int
    visit_name: str
    visit_type: str
    scheduled_date: date
    actual_date: Optional[date]
    window_deviation_days: Optional[int]
    completed_assessments: Optional[Any]
    notes: Optional[str]
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Lab Result
# ─────────────────────────────────────────────────────────────────────────────

class LabResultOut(_Base):
    id: int
    patient_id: str
    visit_id: int
    test_name: str
    display_name: str
    value: float
    unit: str
    reference_low: Optional[float]
    reference_high: Optional[float]
    collection_date: date
    is_out_of_range: bool
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Adverse Event
# ─────────────────────────────────────────────────────────────────────────────

class AdverseEventOut(_Base):
    id: int
    patient_id: str
    site_id: str
    description: str
    onset_date: date
    sae_flag: bool
    expected_flag: bool
    reported_date: Optional[date]
    reporting_delay_hours: Optional[float]
    severity_grade: Optional[int]
    outcome: Optional[str]
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Deviation
# ─────────────────────────────────────────────────────────────────────────────

class DeviationOut(_Base):
    id: int
    patient_id: str
    visit_id: Optional[int]
    site_id: str
    rule_id: str
    deviation_type: str
    description: str
    severity: str
    status: str
    detected_date: date
    evidence: Optional[str]
    created_at: datetime
    updated_at: datetime


class DeviationUpdate(BaseModel):
    status: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# CAPA
# ─────────────────────────────────────────────────────────────────────────────

class CapaOut(_Base):
    id: int
    deviation_id: int
    site_id: str
    root_cause: Optional[str]
    corrective_action: Optional[str]
    preventive_action: Optional[str]
    watsonx_narrative: Optional[str]
    source: Optional[str]  # "watsonx" | "fallback"
    due_date: Optional[date]
    closed_date: Optional[date]
    status: str
    created_at: datetime
    updated_at: datetime


class CapaUpdate(BaseModel):
    root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    preventive_action: Optional[str] = None
    due_date: Optional[date] = None
    closed_date: Optional[date] = None
    status: Optional[str] = None


class CapaGenerateRequest(BaseModel):
    deviation_id: int


class CapaGenerateResponse(BaseModel):
    capa_id: int
    deviation_id: int
    narrative: str
    source: str  # "watsonx" | "fallback"


# ─────────────────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisRunResponse(BaseModel):
    deviations_created: int
    total_open_deviations: int
    sites_scored: int
    site_risk_summary: list[dict]


class PatientAnalyseResponse(BaseModel):
    patient_id: str
    deviations_created: int
    total_open_deviations: int


# ─────────────────────────────────────────────────────────────────────────────
# Patient Timeline
# ─────────────────────────────────────────────────────────────────────────────

class TimelineVisit(BaseModel):
    visit_id: int
    visit_number: int
    visit_name: str
    scheduled_date: date
    actual_date: Optional[date]
    window_deviation_days: Optional[int]
    deviations: list[DeviationOut] = []
    lab_results: list[LabResultOut] = []


class PatientTimeline(BaseModel):
    patient: PatientOut
    visits: list[TimelineVisit]
    all_deviations: list[DeviationOut]
    adverse_events: list[AdverseEventOut]


# ─────────────────────────────────────────────────────────────────────────────
# Site Report
# ─────────────────────────────────────────────────────────────────────────────

class SiteReportResponse(BaseModel):
    site_id: str
    report_markdown: str
    generated_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Misc / health
# ─────────────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    protocol_loaded: bool
