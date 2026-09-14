"""
Site-level risk scorer for TrialGuard.

FORMULA
-------

    risk_score =
        (major_open_deviations   × 10)
      + (minor_open_deviations   ×  3)
      + (admin_open_deviations   ×  1)
      + (avg_capa_age_days / 30  ×  5)   [CAPA age in months × 5]
      + enrollment_risk_points           [0–10; see below]
      + data_query_risk_points           [0–10; see below]

Risk tiers:
    score >= 60  →  High
    30 <= score < 60  →  Medium
    score <  30  →  Low

ENROLLMENT RISK (leading indicator, capped at 10 pts)
------------------------------------------------------
Under-enrollment on its own is a *leading indicator* of site problems
(insufficient staffing, screening failures, patient hesitancy) — but a site
that is 50% below its enrollment target is NOT equivalent to a site with 6
open Major deviations.  The old formula gave 100 pts to any site at 50%
enrollment, drowning out all compliance signals.

New design:
  * Below 10% deviation from target → 0 points (within normal variance)
  * 10–30% deviation               → scaled linearly from 0 to 5 points
  * 30–50% deviation               → scaled linearly from 5 to 8 points
  * Above 50% deviation            → capped at 10 points (severe concern)

This gives at most 10 pts for enrollment, preserving it as a meaningful
signal without ever making it the dominant factor.

DATA QUERY RATE (leading indicator, capped at 10 pts)
-----------------------------------------------------
The data-query rate (% of patients with open deviations) is also a leading
indicator of site data quality.  Previously it was multiplied by 2 unbounded,
giving 200 pts when every patient has any open deviation.

New design: linearly map 0–100% onto 0–10 points (rate / 10.0), capped at 10.
A site where every patient has an open deviation gets exactly 10 pts — meaningful
but not overwhelming.

BACKWARD COMPATIBILITY
----------------------
The SiteInputs and SiteRiskScore schemas are unchanged.  The `enrollment_deviation_pct`
and `data_query_rate_pct` fields still carry the raw percentages; only the
formula that converts them to score contributions changes.  Callers (IBM Bob,
dashboard) can still display the raw percentages for transparency.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.backend.models import RiskTier


# ─────────────────────────────────────────────────────────────────────────────
# Tier thresholds (named constants for tests and explanations)
# ─────────────────────────────────────────────────────────────────────────────

HIGH_THRESHOLD: float = 60.0
MEDIUM_THRESHOLD: float = 30.0

# Deviation severity weights
WEIGHT_MAJOR: float = 10.0
WEIGHT_MINOR: float = 3.0
WEIGHT_ADMIN: float = 1.0

# CAPA age: each full month an open deviation goes without a CAPA adds 5 pts
WEIGHT_CAPA_AGE_PER_MONTH: float = 5.0

# Maximum contributions from the two leading-indicator components
MAX_ENROLLMENT_CONTRIBUTION: float = 10.0
MAX_DATA_QUERY_CONTRIBUTION: float = 10.0

# Enrollment risk thresholds (percentage points)
ENROLL_LOW_THRESHOLD: float = 10.0   # < 10% dev → no risk signal
ENROLL_MID_THRESHOLD: float = 30.0   # 10–30% → moderate risk
ENROLL_HIGH_THRESHOLD: float = 50.0  # 30–50% → elevated risk; >50% → capped at max

# These two weights are kept for backward compatibility with tests that
# call the old enrollment_deviation_pct * WEIGHT_ENROLLMENT_DEVIATION pattern.
# They are NOT used in score_site().  The formula now calls
# compute_enrollment_risk_points() and compute_data_query_risk_points() instead.
WEIGHT_ENROLLMENT_DEVIATION: float = 2.0   # legacy; no longer applied directly
WEIGHT_DATA_QUERY_RATE: float = 2.0        # legacy; no longer applied directly


# ─────────────────────────────────────────────────────────────────────────────
# Input/output dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SiteInputs:
    """
    Inputs to the risk score formula.

    All fields correspond directly to a SiteRiskScore column so the scorer
    output can be persisted without transformation.
    """

    site_id: str
    major_open_count: int
    minor_open_count: int
    admin_open_count: int
    avg_capa_age_days: float
    """Average age in days of open Major/Minor deviations (CAPA-age proxy).
    0.0 if no open deviations."""
    data_query_rate_pct: float
    """Percentage of patients at this site with >= 1 open deviation (0–100).
    Used as a data-quality leading indicator."""
    enrollment_deviation_pct: float
    """
    Absolute percentage deviation from target enrollment (0–100+).
    e.g., site enrolled 8 of 20 target → (20-8)/20 * 100 = 60.0
    abs() applied so over-enrollment is also captured.
    """


@dataclass(frozen=True)
class SiteRiskResult:
    """
    Output of the risk scorer for one site.

    Each component field shows its individual contribution to the total so
    the dashboard and IBM Bob can explain the score.
    """

    site_id: str
    total_score: float
    risk_tier: RiskTier

    # Score components (contribution of each factor)
    major_contribution: float
    minor_contribution: float
    admin_contribution: float
    capa_age_contribution: float
    data_query_contribution: float
    enrollment_contribution: float

    # Raw inputs (for display / explanation)
    major_open_count: int
    minor_open_count: int
    admin_open_count: int
    avg_capa_age_days: float
    data_query_rate_pct: float
    enrollment_deviation_pct: float


# ─────────────────────────────────────────────────────────────────────────────
# Enrollment and data-query risk helpers
# ─────────────────────────────────────────────────────────────────────────────

def compute_enrollment_risk_points(enrollment_deviation_pct: float) -> float:
    """
    Map a raw enrollment deviation percentage to a bounded risk contribution.

    The mapping is piecewise linear with a hard cap:

      deviation < 10%   →  0.0 pts   (within normal variance, no signal)
      10% – 30%         →  0.0–5.0   (linear: mild concern)
      30% – 50%         →  5.0–8.0   (linear: material concern)
      > 50%             →  capped at MAX_ENROLLMENT_CONTRIBUTION (10.0)

    This ensures enrollment never contributes more than 10 pts so it cannot
    dominate a site's score on its own.

    Parameters
    ----------
    enrollment_deviation_pct : float
        Absolute percentage deviation from target (0–100+).

    Returns
    -------
    float
        Risk contribution in [0.0, MAX_ENROLLMENT_CONTRIBUTION].
    """
    dev = max(0.0, enrollment_deviation_pct)

    if dev < ENROLL_LOW_THRESHOLD:
        return 0.0

    if dev < ENROLL_MID_THRESHOLD:
        # Linear from 0 to 5 over [10, 30]
        t = (dev - ENROLL_LOW_THRESHOLD) / (ENROLL_MID_THRESHOLD - ENROLL_LOW_THRESHOLD)
        return round(t * 5.0, 4)

    if dev < ENROLL_HIGH_THRESHOLD:
        # Linear from 5 to 8 over [30, 50]
        t = (dev - ENROLL_MID_THRESHOLD) / (ENROLL_HIGH_THRESHOLD - ENROLL_MID_THRESHOLD)
        return round(5.0 + t * 3.0, 4)

    # Severe deviation (>= 50%)
    return MAX_ENROLLMENT_CONTRIBUTION


def compute_data_query_risk_points(data_query_rate_pct: float) -> float:
    """
    Map a raw data-query rate percentage to a bounded risk contribution.

    Linear mapping: rate / 10.0, capped at MAX_DATA_QUERY_CONTRIBUTION (10.0).

    Example:
      0%  → 0 pts
      50% → 5 pts
      100% → 10 pts (cap)

    Parameters
    ----------
    data_query_rate_pct : float
        Percentage of patients with >= 1 open deviation (0–100).

    Returns
    -------
    float
        Risk contribution in [0.0, MAX_DATA_QUERY_CONTRIBUTION].
    """
    raw = max(0.0, data_query_rate_pct) / 10.0
    return round(min(raw, MAX_DATA_QUERY_CONTRIBUTION), 4)


def compute_enrollment_deviation_pct(enrolled: int, target: int) -> float:
    """
    Compute the absolute enrollment deviation as a percentage of target.

    Returns 0.0 if target is 0 (avoids ZeroDivisionError).
    """
    if target <= 0:
        return 0.0
    return abs(target - enrolled) / target * 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Core scoring function
# ─────────────────────────────────────────────────────────────────────────────

def score_site(inputs: SiteInputs) -> SiteRiskResult:
    """
    Calculate the risk score for a single site.

    Parameters
    ----------
    inputs : SiteInputs
        All inputs to the scoring formula.

    Returns
    -------
    SiteRiskResult
        Fully-explained result with per-component contributions and risk tier.
    """
    major_contrib = inputs.major_open_count * WEIGHT_MAJOR
    minor_contrib = inputs.minor_open_count * WEIGHT_MINOR
    admin_contrib = inputs.admin_open_count * WEIGHT_ADMIN

    # CAPA age in months (days / 30), zero if no open deviations
    capa_months = inputs.avg_capa_age_days / 30.0 if inputs.avg_capa_age_days > 0 else 0.0
    capa_contrib = capa_months * WEIGHT_CAPA_AGE_PER_MONTH

    # Bounded leading indicators
    enroll_contrib = compute_enrollment_risk_points(inputs.enrollment_deviation_pct)
    dq_contrib = compute_data_query_risk_points(inputs.data_query_rate_pct)

    total = (
        major_contrib
        + minor_contrib
        + admin_contrib
        + capa_contrib
        + enroll_contrib
        + dq_contrib
    )

    tier = _tier(total)

    return SiteRiskResult(
        site_id=inputs.site_id,
        total_score=round(total, 2),
        risk_tier=tier,
        major_contribution=round(major_contrib, 2),
        minor_contribution=round(minor_contrib, 2),
        admin_contribution=round(admin_contrib, 2),
        capa_age_contribution=round(capa_contrib, 2),
        data_query_contribution=round(dq_contrib, 2),
        enrollment_contribution=round(enroll_contrib, 2),
        major_open_count=inputs.major_open_count,
        minor_open_count=inputs.minor_open_count,
        admin_open_count=inputs.admin_open_count,
        avg_capa_age_days=inputs.avg_capa_age_days,
        data_query_rate_pct=inputs.data_query_rate_pct,
        enrollment_deviation_pct=inputs.enrollment_deviation_pct,
    )


def _tier(score: float) -> RiskTier:
    """Map a numeric score to a RiskTier."""
    if score >= HIGH_THRESHOLD:
        return RiskTier.HIGH
    if score >= MEDIUM_THRESHOLD:
        return RiskTier.MEDIUM
    return RiskTier.LOW
