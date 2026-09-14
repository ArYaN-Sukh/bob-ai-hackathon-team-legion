"""
Tests for Bob response generator service.
"""
from __future__ import annotations

import pytest

from src.backend.services.bob_response_generator import (
    _sanitize_llm_response,
    _is_greeting,
    _get_greeting_response,
    _format_site_risk_detail,
    _format_query_deviations,
    _format_get_protocol_rule,
    _format_analyse_site_trends,
    _format_get_patient_timeline,
    _deterministic_format,
    generate_bob_response,
)


class TestDeterministicFormatters:
    """Test deterministic fallback formatters."""

    def test_site_risk_detail_formatter(self):
        """Should format site risk data correctly."""
        data = {
            "site_id": "SITE-003",
            "risk_score": 422.48,
            "risk_tier": "High",
            "open_major_deviations": 31,
            "open_minor_deviations": 28,
            "open_admin_deviations": 0,
            "score_components": {
                "major_contribution": 310,
                "minor_contribution": 84,
            },
            "recent_open_deviations": [
                {
                    "severity": "Major",
                    "deviation_type": "Missing Assessment",
                    "rule_id": "MISSING-ASSESSMENT-TUMOR-ASSESSMENT",
                },
                {
                    "severity": "Minor",
                    "deviation_type": "Visit Window",
                    "rule_id": "VISIT-WINDOW",
                },
            ],
        }

        result = _format_site_risk_detail(data)
        
        assert "SITE-003" in result
        assert "High" in result
        assert "422.5" in result
        assert "31" in result
        assert "28" in result
        assert "0" in result
        assert "310" in result
        assert "84" in result
        assert "Missing Assessment" in result
        assert "Visit Window" in result

    def test_query_deviations_formatter(self):
        """Should format deviation data correctly."""
        data = {
            "deviations": [
                {
                    "rule_id": "INC-01",
                    "severity": "Major",
                    "deviation_type": "Eligibility - Inclusion",
                    "patient_id": "PT-0042",
                },
                {
                    "rule_id": "LAB-01",
                    "severity": "Major",
                    "deviation_type": "Lab Threshold",
                    "patient_id": "PT-0042",
                },
                {
                    "rule_id": "VISIT-WINDOW",
                    "severity": "Minor",
                    "deviation_type": "Visit Window",
                    "patient_id": "PT-0042",
                },
            ],
        }

        result = _format_query_deviations(data)
        
        assert "Found 3 deviation(s)" in result
        assert "Major (2)" in result
        assert "Minor (1)" in result
        assert "INC-01" in result
        assert "LAB-01" in result
        assert "VISIT-WINDOW" in result
        assert "PT-0042" in result

    def test_query_deviations_empty(self):
        """Should handle empty deviation list."""
        data = {"deviations": []}
        result = _format_query_deviations(data)
        assert "No deviations found" in result

    def test_get_protocol_rule_formatter(self):
        """Should format protocol rule data correctly."""
        data = {
            "rule_id": "INC-01",
            "description": "Patient age must be between 18 and 75 years",
            "open_violation_count": 1,
        }

        result = _format_get_protocol_rule(data)
        
        assert "INC-01" in result
        assert "Patient age must be between 18 and 75 years" in result
        assert "1 time(s)" in result

    def test_analyse_site_trends_formatter(self):
        """Should format site trends data correctly."""
        data = {
            "sites": [
                {
                    "site_id": "SITE-003",
                    "risk_tier": "High",
                    "risk_score": 422.48,
                    "open_major": 31,
                    "open_minor": 28,
                },
                {
                    "site_id": "SITE-005",
                    "risk_tier": "Low",
                    "risk_score": 10.0,
                    "open_major": 0,
                    "open_minor": 0,
                },
            ],
        }

        result = _format_analyse_site_trends(data)
        
        assert "Trial-wide risk summary" in result
        assert "SITE-003" in result
        assert "High" in result
        assert "422.5" in result
        assert "SITE-005" in result
        assert "Low" in result
        assert "10.0" in result

    def test_get_patient_timeline_formatter(self):
        """Should format patient timeline data correctly."""
        data = {
            "patient_id": "PT-0042",
            "total_open_deviations": 8,
            "visits": [
                {"visit_number": 1},
                {"visit_number": 2},
                {"visit_number": 3},
                {"visit_number": 4},
            ],
            "all_deviations": [
                {"severity": "Major"},
                {"severity": "Major"},
                {"severity": "Major"},
                {"severity": "Major"},
                {"severity": "Major"},
                {"severity": "Major"},
                {"severity": "Minor"},
                {"severity": "Minor"},
            ],
        }

        result = _format_get_patient_timeline(data)
        
        assert "PT-0042" in result
        assert "8" in result
        assert "4" in result
        assert "6 Major" in result
        assert "2 Minor" in result


class TestDeterministicRouting:
    """Test routing to correct formatter."""

    def test_routes_to_site_risk_formatter(self):
        """Should route get_site_risk_detail to correct formatter."""
        data = {
            "site_id": "SITE-003",
            "risk_score": 422.48,
            "risk_tier": "High",
            "open_major_deviations": 31,
        }
        result = _deterministic_format("get_site_risk_detail", data)
        assert "SITE-003" in result
        assert "High" in result

    def test_routes_to_deviations_formatter(self):
        """Should route query_deviations to correct formatter."""
        data = {"deviations": []}
        result = _deterministic_format("query_deviations", data)
        assert "No deviations found" in result

    def test_routes_to_protocol_rule_formatter(self):
        """Should route get_protocol_rule to correct formatter."""
        data = {
            "rule_id": "INC-01",
            "description": "Test rule",
            "open_violation_count": 0,
        }
        result = _deterministic_format("get_protocol_rule", data)
        assert "INC-01" in result

    def test_routes_to_site_trends_formatter(self):
        """Should route analyse_site_trends to correct formatter."""
        data = {"sites": []}
        result = _deterministic_format("analyse_site_trends", data)
        assert "No site data available" in result

    def test_routes_to_patient_timeline_formatter(self):
        """Should route get_patient_timeline to correct formatter."""
        data = {
            "patient_id": "PT-0042",
            "total_open_deviations": 0,
            "visits": [],
        }
        result = _deterministic_format("get_patient_timeline", data)
        assert "PT-0042" in result

    def test_unknown_tool_returns_json(self):
        """Should return JSON for unknown tools."""
        data = {"test": "data"}
        result = _deterministic_format("unknown_tool", data)
        assert '"test"' in result
        assert '"data"' in result


class TestGenerateBobResponse:
    """Test the main generate_bob_response function."""

    def test_fallback_when_nvidia_unavailable(self, monkeypatch):
        """Should use fallback when NVIDIA is not configured."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        tool_result = {
            "site_id": "SITE-003",
            "risk_score": 422.48,
            "risk_tier": "High",
            "open_major_deviations": 31,
            "open_minor_deviations": 28,
            "open_admin_deviations": 0,
        }

        response, source = generate_bob_response(
            user_question="Why is SITE-003 at High risk?",
            tool_name="get_site_risk_detail",
            tool_result=tool_result,
        )

        assert source == "fallback"
        assert "SITE-003" in response
        assert "High" in response

    def test_fallback_when_nvidia_api_error(self, monkeypatch):
        """Should use fallback when NVIDIA API errors."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        # Mock NVIDIA client to raise error
        from src.backend.services import nvidia_client
        original_generate = nvidia_client.generate_response

        def mock_generate(*args, **kwargs):
            from src.backend.services.nvidia_client import NvidiaAPIError
            raise NvidiaAPIError("API error")

        monkeypatch.setattr(nvidia_client, "generate_response", mock_generate)

        tool_result = {
            "site_id": "SITE-003",
            "risk_score": 422.48,
            "risk_tier": "High",
            "open_major_deviations": 31,
        }

        response, source = generate_bob_response(
            user_question="Why is SITE-003 at High risk?",
            tool_name="get_site_risk_detail",
            tool_result=tool_result,
        )

        assert source == "fallback"
        assert "SITE-003" in response

    def test_preserves_numeric_values_in_fallback(self, monkeypatch):
        """Should preserve exact numeric values in fallback mode."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "")

        tool_result = {
            "site_id": "SITE-003",
            "risk_score": 422.48,
            "risk_tier": "High",
            "open_major_deviations": 31,
            "open_minor_deviations": 28,
        }

        response, source = generate_bob_response(
            user_question="Why is SITE-003 at High risk?",
            tool_name="get_site_risk_detail",
            tool_result=tool_result,
        )

        assert source == "fallback"
        assert "422.5" in response  # Formatted but correct
        assert "31" in response
        assert "28" in response

    def test_preserves_severity_values_in_fallback(self, monkeypatch):
        """Should preserve severity classifications in fallback mode."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "")

        tool_result = {
            "deviations": [
                {
                    "rule_id": "INC-01",
                    "severity": "Major",
                    "deviation_type": "Eligibility",
                    "patient_id": "PT-0042",
                },
                {
                    "rule_id": "VISIT-WINDOW",
                    "severity": "Minor",
                    "deviation_type": "Visit Window",
                    "patient_id": "PT-0042",
                },
            ],
        }

        response, source = generate_bob_response(
            user_question="Show me deviations for PT-0042",
            tool_name="query_deviations",
            tool_result=tool_result,
        )

        assert source == "fallback"
        assert "Major" in response
        assert "Minor" in response
        # Should NOT have lowercase or altered severity
        assert "major" not in response.lower() or "Major" in response

    def test_preserves_site_id_in_fallback(self, monkeypatch):
        """Should preserve site ID exactly in fallback mode."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "")

        tool_result = {
            "site_id": "SITE-003",
            "risk_score": 422.48,
            "risk_tier": "High",
            "open_major_deviations": 31,
        }

        response, source = generate_bob_response(
            user_question="Why is SITE-003 at High risk?",
            tool_name="get_site_risk_detail",
            tool_result=tool_result,
        )

        assert source == "fallback"
        assert "SITE-003" in response
        # Should NOT alter site ID
        assert "site-003" not in response.lower() or "SITE-003" in response


class TestResponseSanitization:
    """Test response sanitization to remove visible reasoning."""

    def test_removes_thinking_process_prefix(self):
        """Should remove 'Here's a thinking process:' prefix and following reasoning lines."""
        response = """Here's a thinking process:
Let me analyze the data.
Check the score.
Review deviations.

Site SITE-003 is High risk."""
        result = _sanitize_llm_response(response)
        assert "Here's a thinking process:" not in result
        assert "Let me analyze the data" not in result
        assert "Site SITE-003 is High risk" in result

    def test_removes_analysis_prefix(self):
        """Should remove 'Analysis:' prefix and following reasoning lines."""
        response = """Analysis:
The risk score is 422.48.
Check the deviations.
Review the data.

SITE-003 has 31 major deviations."""
        result = _sanitize_llm_response(response)
        assert "Analysis:" not in result
        assert "The risk score is 422.48" not in result
        assert "SITE-003 has 31 major deviations" in result

    def test_removes_let_me_think_prefix(self):
        """Should remove 'Let me think:' prefix and following reasoning lines."""
        response = """Let me think:
First, I'll check the data.
Review the scores.
Check the count.

SITE-003 is High risk."""
        result = _sanitize_llm_response(response)
        assert "Let me think:" not in result
        assert "First, I'll check the data" not in result
        assert "SITE-003 is High risk" in result

    def test_removes_step_prefixes(self):
        """Should remove 'Step 1:', 'Step 2:' prefixes and following reasoning lines."""
        response = """Step 1: Analyze the data.
Step 2: Check the score.
Step 3: Review deviations.

SITE-003 is High risk."""
        result = _sanitize_llm_response(response)
        assert "Step 1:" not in result
        assert "Step 2:" not in result
        assert "SITE-003 is High risk" in result

    def test_removes_wait_prefix(self):
        """Should remove 'Wait,' prefix and following reasoning lines."""
        response = """Wait, let me check.
I need to verify.
Check the data.

SITE-003 is High risk."""
        result = _sanitize_llm_response(response)
        assert "Wait," not in result
        assert "let me check" not in result
        assert "SITE-003 is High risk" in result

    def test_preserves_valid_response(self):
        """Should preserve valid response without reasoning."""
        response = "Site SITE-003 is High risk with a score of 422.48."
        result = _sanitize_llm_response(response)
        assert result == response

    def test_handles_empty_after_sanitization(self):
        """Should return fallback if response becomes empty."""
        response = """Here's a thinking process:
Let me analyze."""
        result = _sanitize_llm_response(response)
        assert "apologize" in result.lower()
        assert "rephrasing" in result.lower()

    def test_removes_multiline_reasoning_block(self):
        """Should remove multiline reasoning blocks."""
        response = """Here's a thinking process:
I need to analyze the user's question.
The tool result shows SITE-003 data.
Let me structure the answer.

Site SITE-003 is High risk."""
        result = _sanitize_llm_response(response)
        assert "Here's a thinking process:" not in result
        assert "I need to analyze" not in result
        assert "Let me structure" not in result
        assert "Site SITE-003 is High risk" in result


class TestGreetingHandling:
    """Test greeting detection and response."""

    def test_detects_hi(self):
        """Should detect 'hi' as greeting."""
        assert _is_greeting("hi")
        assert _is_greeting("hi ")
        assert _is_greeting("Hi")

    def test_detects_hello(self):
        """Should detect 'hello' as greeting."""
        assert _is_greeting("hello")
        assert _is_greeting("Hello")
        assert _is_greeting("hello there")

    def test_detects_hey(self):
        """Should detect 'hey' as greeting."""
        assert _is_greeting("hey")
        assert _is_greeting("Hey")

    def test_detects_greetings(self):
        """Should detect 'greetings' as greeting."""
        assert _is_greeting("greetings")

    def test_detects_good_morning(self):
        """Should detect 'good morning' as greeting."""
        assert _is_greeting("good morning")
        assert _is_greeting("Good morning")

    def test_rejects_non_greetings(self):
        """Should reject non-greeting queries."""
        assert not _is_greeting("Why is SITE-003 at High risk?")
        assert not _is_greeting("Show me deviations")
        assert not _is_greeting("What is rule INC-01?")
        assert not _is_greeting("site risk")

    def test_greeting_response_content(self):
        """Should return appropriate greeting response."""
        response = _get_greeting_response()
        assert "Hello" in response
        assert "TrialGuard AI" in response
        assert "site risk" in response.lower()
        assert "deviations" in response.lower()
        assert "protocol rules" in response.lower()
