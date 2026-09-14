"""
watsonx.ai REST client for TrialGuard.

Makes POST requests to the IBM watsonx.ai text generation endpoint.
If WATSONX_API_KEY is not configured, all calls raise WatsonxUnavailableError
so callers can fall back gracefully.

Endpoint: POST {WATSONX_URL}/ml/v1/text/generation?version=2023-05-29
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from src.backend.config import settings

logger = logging.getLogger(__name__)

GENERATION_API_VERSION = "2023-05-29"
DEFAULT_MODEL_ID = "ibm/granite-13b-instruct-v2"
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.3


class WatsonxUnavailableError(Exception):
    """Raised when watsonx.ai credentials are not configured."""


class WatsonxAPIError(Exception):
    """Raised when the watsonx.ai API returns a non-2xx response."""


def _get_iam_token() -> str:
    """
    Exchange the IBM Cloud API key for a short-lived IAM bearer token.

    IBM Cloud IAM token endpoint:
        POST https://iam.cloud.ibm.com/identity/token
    """
    resp = httpx.post(
        "https://iam.cloud.ibm.com/identity/token",
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": settings.watsonx_api_key,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def generate_text(
    prompt: str,
    model_id: str = DEFAULT_MODEL_ID,
    max_new_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """
    Call the watsonx.ai text generation API and return the generated text.

    Parameters
    ----------
    prompt : str
        The full prompt string to send to the model.
    model_id : str
        watsonx.ai model identifier.
    max_new_tokens : int
        Maximum tokens to generate.
    temperature : float
        Sampling temperature (0 = deterministic, 1 = creative).

    Returns
    -------
    str
        Generated text from the model.

    Raises
    ------
    WatsonxUnavailableError
        If WATSONX_API_KEY is not set.
    WatsonxAPIError
        If the API returns a non-2xx status code.
    """
    if not settings.watsonx_api_key:
        raise WatsonxUnavailableError("WATSONX_API_KEY is not configured")

    if not settings.watsonx_project_id:
        raise WatsonxUnavailableError("WATSONX_PROJECT_ID is not configured")

    # Get IAM token
    try:
        token = _get_iam_token()
    except httpx.HTTPError as exc:
        raise WatsonxAPIError(f"IAM token exchange failed: {exc}") from exc

    url = f"{settings.watsonx_url}/ml/v1/text/generation?version={GENERATION_API_VERSION}"

    payload: dict[str, Any] = {
        "model_id": model_id,
        "project_id": settings.watsonx_project_id,
        "input": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "stop_sequences": ["\n\n\n"],
        },
    }

    try:
        resp = httpx.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise WatsonxAPIError(f"watsonx.ai request failed: {exc}") from exc

    if resp.status_code != 200:
        raise WatsonxAPIError(
            f"watsonx.ai returned HTTP {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()
    try:
        return data["results"][0]["generated_text"].strip()
    except (KeyError, IndexError) as exc:
        raise WatsonxAPIError(
            f"Unexpected watsonx.ai response shape: {data}"
        ) from exc
