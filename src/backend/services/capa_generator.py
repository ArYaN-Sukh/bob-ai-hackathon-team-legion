"""
CAPA Narrative Generator for TrialGuard.

Builds a structured prompt from a Deviation + site context and calls
watsonx.ai to generate a CAPA (Corrective and Preventive Action) narrative.

If watsonx.ai is unavailable (no API key, network error), a deterministic
fallback template is returned so the UI always shows something useful.

Architecture note:
    The CAPA *narrative* is AI-generated text.
    The deviation *detection* and *severity classification* are deterministic.
    These two layers are intentionally separated.
"""
from __future__ import annotations

import logging
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.backend.models import Deviation, Site, SiteRiskScore

logger = logging.getLogger(__name__)

# Literal type for the source field in the response
CapaSource = Literal["watsonx", "fallback"]


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
You are a Clinical Research Associate (CRA) writing a formal CAPA report for a \
clinical trial protocol deviation.

TRIAL CONTEXT
=============
Trial: Phase II Study of Compound XR-447 in Advanced Non-Small Cell Lung Cancer
Site: {site_name} ({site_city}, {site_country})
Principal Investigator: {pi}
Current Site Risk Tier: {risk_tier}
Open Major Deviations at Site: {major_count}

DEVIATION DETAILS
=================
Patient ID: {patient_id}
Rule ID: {rule_id}
Deviation Type: {deviation_type}
Severity: {severity}
Description: {description}
Detected Date: {detected_date}
Evidence: {evidence}

INSTRUCTIONS
============
Write a structured CAPA report with the following three sections:

1. ROOT CAUSE ANALYSIS
   Identify the most likely root cause of this deviation. Consider procedural, \
training, and systemic factors.

2. CORRECTIVE ACTION
   Describe the immediate action to resolve this specific deviation and prevent \
recurrence in the short term.

3. PREVENTIVE ACTION
   Describe the systemic change to prevent similar deviations at this site and \
across the trial.

Format each section with a clear heading. Be specific, use clinical operations \
terminology, and limit the total response to 400 words.
"""


def _build_prompt(db: Session, dev: Deviation) -> str:
    site = db.query(Site).filter(Site.id == dev.site_id).first()

    # Latest risk score for site context
    risk = (
        db.query(SiteRiskScore)
        .filter(SiteRiskScore.site_id == dev.site_id)
        .order_by(SiteRiskScore.score_date.desc())
        .first()
    )

    return _PROMPT_TEMPLATE.format(
        site_name=site.name if site else dev.site_id,
        site_city=site.city if site else "Unknown",
        site_country=site.country if site else "Unknown",
        pi=site.principal_investigator if site else "Unknown",
        risk_tier=(risk.risk_tier if risk else "Unknown"),
        major_count=(risk.major_open_count if risk else "Unknown"),
        patient_id=dev.patient_id,
        rule_id=dev.rule_id,
        deviation_type=dev.deviation_type,
        severity=dev.severity,
        description=dev.description,
        detected_date=dev.detected_date,
        evidence=(dev.evidence or "Not documented"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fallback template
# ─────────────────────────────────────────────────────────────────────────────

_FALLBACK_TEMPLATE = """\
1. ROOT CAUSE ANALYSIS
Site staff may not have been adequately trained on the specific protocol \
requirement defined by rule {rule_id} ({deviation_type}). Additionally, \
the site's quality management system may lack a review step to detect \
this type of deviation before it is reported.

2. CORRECTIVE ACTION
Immediately review and document the deviation with the Principal Investigator. \
Confirm whether patient {patient_id} requires any remedial clinical action. \
Update the patient's source document to reflect the protocol deviation and \
notify the sponsor's medical monitor within 5 business days.

3. PREVENTIVE ACTION
Schedule a targeted training session for all site staff on the protocol \
requirements covered by rule {rule_id}. Update the site's deviation log SOP \
to include a pre-visit checklist item for this requirement. A follow-up \
monitoring visit should be scheduled within 30 days to verify compliance \
across all active patients at this site.

[Note: This CAPA was generated from a fallback template. \
Configure WATSONX_API_KEY to enable AI-generated CAPA narratives.]
"""


def _fallback_narrative(dev: Deviation) -> str:
    return _FALLBACK_TEMPLATE.format(
        rule_id=dev.rule_id,
        deviation_type=dev.deviation_type,
        patient_id=dev.patient_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_capa_narrative(
    db: Session,
    dev: Deviation,
) -> tuple[str, CapaSource]:
    """
    Generate a CAPA narrative for the given deviation.

    Attempts to call watsonx.ai. If watsonx.ai is unavailable or returns an
    error, falls back to the deterministic template.

    Returns
    -------
    tuple[str, CapaSource]
        (narrative_text, source)  where source is "watsonx" or "fallback".
    """
    from src.backend.services.watsonx_client import (
        WatsonxAPIError,
        WatsonxUnavailableError,
        generate_text,
    )

    try:
        prompt = _build_prompt(db, dev)
        narrative = generate_text(prompt)
        logger.info(
            "watsonx.ai CAPA generated for deviation %s (patient %s)",
            dev.id, dev.patient_id,
        )
        return narrative, "watsonx"

    except WatsonxUnavailableError:
        logger.info(
            "watsonx.ai not configured — using fallback CAPA for deviation %s",
            dev.id,
        )
        return _fallback_narrative(dev), "fallback"

    except WatsonxAPIError as exc:
        logger.warning(
            "watsonx.ai API error for deviation %s: %s — falling back",
            dev.id, exc,
        )
        return _fallback_narrative(dev), "fallback"

    except Exception as exc:
        logger.error(
            "Unexpected error during CAPA generation for deviation %s: %s",
            dev.id, exc, exc_info=True,
        )
        return _fallback_narrative(dev), "fallback"
