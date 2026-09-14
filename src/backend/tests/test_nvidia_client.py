"""
Tests for NVIDIA Nemotron client.
"""
from __future__ import annotations

import pytest
from httpx import HTTPError, Response

from src.backend.services.nvidia_client import (
    NvidiaAPIError,
    NvidiaUnavailableError,
    generate_response,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
)


class TestNvidiaUnavailable:
    """Test behavior when NVIDIA credentials are not configured."""

    def test_raises_without_api_key(self, monkeypatch):
        """Should raise NvidiaUnavailableError when API key is missing."""
        # Mock settings directly
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        with pytest.raises(NvidiaUnavailableError, match="NVIDIA_API_KEY is not configured"):
            generate_response([{"role": "user", "content": "test"}])


class TestNvidiaAPIError:
    """Test API error handling."""

    def test_http_error_handling(self, monkeypatch):
        """Should raise NvidiaAPIError on HTTP errors."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        # Mock httpx.post to raise HTTPError
        import httpx

        def mock_post(*args, **kwargs):
            raise HTTPError("Connection error")

        monkeypatch.setattr(httpx, "post", mock_post)

        with pytest.raises(NvidiaAPIError, match="NVIDIA request failed"):
            generate_response([{"role": "user", "content": "test"}])

    def test_non_200_status_handling(self, monkeypatch):
        """Should raise NvidiaAPIError on non-200 status."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        import httpx

        def mock_post(*args, **kwargs):
            return Response(500, request=None)

        monkeypatch.setattr(httpx, "post", mock_post)

        with pytest.raises(NvidiaAPIError, match="NVIDIA returned HTTP 500"):
            generate_response([{"role": "user", "content": "test"}])

    def test_malformed_response_handling(self, monkeypatch):
        """Should raise NvidiaAPIError on malformed response."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        import httpx

        def mock_post(*args, **kwargs):
            resp = Response(200, request=None)
            resp._content = b'{"invalid": "structure"}'
            return resp

        monkeypatch.setattr(httpx, "post", mock_post)

        with pytest.raises(NvidiaAPIError, match="Unexpected NVIDIA response shape"):
            generate_response([{"role": "user", "content": "test"}])


class TestResponseStructure:
    """Test response structure when successful."""

    def test_extracts_generated_text(self, monkeypatch):
        """Should extract generated text from OpenAI-compatible response."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        import httpx

        def mock_post(*args, **kwargs):
            resp = Response(200, request=None)
            resp._content = b'{"choices": [{"message": {"content": "Test response"}}]}'
            return resp

        monkeypatch.setattr(httpx, "post", mock_post)

        result = generate_response([{"role": "user", "content": "test"}])
        assert result == "Test response"

    def test_strips_whitespace(self, monkeypatch):
        """Should strip whitespace from generated text."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        import httpx

        def mock_post(*args, **kwargs):
            resp = Response(200, request=None)
            resp._content = b'{"choices": [{"message": {"content": "  Test response  "}}]}'
            return resp

        monkeypatch.setattr(httpx, "post", mock_post)

        result = generate_response([{"role": "user", "content": "test"}])
        assert result == "Test response"


class TestThinkingDisabled:
    """Test that thinking is explicitly disabled in NVIDIA requests."""

    def test_request_includes_thinking_disabled(self, monkeypatch):
        """Should include chat_template_kwargs with enable_thinking=False in request."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        import httpx

        captured_kwargs = {}

        def mock_post(*args, **kwargs):
            captured_kwargs.update(kwargs)
            resp = Response(200, request=None)
            resp._content = b'{"choices": [{"message": {"content": "Test response"}}]}'
            return resp

        monkeypatch.setattr(httpx, "post", mock_post)

        generate_response([{"role": "user", "content": "test"}])

        # Verify the payload includes chat_template_kwargs
        assert "json" in captured_kwargs
        payload = captured_kwargs["json"]
        assert "chat_template_kwargs" in payload
        assert payload["chat_template_kwargs"]["enable_thinking"] is False

    def test_temperature_set_lower_for_determinism(self, monkeypatch):
        """Should use lower temperature for more deterministic responses."""
        # Mock settings
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "test-key")
        monkeypatch.setattr(config.settings, "nvidia_model", "test-model")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "https://test.com/v1")

        import httpx

        captured_kwargs = {}

        def mock_post(*args, **kwargs):
            captured_kwargs.update(kwargs)
            resp = Response(200, request=None)
            resp._content = b'{"choices": [{"message": {"content": "Test response"}}]}'
            return resp

        monkeypatch.setattr(httpx, "post", mock_post)

        generate_response([{"role": "user", "content": "test"}])

        # Verify temperature is set to expected value
        assert "json" in captured_kwargs
        payload = captured_kwargs["json"]
        assert payload["temperature"] == DEFAULT_TEMPERATURE
        assert DEFAULT_TEMPERATURE == 0.3  # Deterministic temperature for TrialGuard
