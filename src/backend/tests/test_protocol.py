"""
Tests for protocol.json structure and content.
These tests verify that the protocol file exists, is valid JSON, and contains
all the required sections and rules expected by the deviation engine.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

PROTOCOL_PATH = Path("src/backend/data/protocol.json")


@pytest.fixture(scope="module")
def protocol() -> dict:
    assert PROTOCOL_PATH.exists(), f"protocol.json not found at {PROTOCOL_PATH}"
    with PROTOCOL_PATH.open() as f:
        return json.load(f)


class TestProtocolExists:
    def test_file_exists(self):
        assert PROTOCOL_PATH.exists(), "protocol.json must exist"

    def test_is_valid_json(self):
        with PROTOCOL_PATH.open() as f:
            data = json.load(f)
        assert isinstance(data, dict)


class TestProtocolMetadata:
    def test_has_trial_id(self, protocol):
        assert "trial_id" in protocol
        assert protocol["trial_id"] == "TRIAL-TG-001"

    def test_has_version(self, protocol):
        assert "version" in protocol
        assert protocol["version"] == "2.1"

    def test_has_title(self, protocol):
        assert "title" in protocol
        assert len(protocol["title"]) > 0

    def test_has_phase(self, protocol):
        assert "phase" in protocol
        assert protocol["phase"] == "II"

    def test_synthetic_marker_in_comment(self, protocol):
        """Protocol must be clearly identified as synthetic demo data."""
        comment = protocol.get("_comment", "")
        assert "SYNTHETIC" in comment.upper() or "DEMO" in comment.upper(), \
            "Protocol must contain a synthetic/demo data marker"


class TestInclusionCriteria:
    def test_has_inclusion_criteria(self, protocol):
        assert "inclusion_criteria" in protocol
        assert isinstance(protocol["inclusion_criteria"], list)

    def test_at_least_three_inclusion_criteria(self, protocol):
        assert len(protocol["inclusion_criteria"]) >= 3, \
            "Protocol must define at least 3 inclusion criteria"

    def test_inc_01_age_rule_exists(self, protocol):
        """INC-01 (age 18–75) is critical for the PT-0042 demo scenario."""
        rule_ids = [r["rule_id"] for r in protocol["inclusion_criteria"]]
        assert "INC-01" in rule_ids, "INC-01 (age eligibility rule) must be present"

    def test_inc_01_age_values(self, protocol):
        inc_01 = next(r for r in protocol["inclusion_criteria"] if r["rule_id"] == "INC-01")
        assert inc_01["operator"] == "between"
        assert 18 in inc_01["values"]
        assert 75 in inc_01["values"]

    def test_inc_01_severity_is_major(self, protocol):
        inc_01 = next(r for r in protocol["inclusion_criteria"] if r["rule_id"] == "INC-01")
        assert inc_01["severity_if_violated"] == "Major"

    def test_all_inclusion_criteria_have_required_fields(self, protocol):
        required_fields = {"rule_id", "description", "severity_if_violated"}
        for rule in protocol["inclusion_criteria"]:
            missing = required_fields - set(rule.keys())
            assert not missing, f"Rule {rule.get('rule_id')} missing fields: {missing}"


class TestExclusionCriteria:
    def test_has_exclusion_criteria(self, protocol):
        assert "exclusion_criteria" in protocol
        assert isinstance(protocol["exclusion_criteria"], list)

    def test_at_least_two_exclusion_criteria(self, protocol):
        assert len(protocol["exclusion_criteria"]) >= 2, \
            "Protocol must define at least 2 exclusion criteria"

    def test_all_exclusion_criteria_have_required_fields(self, protocol):
        required_fields = {"rule_id", "description", "severity_if_violated"}
        for rule in protocol["exclusion_criteria"]:
            missing = required_fields - set(rule.keys())
            assert not missing, f"Rule {rule.get('rule_id')} missing fields: {missing}"


class TestVisitSchedule:
    def test_has_visit_schedule(self, protocol):
        assert "visit_schedule" in protocol
        assert isinstance(protocol["visit_schedule"], list)

    def test_exactly_four_visits(self, protocol):
        assert len(protocol["visit_schedule"]) == 4, \
            "Protocol must define exactly 4 visits for Phase 1"

    def test_visit_numbers_are_sequential(self, protocol):
        numbers = sorted(v["visit_number"] for v in protocol["visit_schedule"])
        assert numbers == [1, 2, 3, 4]

    def test_all_visits_have_window_tolerances(self, protocol):
        for visit in protocol["visit_schedule"]:
            assert "window_days_before" in visit, f"Visit {visit['visit_number']} missing window_days_before"
            assert "window_days_after" in visit, f"Visit {visit['visit_number']} missing window_days_after"

    def test_all_visits_have_required_assessments(self, protocol):
        for visit in protocol["visit_schedule"]:
            assert "required_assessments" in visit, f"Visit {visit['visit_number']} missing required_assessments"
            assert len(visit["required_assessments"]) > 0

    def test_visit_4_includes_tumor_assessment(self, protocol):
        """Visit 4 is the primary endpoint visit — tumor_assessment must be required."""
        v4 = next(v for v in protocol["visit_schedule"] if v["visit_number"] == 4)
        assert "tumor_assessment" in v4["required_assessments"]


class TestLabThresholds:
    def test_has_lab_thresholds(self, protocol):
        assert "lab_thresholds" in protocol
        assert isinstance(protocol["lab_thresholds"], list)

    def test_at_least_three_lab_thresholds(self, protocol):
        assert len(protocol["lab_thresholds"]) >= 3, \
            "Protocol must define at least 3 lab thresholds"

    def test_lab_01_hemoglobin_rule_exists(self, protocol):
        rule_ids = [r["rule_id"] for r in protocol["lab_thresholds"]]
        assert "LAB-01" in rule_ids

    def test_all_lab_thresholds_have_required_fields(self, protocol):
        required_fields = {"rule_id", "test_name", "unit", "severity_if_violated"}
        for rule in protocol["lab_thresholds"]:
            missing = required_fields - set(rule.keys())
            assert not missing, f"Lab rule {rule.get('rule_id')} missing fields: {missing}"

    def test_each_lab_rule_has_at_least_one_bound(self, protocol):
        for rule in protocol["lab_thresholds"]:
            has_min = rule.get("min_value") is not None
            has_max = rule.get("max_value") is not None
            assert has_min or has_max, \
                f"Lab rule {rule['rule_id']} must have at least min_value or max_value"


class TestDosingRules:
    def test_has_dosing_rules(self, protocol):
        assert "dosing_rules" in protocol
        assert isinstance(protocol["dosing_rules"], list)

    def test_at_least_two_dosing_rules(self, protocol):
        assert len(protocol["dosing_rules"]) >= 2, \
            "Protocol must define at least 2 dosing rules"

    def test_all_dosing_rules_have_required_fields(self, protocol):
        required_fields = {"rule_id", "description", "severity_if_violated"}
        for rule in protocol["dosing_rules"]:
            missing = required_fields - set(rule.keys())
            assert not missing, f"Dosing rule {rule.get('rule_id')} missing fields: {missing}"


class TestReportingRules:
    def test_has_reporting_rules(self, protocol):
        assert "reporting_rules" in protocol
        assert isinstance(protocol["reporting_rules"], list)

    def test_rep_01_sae_rule_exists(self, protocol):
        """SAE 24-hour reporting rule is critical for the demo scenario."""
        rule_ids = [r["rule_id"] for r in protocol["reporting_rules"]]
        assert "REP-01" in rule_ids, "REP-01 (SAE reporting within 24h) must be present"

    def test_rep_01_value_is_24(self, protocol):
        rep_01 = next(r for r in protocol["reporting_rules"] if r["rule_id"] == "REP-01")
        assert rep_01["value"] == 24

    def test_rep_01_severity_is_major(self, protocol):
        rep_01 = next(r for r in protocol["reporting_rules"] if r["rule_id"] == "REP-01")
        assert rep_01["severity_if_violated"] == "Major"


class TestSeverityDefinitions:
    def test_has_severity_definitions(self, protocol):
        assert "severity_definitions" in protocol

    def test_all_three_severities_defined(self, protocol):
        defs = protocol["severity_definitions"]
        assert "Major" in defs
        assert "Minor" in defs
        assert "Administrative" in defs
