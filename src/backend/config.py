"""
Application configuration using pydantic-settings.
All secrets must be provided via environment variables or a .env file.
Never hardcode real credentials here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration object.  Values are read from environment variables
    first, then from a .env file in the repository root (if present).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── IBM watsonx.ai ────────────────────────────────────────────────────────
    watsonx_api_key: str = ""
    """IBM Cloud API key for watsonx.ai inference.  Required for CAPA generation."""

    watsonx_project_id: str = ""
    """watsonx.ai project ID.  Required for CAPA generation."""

    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    """watsonx.ai regional endpoint.  Defaults to US South."""

    # ── Database ──────────────────────────────────────────────────────────────
    database_path: str = "src/backend/data/trialguard.db"
    """Path to the SQLite database file, relative to the repository root."""

    database_url: str = ""
    """Optional SQLAlchemy URL. Set this to managed PostgreSQL in Vercel."""

    # ── Protocol ──────────────────────────────────────────────────────────────
    protocol_path: str = "src/backend/data/protocol.json"
    """Path to the trial protocol JSON file, relative to the repository root."""

    # ── Backend application ───────────────────────────────────────────────────
    app_port: int = 8000
    """Port on which the FastAPI application listens."""

    app_env: Literal["development", "production", "test"] = "development"
    """Runtime environment.  Controls debug logging and other behaviour."""

    # ── Frontend (consumed by Vite at build time) ─────────────────────────────
    vite_api_base_url: str = "http://localhost:8000/api"
    """Base URL for the React frontend to reach the FastAPI backend API."""

    # ── IBM Bob MCP ───────────────────────────────────────────────────────────
    bob_mcp_server_url: str = "http://localhost:8000/mcp"
    """URL at which the MCP server is exposed for IBM Bob tool calls."""

    # ── NVIDIA Nemotron (Ask Bob) ───────────────────────────────────────────────
    nvidia_api_key: str = ""
    """NVIDIA API key for Nemotron inference. Required for Ask Bob natural-language responses."""

    nvidia_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    """NVIDIA model identifier for Ask Bob."""

    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    """NVIDIA OpenAI-compatible API base URL."""

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def resolved_database_url(self) -> str:
        """Use an explicit managed database URL, or SQLite for local development."""
        return self.database_url or f"sqlite:///{self.database_path}"

    @property
    def watsonx_configured(self) -> bool:
        """True when both watsonx credentials are present."""
        return bool(self.watsonx_api_key and self.watsonx_project_id)

    @property
    def nvidia_configured(self) -> bool:
        """True when NVIDIA API key is present."""
        return bool(self.nvidia_api_key)

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


# Module-level singleton — import this everywhere
settings = Settings()
