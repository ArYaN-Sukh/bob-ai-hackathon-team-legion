"""
NVIDIA Nemotron REST client for TrialGuard Ask Bob.

Uses NVIDIA's OpenAI-compatible API endpoint for text generation.
If NVIDIA_API_KEY is not configured, all calls raise NvidiaUnavailableError
so callers can fall back gracefully.

Endpoint: POST {NVIDIA_BASE_URL}/chat/completions
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from src.backend.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.3  # Deterministic temperature for TrialGuard
DEFAULT_TIMEOUT = 30


class NvidiaUnavailableError(Exception):
    """Raised when NVIDIA credentials are not configured."""


class NvidiaAPIError(Exception):
    """Raised when the NVIDIA API returns a non-2xx response."""


def generate_response(
    messages: list[dict[str, str]],
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """
    Call the NVIDIA OpenAI-compatible chat completion API and return the generated text.

    Parameters
    ----------
    messages : list[dict[str, str]]
        Chat messages in OpenAI format [{"role": "user", "content": "..."}].
    model : str | None
        NVIDIA model identifier. If None, uses NVIDIA_MODEL from settings or default.
    max_tokens : int
        Maximum tokens to generate.
    temperature : float
        Sampling temperature (0 = deterministic, 1 = creative).

    Returns
    -------
    str
        Generated text from the model.

    Raises
    ------
    NvidiaUnavailableError
        If NVIDIA_API_KEY is not set.
    NvidiaAPIError
        If the API returns a non-2xx status code.
    """
    if not settings.nvidia_api_key:
        raise NvidiaUnavailableError("NVIDIA_API_KEY is not configured")

    # Use configured model or default
    model_name = model or settings.nvidia_model or DEFAULT_MODEL
    base_url = settings.nvidia_base_url or "https://integrate.api.nvidia.com/v1"

    url = f"{base_url}/chat/completions"

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
        # NVIDIA-specific: disable thinking/reasoning to get only final answer
        "chat_template_kwargs": {
            "enable_thinking": False
        }
    }

    try:
        resp = httpx.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.nvidia_api_key}",
                "Content-Type": "application/json",
            },
            timeout=DEFAULT_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise NvidiaAPIError(f"NVIDIA request failed: {exc}") from exc

    if resp.status_code != 200:
        raise NvidiaAPIError(
            f"NVIDIA returned HTTP {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise NvidiaAPIError(
            f"Unexpected NVIDIA response shape: {data}"
        ) from exc
