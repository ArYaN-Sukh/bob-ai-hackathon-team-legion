"""
SQLAlchemy ORM models for TrialGuard.

IMPORTANT: All data represented here is entirely synthetic and is used
solely for the IBM Bob AI Hackathon demo.  No real patient or clinical data
is stored or processed by this application.

Entity hierarchy:
  ClinicalTrial
    └── Site (1:N)
          └── Patient (1:N)
                ├── Visit (1:N)
                │     └── LabResult (1:N)
                └── AdverseEvent (1:N)
  Deviation  (links Patient + Visit + Site)
  CAPA       (links Deviation + Site)
  SiteRiskScore (links Site)
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.backend.db import Base


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class DeviationSeverity(str, enum.Enum):
    MAJOR = "Major"
    MINOR = "Minor"
    ADMINISTRATIVE = "Administrative"


class DeviationStatus(str, enum.Enum):
    OPEN = "Open"
    CLOSED = "Closed"
    PENDING_REVIEW = "Pending Review"


class CAPAStatus(str, enum.Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    CLOSED = "Closed"
    OVERDUE = "Overdue"


class RiskTier(str, enum.Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SiteStatus(str, enum.Enum):
    ACTIVE = "Active"
    CLOSED = "Closed"
    ON_HOLD = "On Hold"


class PatientStatus(str, enum.Enum):
    ENROLLED = "Enrolled"
    COMPLETED = "Completed"
    WITHDRAWN = "Withdrawn"
    SCREEN_FAILED = "Screen Failed"


class VisitType(str, enum.Enum):
    SCHEDULED = "Scheduled"
    UNSCHEDULED = "Unscheduled"
    FOLLOW_UP = "Follow-Up"


# ─────────────────────────────────────────────────────────────────────────────
# ClinicalTrial
# ─────────────────────────────────────────────────────────────────────────────

class ClinicalTrial(Base):
    """Top-level trial entity.  One per demo dataset."""
    __tablename__ = "clinical_trials"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    """Protocol-assigned trial identifier, e.g. 'TRIAL-TG-001'."""

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol_version: Mapped[str] = mapped_column(String(20), nullable=False)
    sponsor: Mapped[str] = mapped_column(String(255), nullable=False)
    phase: Mapped[str] = mapped_column(String(10), nullable=False)
    indication: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=True)
    target_enrollment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    primary_endpoint: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    sites: Mapped[list["Site"]] = relationship("Site", back_populates="trial", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ClinicalTrial id={self.id!r} name={self.name!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Site
# ─────────────────────────────────────────────────────────────────────────────

class Site(Base):
    """Clinical research site.  Each site enrolls patients."""
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    """Human-readable site code, e.g. 'SITE-003'."""

    trial_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("clinical_trials.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    principal_investigator: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[SiteStatus] = mapped_column(
        Enum(SiteStatus), nullable=False, default=SiteStatus.ACTIVE
    )
    enrolled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_enrollment: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    activation_date: Mapped[date] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    trial: Mapped["ClinicalTrial"] = relationship("ClinicalTrial", back_populates="sites")
    patients: Mapped[list["Patient"]] = relationship("Patient", back_populates="site", cascade="all, delete-orphan")
    deviations: Mapped[list["Deviation"]] = relationship("Deviation", back_populates="site")
    risk_scores: Mapped[list["SiteRiskScore"]] = relationship("SiteRiskScore", back_populates="site", cascade="all, delete-orphan")
    capas: Mapped[list["CAPA"]] = relationship("CAPA", back_populates="site")

    __table_args__ = (
        Index("ix_sites_trial_id", "trial_id"),
    )

    def __repr__(self) -> str:
        return f"<Site id={self.id!r} name={self.name!r} country={self.country!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Patient
# ─────────────────────────────────────────────────────────────────────────────

class Patient(Base):
    """
    Synthetic patient enrolled in the trial.
    All identifiers are fictitious and not linked to any real individual.
    """
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    """Protocol subject identifier, e.g. 'PT-0042'."""

    site_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    trial_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("clinical_trials.id", ondelete="CASCADE"), nullable=False
    )

    # Demographics (synthetic)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[str] = mapped_column(String(10), nullable=False)  # M / F / Other

    # Clinical eligibility fields
    ecog_score: Mapped[int] = mapped_column(Integer, nullable=True)
    """ECOG Performance Status score (0–4). Checked against INC-02."""

    diagnosis_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    """Whether NSCLC diagnosis was histologically/cytologically confirmed. INC-03."""

    prior_egfr_alk_treatment_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Days since last EGFR/ALK inhibitor treatment. EXC-01 requires >= 28."""

    active_infection: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """EXC-02: must be False for enrollment."""

    pregnant_or_breastfeeding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """EXC-03: must be False for enrollment."""

    consent_signed_before_procedure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    """INC-05: ICF must be signed before any study procedure."""

    # Enrollment
    enrollment_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PatientStatus] = mapped_column(
        Enum(PatientStatus), nullable=False, default=PatientStatus.ENROLLED
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="patients")
    visits: Mapped[list["Visit"]] = relationship("Visit", back_populates="patient", cascade="all, delete-orphan", order_by="Visit.visit_number")
    adverse_events: Mapped[list["AdverseEvent"]] = relationship("AdverseEvent", back_populates="patient", cascade="all, delete-orphan")
    deviations: Mapped[list["Deviation"]] = relationship("Deviation", back_populates="patient")

    __table_args__ = (
        Index("ix_patients_site_id", "site_id"),
        Index("ix_patients_trial_id", "trial_id"),
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id!r} age={self.age} site={self.site_id!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Visit
# ─────────────────────────────────────────────────────────────────────────────

class Visit(Base):
    """A single protocol-defined or unscheduled visit for a patient."""
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )

    visit_number: Mapped[int] = mapped_column(Integer, nullable=False)
    """Corresponds to visit_schedule[].visit_number in the protocol."""

    visit_name: Mapped[str] = mapped_column(String(100), nullable=False)
    visit_type: Mapped[VisitType] = mapped_column(
        Enum(VisitType), nullable=False, default=VisitType.SCHEDULED
    )

    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Null if the visit has not yet occurred."""

    window_deviation_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """
    Computed at analysis time: actual_date - scheduled_date in days.
    Positive = late, Negative = early.  Null until analysis runs.
    """

    completed_assessments: Mapped[str | None] = mapped_column(Text, nullable=True)
    """JSON array of assessment names completed at this visit, e.g. '["vitals","ecg"]'."""

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="visits")
    lab_results: Mapped[list["LabResult"]] = relationship("LabResult", back_populates="visit", cascade="all, delete-orphan")
    deviations: Mapped[list["Deviation"]] = relationship("Deviation", back_populates="visit")

    __table_args__ = (
        Index("ix_visits_patient_id", "patient_id"),
        Index("ix_visits_site_id", "site_id"),
    )

    def __repr__(self) -> str:
        return f"<Visit id={self.id} patient={self.patient_id!r} visit_number={self.visit_number} actual={self.actual_date}>"


# ─────────────────────────────────────────────────────────────────────────────
# LabResult
# ─────────────────────────────────────────────────────────────────────────────

class LabResult(Base):
    """A single laboratory test result recorded at a visit."""
    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    visit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("visits.id", ondelete="CASCADE"), nullable=False
    )

    test_name: Mapped[str] = mapped_column(String(100), nullable=False)
    """Matches test_name in protocol.lab_thresholds, e.g. 'hemoglobin'."""

    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    collection_date: Mapped[date] = mapped_column(Date, nullable=False)

    is_out_of_range: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """Pre-computed flag.  True if value violates protocol lab threshold."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    visit: Mapped["Visit"] = relationship("Visit", back_populates="lab_results")

    __table_args__ = (
        Index("ix_lab_results_patient_id", "patient_id"),
        Index("ix_lab_results_visit_id", "visit_id"),
    )

    def __repr__(self) -> str:
        return f"<LabResult id={self.id} test={self.test_name!r} value={self.value} patient={self.patient_id!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# AdverseEvent
# ─────────────────────────────────────────────────────────────────────────────

class AdverseEvent(Base):
    """An adverse event or serious adverse event recorded for a patient."""
    __tablename__ = "adverse_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    onset_date: Mapped[date] = mapped_column(Date, nullable=False)

    sae_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """True if classified as a Serious Adverse Event requiring 24-hour reporting."""

    expected_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    """True if the AE is listed in the Investigator's Brochure as expected."""

    reported_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Date the SAE was reported to the Sponsor.  Null if not yet reported."""

    reporting_delay_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    """
    Computed: hours between onset_date and reported_date.
    REP-01 requires this to be <= 24 for SAEs.
    """

    severity_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """CTCAE grade 1–5."""

    outcome: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="adverse_events")

    __table_args__ = (
        Index("ix_adverse_events_patient_id", "patient_id"),
        Index("ix_adverse_events_site_id", "site_id"),
        Index("ix_adverse_events_sae_flag", "sae_flag"),
    )

    def __repr__(self) -> str:
        return f"<AdverseEvent id={self.id} patient={self.patient_id!r} sae={self.sae_flag} reported={self.reported_date}>"


# ─────────────────────────────────────────────────────────────────────────────
# Deviation
# ─────────────────────────────────────────────────────────────────────────────

class Deviation(Base):
    """
    A detected protocol deviation.  Written by the deviation engine (deterministic).
    Severity is assigned from the protocol rule definition, never inferred by AI.
    """
    __tablename__ = "deviations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    visit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("visits.id", ondelete="SET NULL"), nullable=True
    )
    site_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )

    rule_id: Mapped[str] = mapped_column(String(20), nullable=False)
    """Protocol rule that was violated, e.g. 'INC-01'."""

    deviation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    """Category: 'Eligibility', 'Visit Window', 'Missing Assessment', 'Lab Threshold', 'SAE Reporting', 'Dosing'."""

    description: Mapped[str] = mapped_column(Text, nullable=False)
    """Human-readable description of the specific deviation detected."""

    severity: Mapped[DeviationSeverity] = mapped_column(
        Enum(DeviationSeverity), nullable=False
    )
    """Assigned from protocol rule definition.  Never inferred by AI."""

    status: Mapped[DeviationStatus] = mapped_column(
        Enum(DeviationStatus), nullable=False, default=DeviationStatus.OPEN
    )

    detected_date: Mapped[date] = mapped_column(Date, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    """JSON blob of supporting evidence fields, e.g. actual vs expected values."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="deviations")
    visit: Mapped["Visit | None"] = relationship("Visit", back_populates="deviations")
    site: Mapped["Site"] = relationship("Site", back_populates="deviations")
    capa: Mapped["CAPA | None"] = relationship("CAPA", back_populates="deviation", uselist=False)

    __table_args__ = (
        Index("ix_deviations_site_id", "site_id"),
        Index("ix_deviations_patient_id", "patient_id"),
        Index("ix_deviations_severity", "severity"),
        Index("ix_deviations_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Deviation id={self.id} rule={self.rule_id!r} severity={self.severity.value!r} patient={self.patient_id!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# CAPA
# ─────────────────────────────────────────────────────────────────────────────

class CAPA(Base):
    """
    Corrective and Preventive Action record.
    The watsonx_narrative field is populated by the AI CAPA generator.
    All other fields are filled by investigators or the seed script.
    """
    __tablename__ = "capas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deviation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deviations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    site_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )

    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrective_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    preventive_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    watsonx_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    """AI-generated narrative from watsonx.ai.  Null until generate_capa is called."""

    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """Source of the narrative: 'watsonx' or 'fallback'."""

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[CAPAStatus] = mapped_column(
        Enum(CAPAStatus), nullable=False, default=CAPAStatus.OPEN
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    deviation: Mapped["Deviation"] = relationship("Deviation", back_populates="capa")
    site: Mapped["Site"] = relationship("Site", back_populates="capas")

    __table_args__ = (
        Index("ix_capas_site_id", "site_id"),
        Index("ix_capas_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<CAPA id={self.id} deviation_id={self.deviation_id} status={self.status.value!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# SiteRiskScore
# ─────────────────────────────────────────────────────────────────────────────

class SiteRiskScore(Base):
    """
    Snapshot of a site's computed risk score on a given date.
    Calculated by the risk scorer engine — not by AI.

    Score formula (see engine/risk_scorer.py):
      (major_open * 10) + (minor_open * 3) + (admin_open * 1)
      + (avg_capa_age_days/30 * 5)
      + (data_query_rate_pct * 2)
      + (enrollment_deviation_pct * 2)

    Tiers: >= 60 = High | 30-59 = Medium | < 30 = Low
    """
    __tablename__ = "site_risk_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    score_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Score components (inputs to formula)
    major_open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minor_open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    admin_open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_capa_age_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    data_query_rate_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    enrollment_deviation_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Computed results
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_tier: Mapped[RiskTier] = mapped_column(
        Enum(RiskTier), nullable=False, default=RiskTier.LOW
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="risk_scores")

    __table_args__ = (
        Index("ix_site_risk_scores_site_id", "site_id"),
        Index("ix_site_risk_scores_score_date", "score_date"),
    )

    def __repr__(self) -> str:
        return f"<SiteRiskScore id={self.id} site={self.site_id!r} score={self.total_score} tier={self.risk_tier.value!r} date={self.score_date}>"
