"""
Tests for database initialisation and connection.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from src.backend.db import Base, _make_engine, init_db, verify_db_connection


class TestDatabaseConnection:
    def test_verify_db_connection_default(self):
        """Default engine (points at settings.database_path) should connect."""
        assert verify_db_connection() is True

    def test_make_engine_sqlite_in_memory(self):
        engine = _make_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1
        engine.dispose()


class TestSchemaCreation:
    """Use a temporary SQLite file so tests don't touch the real database."""

    @pytest.fixture()
    def tmp_engine(self, tmp_path):
        db_file = tmp_path / "test_trialguard.db"
        engine = _make_engine(f"sqlite:///{db_file}")
        yield engine
        engine.dispose()

    def test_create_all_tables(self, tmp_engine, monkeypatch):
        """All ORM models should produce tables via create_all."""
        # Patch the module-level engine used by init_db
        import src.backend.db as db_module
        original_engine = db_module.engine
        db_module.engine = tmp_engine
        try:
            init_db(drop_existing=False)
            inspector = inspect(tmp_engine)
            tables = inspector.get_table_names()
        finally:
            db_module.engine = original_engine

        expected_tables = {
            "clinical_trials",
            "sites",
            "patients",
            "visits",
            "lab_results",
            "adverse_events",
            "deviations",
            "capas",
            "site_risk_scores",
        }
        assert expected_tables.issubset(set(tables)), \
            f"Missing tables: {expected_tables - set(tables)}"

    def test_drop_and_recreate(self, tmp_engine, monkeypatch):
        """drop_existing=True should produce a clean schema."""
        import src.backend.db as db_module
        original_engine = db_module.engine
        db_module.engine = tmp_engine
        try:
            init_db(drop_existing=False)
            init_db(drop_existing=True)  # Should not raise
            inspector = inspect(tmp_engine)
            tables = inspector.get_table_names()
        finally:
            db_module.engine = original_engine

        assert "patients" in tables


class TestForeignKeyEnforcement:
    """Verify SQLite FK enforcement pragma is active."""

    def test_foreign_keys_enabled(self, tmp_path):
        db_file = tmp_path / "fk_test.db"
        engine = _make_engine(f"sqlite:///{db_file}")
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys")).scalar()
        engine.dispose()
        assert result == 1, "foreign_keys pragma should be ON"
