"""
Tests for the protocol loader.

Covers: file loading, JSON validation, rule parsing, severity validation,
VisitSpec window logic, and error cases.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.backend.engine.protocol_loader import (
    VALID_SEVERITIES,
    Protocol,
    ProtocolLoadError,
    VisitSpec,
    get_protocol,
    load_protocol,
    reset_protocol_cache,
)

PROTOCOL_PATH = Path("src/backend/data/protocol.json")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _write_protocol(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "protocol.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _minimal_valid_protocol() -> dict:
    """Return a minimal but valid protocol dict for error-case tests."""
    return {
        "trial_id": "TEST-001",
        "version": "1.0",
        "title": "Test Protocol",
        "inclusion_criteria": [{
            "rule_id": "INC-01",
            "description": "Age 18-75",
            "field": "patient.age",
            "operator": "between",
            "values": [18, 75],
            "severity_if_violated": "Major",
        }],
        "exclusion_criteria": [{
            "rule_id": "EXC-01",
            "description": "No active infection",
            "severity_if_violated": "Major",
        }],
        "visit_schedule": [{
            "visit_number": 1,
            "name": "Screening",
            "nominal_day": -14,
            "window_days_before": 0,
            "window_days_after": 3,
            "required_assessments": ["vitals", "ecg"],
        }],
        "lab_thresholds": [{
            "rule_id": "LAB-01",
            "test_name": "hemoglobin",
            "display_name": "Hemoglobin",
            "min_value": 8.0,
            "max_value": None,
            "unit": "g/dL",
            "severity_if_violated": "Major",
        }],
        "dosing_rules": [{
            "rule_id": "DOS-01",
            "description": "Drug with meal",
            "severity_if_violated": "Minor",
        }],
        "reporting_rules": [{
            "rule_id": "REP-01",
            "description": "SAE within 24h",
            "field": "adverse_event.reporting_delay_hours",
            "operator": "lte",
            "value": 24,
            "severity_if_violated": "Major",
        }],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: real protocol
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def protocol() -> Protocol:
    return load_protocol(PROTOCOL_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# Loading and structure
# ─────────────────────────────────────────────────────────────────────────────

class TestProtocolLoading:
    def test_loads_real_protocol(self, protocol):
        assert isinstance(protocol, Protocol)

    def test_trial_id(self, protocol):
        assert protocol.trial_id == "TRIAL-TG-001"

    def test_version(self, protocol):
        assert protocol.version == "2.1"

    def test_title_non_empty(self, protocol):
        assert len(protocol.title) > 0

    def test_has_visits(self, protocol):
        assert len(protocol.visits) == 4

    def test_has_rules(self, protocol):
        assert len(protocol.rules) > 0

    def test_all_rules_have_valid_severity(self, protocol):
        for rule in protocol.rules.values():
            assert rule.severity_if_violated in VALID_SEVERITIES

    def test_rule_ids_are_unique(self, protocol):
        ids = list(protocol.rules.keys())
        assert len(ids) == len(set(ids))


class TestProtocolRuleAccess:
    def test_get_known_rule(self, protocol):
        rule = protocol.get_rule("INC-01")
        assert rule.rule_id == "INC-01"

    def test_get_unknown_rule_raises(self, protocol):
        with pytest.raises(KeyError):
            protocol.get_rule("NONEXISTENT-99")

    def test_severity_for_inc01(self, protocol):
        assert protocol.severity_for("INC-01") == "Major"

    def test_severity_for_lab03(self, protocol):
        assert protocol.severity_for("LAB-03") == "Minor"

    def test_severity_for_dos03(self, protocol):
        assert protocol.severity_for("DOS-03") == "Administrative"

    def test_rules_by_category_inclusion(self, protocol):
        rules = protocol.rules_by_category("inclusion")
        assert len(rules) >= 3

    def test_rules_by_category_lab(self, protocol):
        rules = protocol.rules_by_category("lab")
        assert len(rules) >= 3

    def test_rules_by_category_reporting(self, protocol):
        rules = protocol.rules_by_category("reporting")
        assert any(r.rule_id == "REP-01" for r in rules)


class TestVisitSpec:
    def test_visit_1_exists(self, protocol):
        v = protocol.visit(1)
        assert v.visit_number == 1
        assert v.name == "Screening"

    def test_visit_4_has_tumor_assessment(self, protocol):
        v = protocol.visit(4)
        assert "tumor_assessment" in v.required_assessments

    def test_window_within(self):
        spec = VisitSpec(1, "Test", 0, 2, 3, ("vitals",))
        assert spec.within_window(0)
        assert spec.within_window(-2)
        assert spec.within_window(3)

    def test_window_outside_late(self):
        spec = VisitSpec(1, "Test", 0, 2, 3, ("vitals",))
        assert not spec.within_window(4)   # > window_after

    def test_window_outside_early(self):
        spec = VisitSpec(1, "Test", 0, 2, 3, ("vitals",))
        assert not spec.within_window(-3)  # < -window_before

    def test_visit_3_window(self, protocol):
        """Visit 3 allows ±2 days."""
        v = protocol.visit(3)
        assert v.within_window(2)
        assert v.within_window(-2)
        assert not v.within_window(3)
        assert not v.within_window(-3)

    def test_visit_unknown_raises(self, protocol):
        with pytest.raises(KeyError):
            protocol.visit(99)


# ─────────────────────────────────────────────────────────────────────────────
# Error cases
# ─────────────────────────────────────────────────────────────────────────────

class TestProtocolLoadErrors:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ProtocolLoadError, match="not found"):
            load_protocol(tmp_path / "does_not_exist.json")

    def test_invalid_json_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ProtocolLoadError, match="valid JSON"):
            load_protocol(bad)

    def test_missing_trial_id_raises(self, tmp_path):
        data = _minimal_valid_protocol()
        del data["trial_id"]
        p = _write_protocol(tmp_path, data)
        with pytest.raises(ProtocolLoadError, match="trial_id"):
            load_protocol(p)

    def test_missing_inclusion_criteria_raises(self, tmp_path):
        data = _minimal_valid_protocol()
        del data["inclusion_criteria"]
        p = _write_protocol(tmp_path, data)
        with pytest.raises(ProtocolLoadError):
            load_protocol(p)

    def test_empty_inclusion_criteria_raises(self, tmp_path):
        data = _minimal_valid_protocol()
        data["inclusion_criteria"] = []
        p = _write_protocol(tmp_path, data)
        with pytest.raises(ProtocolLoadError, match="empty"):
            load_protocol(p)

    def test_invalid_severity_raises(self, tmp_path):
        data = _minimal_valid_protocol()
        data["inclusion_criteria"][0]["severity_if_violated"] = "CATASTROPHIC"
        p = _write_protocol(tmp_path, data)
        with pytest.raises(ProtocolLoadError, match="invalid severity"):
            load_protocol(p)

    def test_lab_rule_missing_both_bounds_raises(self, tmp_path):
        data = _minimal_valid_protocol()
        data["lab_thresholds"][0]["min_value"] = None
        data["lab_thresholds"][0]["max_value"] = None
        p = _write_protocol(tmp_path, data)
        with pytest.raises(ProtocolLoadError, match="min_value or max_value"):
            load_protocol(p)

    def test_duplicate_rule_ids_raise(self, tmp_path):
        data = _minimal_valid_protocol()
        # Add an exclusion rule with the same rule_id as the inclusion rule
        data["exclusion_criteria"].append({
            "rule_id": "INC-01",  # duplicate
            "description": "Duplicate",
            "severity_if_violated": "Minor",
        })
        p = _write_protocol(tmp_path, data)
        with pytest.raises(ProtocolLoadError, match="Duplicate rule_id"):
            load_protocol(p)


# ─────────────────────────────────────────────────────────────────────────────
# Cache behaviour
# ─────────────────────────────────────────────────────────────────────────────

class TestProtocolCache:
    def test_get_protocol_returns_same_instance(self):
        reset_protocol_cache()
        p1 = get_protocol(PROTOCOL_PATH)
        p2 = get_protocol()  # Should use cache
        assert p1 is p2

    def test_reset_cache_forces_reload(self):
        reset_protocol_cache()
        p1 = get_protocol(PROTOCOL_PATH)
        reset_protocol_cache()
        p2 = get_protocol(PROTOCOL_PATH)
        # Different object, same content
        assert p1 is not p2
        assert p1.trial_id == p2.trial_id
