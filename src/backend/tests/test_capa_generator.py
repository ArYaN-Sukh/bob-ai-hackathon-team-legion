"""
Tests for the CAPA generator service.

All watsonx.ai calls are mocked — no real API calls are made.
"""
from __future__ import annotations

import datetime
import pytest
from unittest.mock import MagicMock, patch

from src.backend.services.capa_generator import (
    _fallback_narrative,
    generate_capa_narrative,
)
from src.backend.models import CAPA, CAPAStatus, Deviation, DeviationSeverity, DeviationStatus


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_deviation():
    dev = MagicMock(spec=Deviation)
    dev.id = 42
    dev.patient_id = "PT-0042"
    dev.site_id = "SITE-003"
    dev.rule_id = "INC-01"
    dev.deviation_type = "Eligibility Criterion Violation"
    dev.description = "Patient age 76 exceeds maximum age of 75 years"
    dev.severity = DeviationSeverity.MAJOR
    dev.status = DeviationStatus.OPEN
    dev.detected_date = datetime.date(2023, 3, 1)
    dev.evidence = '{"age": 76, "max_age": 75}'
    return dev


@pytest.fixture
def mock_db(mock_deviation):
    db = MagicMock()

    # mock site query
    mock_site = MagicMock()
    mock_site.name = "Royal London Hospital"
    mock_site.city = "London"
    mock_site.country = "UK"
    mock_site.principal_investigator = "Dr. Michael Thornton"

    # mock risk score query
    mock_risk = MagicMock()
    mock_risk.risk_tier = "High"
    mock_risk.major_open_count = 30

    # Chain the query mocks
    db.query.return_value.filter.return_value.first.side_effect = [
        mock_site,  # first call: site query
        mock_risk,  # second call: risk score query
    ]
    return db


# ─────────────────────────────────────────────────────────────────────────────
# Fallback template
# ─────────────────────────────────────────────────────────────────────────────

class TestFallbackNarrative:
    def test_fallback_contains_root_cause(self, mock_deviation):
        text = _fallback_narrative(mock_deviation)
        assert "ROOT CAUSE" in text

    def test_fallback_contains_corrective_action(self, mock_deviation):
        text = _fallback_narrative(mock_deviation)
        assert "CORRECTIVE ACTION" in text

    def test_fallback_contains_preventive_action(self, mock_deviation):
        text = _fallback_narrative(mock_deviation)
        assert "PREVENTIVE ACTION" in text

    def test_fallback_contains_rule_id(self, mock_deviation):
        text = _fallback_narrative(mock_deviation)
        assert "INC-01" in text

    def test_fallback_contains_patient_id(self, mock_deviation):
        text = _fallback_narrative(mock_deviation)
        assert "PT-0042" in text

    def test_fallback_mentions_template_note(self, mock_deviation):
        text = _fallback_narrative(mock_deviation)
        assert "fallback template" in text.lower() or "WATSONX_API_KEY" in text

    def test_fallback_is_not_empty(self, mock_deviation):
        text = _fallback_narrative(mock_deviation)
        assert len(text) > 100


# ─────────────────────────────────────────────────────────────────────────────
# generate_capa_narrative — watsonx unavailable
# ─────────────────────────────────────────────────────────────────────────────

# The generate_text function is imported inside generate_capa_narrative()
# so we patch it at the source module level.
_PATCH_TARGET = "src.backend.services.watsonx_client.generate_text"


class TestGenerateCapaFallback:
    def test_returns_fallback_when_no_api_key(self, mock_db, mock_deviation):
        """Without WATSONX_API_KEY, should return fallback."""
        from src.backend.services.watsonx_client import WatsonxUnavailableError
        with patch(_PATCH_TARGET, side_effect=WatsonxUnavailableError("No key")):
            narrative, source = generate_capa_narrative(mock_db, mock_deviation)

        assert source == "fallback"
        assert len(narrative) > 50

    def test_returns_fallback_on_api_error(self, mock_db, mock_deviation):
        from src.backend.services.watsonx_client import WatsonxAPIError
        with patch(_PATCH_TARGET, side_effect=WatsonxAPIError("HTTP 500")):
            narrative, source = generate_capa_narrative(mock_db, mock_deviation)

        assert source == "fallback"

    def test_returns_fallback_on_unexpected_error(self, mock_db, mock_deviation):
        with patch(_PATCH_TARGET, side_effect=Exception("Unexpected")):
            narrative, source = generate_capa_narrative(mock_db, mock_deviation)

        assert source == "fallback"

    def test_narrative_is_string(self, mock_db, mock_deviation):
        from src.backend.services.watsonx_client import WatsonxUnavailableError
        with patch(_PATCH_TARGET, side_effect=WatsonxUnavailableError("No key")):
            narrative, _ = generate_capa_narrative(mock_db, mock_deviation)
        assert isinstance(narrative, str)


# ─────────────────────────────────────────────────────────────────────────────
# generate_capa_narrative — watsonx available (mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateCapaWatsonx:
    def test_returns_watsonx_source_when_api_succeeds(self, mock_db, mock_deviation):
        watsonx_response = (
            "1. ROOT CAUSE\nProtocol misunderstood.\n\n"
            "2. CORRECTIVE\nRetrain.\n\n"
            "3. PREVENTIVE\nChecklist."
        )
        with patch(_PATCH_TARGET, return_value=watsonx_response):
            narrative, source = generate_capa_narrative(mock_db, mock_deviation)

        assert source == "watsonx"
        assert "ROOT CAUSE" in narrative

    def test_watsonx_narrative_is_used_as_returned(self, mock_db, mock_deviation):
        expected = "The root cause was training failure."
        with patch(_PATCH_TARGET, return_value=expected):
            narrative, source = generate_capa_narrative(mock_db, mock_deviation)

        assert narrative == expected
        assert source == "watsonx"
