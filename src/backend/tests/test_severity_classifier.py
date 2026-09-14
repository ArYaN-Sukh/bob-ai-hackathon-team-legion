"""
Tests for the severity classifier.

Verifies that severity is always read from the protocol rule definition and
never inferred.  Covers all three severity values and error cases.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.backend.engine.protocol_loader import (
    Protocol,
    load_protocol,
    reset_protocol_cache,
)
from src.backend.engine.severity_classifier import (
    UnknownRuleError,
    classify,
    classify_all,
)
from src.backend.models import DeviationSeverity

PROTOCOL_PATH = Path("src/backend/data/protocol.json")


@pytest.fixture(scope="module")
def protocol() -> Protocol:
    reset_protocol_cache()
    return load_protocol(PROTOCOL_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# Core classification tests
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyReturnType:
    def test_returns_deviation_severity_enum(self, protocol):
        result = classify("INC-01", protocol)
        assert isinstance(result, DeviationSeverity)

    def test_major_rule_returns_major(self, protocol):
        assert classify("INC-01", protocol) == DeviationSeverity.MAJOR

    def test_minor_rule_returns_minor(self, protocol):
        assert classify("LAB-03", protocol) == DeviationSeverity.MINOR

    def test_administrative_rule_returns_administrative(self, protocol):
        assert classify("DOS-03", protocol) == DeviationSeverity.ADMINISTRATIVE


class TestAllProtocolRules:
    """Every rule in the protocol must classify without error."""

    def test_all_rules_classify(self, protocol):
        for rule_id in protocol.rules:
            result = classify(rule_id, protocol)
            assert isinstance(result, DeviationSeverity), \
                f"classify({rule_id!r}) did not return DeviationSeverity"

    def test_inc01_is_major(self, protocol):
        """INC-01 is the age eligibility rule violated by PT-0042."""
        assert classify("INC-01", protocol) == DeviationSeverity.MAJOR

    def test_inc02_is_major(self, protocol):
        assert classify("INC-02", protocol) == DeviationSeverity.MAJOR

    def test_inc03_is_major(self, protocol):
        assert classify("INC-03", protocol) == DeviationSeverity.MAJOR

    def test_inc04_is_major(self, protocol):
        assert classify("INC-04", protocol) == DeviationSeverity.MAJOR

    def test_inc05_is_major(self, protocol):
        assert classify("INC-05", protocol) == DeviationSeverity.MAJOR

    def test_exc01_is_major(self, protocol):
        assert classify("EXC-01", protocol) == DeviationSeverity.MAJOR

    def test_exc02_is_major(self, protocol):
        assert classify("EXC-02", protocol) == DeviationSeverity.MAJOR

    def test_exc03_is_major(self, protocol):
        assert classify("EXC-03", protocol) == DeviationSeverity.MAJOR

    def test_lab01_is_major(self, protocol):
        assert classify("LAB-01", protocol) == DeviationSeverity.MAJOR

    def test_lab02_is_major(self, protocol):
        assert classify("LAB-02", protocol) == DeviationSeverity.MAJOR

    def test_lab03_is_minor(self, protocol):
        assert classify("LAB-03", protocol) == DeviationSeverity.MINOR

    def test_lab04_is_minor(self, protocol):
        assert classify("LAB-04", protocol) == DeviationSeverity.MINOR

    def test_lab05_is_major(self, protocol):
        assert classify("LAB-05", protocol) == DeviationSeverity.MAJOR

    def test_dos01_is_minor(self, protocol):
        assert classify("DOS-01", protocol) == DeviationSeverity.MINOR

    def test_dos02_is_major(self, protocol):
        assert classify("DOS-02", protocol) == DeviationSeverity.MAJOR

    def test_dos03_is_administrative(self, protocol):
        assert classify("DOS-03", protocol) == DeviationSeverity.ADMINISTRATIVE

    def test_rep01_is_major(self, protocol):
        assert classify("REP-01", protocol) == DeviationSeverity.MAJOR

    def test_rep02_is_administrative(self, protocol):
        assert classify("REP-02", protocol) == DeviationSeverity.ADMINISTRATIVE


# ─────────────────────────────────────────────────────────────────────────────
# Demo scenario checks
# ─────────────────────────────────────────────────────────────────────────────

class TestDemoScenario:
    def test_pt0042_eligibility_breach_is_major(self, protocol):
        """
        PT-0042 age 76 violates INC-01 (age must be 18-75).
        The severity must be Major — never inferred, always from the protocol.
        """
        severity = classify("INC-01", protocol)
        assert severity == DeviationSeverity.MAJOR, (
            f"INC-01 severity must be Major (got {severity.value}). "
            "PT-0042's age 76 violation is a safety-critical eligibility breach."
        )

    def test_rep01_sae_delay_is_major(self, protocol):
        """PT-0042's SAE 36h reporting delay violates REP-01 which is Major."""
        assert classify("REP-01", protocol) == DeviationSeverity.MAJOR


# ─────────────────────────────────────────────────────────────────────────────
# Error cases
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyErrors:
    def test_unknown_rule_id_raises_unknown_rule_error(self, protocol):
        with pytest.raises(UnknownRuleError):
            classify("NONEXISTENT-999", protocol)

    def test_unknown_rule_error_message_contains_rule_id(self, protocol):
        with pytest.raises(UnknownRuleError, match="NONEXISTENT-999"):
            classify("NONEXISTENT-999", protocol)

    def test_empty_string_rule_id_raises(self, protocol):
        with pytest.raises(UnknownRuleError):
            classify("", protocol)


# ─────────────────────────────────────────────────────────────────────────────
# Batch classification
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyAll:
    def test_classify_all_returns_dict(self, protocol):
        result = classify_all(["INC-01", "LAB-03", "DOS-03"], protocol)
        assert isinstance(result, dict)
        assert len(result) == 3

    def test_classify_all_values(self, protocol):
        result = classify_all(["INC-01", "LAB-03", "DOS-03"], protocol)
        assert result["INC-01"] == DeviationSeverity.MAJOR
        assert result["LAB-03"] == DeviationSeverity.MINOR
        assert result["DOS-03"] == DeviationSeverity.ADMINISTRATIVE

    def test_classify_all_unknown_raises(self, protocol):
        with pytest.raises(UnknownRuleError):
            classify_all(["INC-01", "BAD-RULE"], protocol)
