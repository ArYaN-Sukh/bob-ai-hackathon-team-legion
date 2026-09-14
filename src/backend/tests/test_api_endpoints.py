"""
API endpoint tests for TrialGuard.

Uses FastAPI's TestClient (synchronous httpx-based test client) rather than
AsyncClient to keep tests simple and fast.

All tests use a fresh in-memory SQLite database seeded with a minimal dataset.
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models FIRST so they register with Base before create_all() is called
import src.backend.models  # noqa: F401

from src.backend.db import Base, get_db
from src.backend.models import CAPAStatus
from src.backend.main import app
from src.backend.models import (
    CAPA,
    AdverseEvent,
    ClinicalTrial,
    Deviation,
    DeviationSeverity,
    DeviationStatus,
    LabResult,
    Patient,
    RiskTier,
    Site,
    SiteRiskScore,
    Visit,
)

import datetime


# ─────────────────────────────────────────────────────────────────────────────
# Test database + client fixtures
#
# SQLite :memory: databases are connection-scoped — each new connection sees an
# empty DB.  We work around this by using a single shared connection for the
# entire test module.  All sessions are bound to that one connection.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def shared_connection():
    """A single SQLite :memory: connection that persists for the module."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    conn = engine.connect()
    Base.metadata.create_all(bind=conn)
    yield conn, engine
    conn.close()
    engine.dispose()


@pytest.fixture(scope="module")
def test_session_factory(shared_connection):
    conn, engine = shared_connection
    factory = sessionmaker(bind=conn, autocommit=False, autoflush=False)
    # Seed data once using a dedicated session
    seed_session = factory()
    try:
        _seed_test_data(seed_session)
    finally:
        seed_session.close()
    return factory


@pytest.fixture(scope="module")
def client(test_session_factory):
    def _override_get_db():
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Minimal seed data
# ─────────────────────────────────────────────────────────────────────────────

def _seed_test_data(db):
    today = datetime.date(2024, 1, 15)

    trial = ClinicalTrial(
        id="TRIAL-TEST-001",
        name="Test Trial",
        protocol_version="1.0",
        sponsor="Test Sponsor",
        phase="II",
        indication="NSCLC",
        start_date=datetime.date(2023, 1, 1),
        target_enrollment=20,
        primary_endpoint="PFS",
    )
    db.add(trial)

    site1 = Site(
        id="SITE-001",
        trial_id="TRIAL-TEST-001",
        name="Test Hospital",
        city="Boston",
        country="USA",
        principal_investigator="Dr. Test",
        status="ACTIVE",
        enrolled_count=5,
        target_enrollment=10,
    )
    site2 = Site(
        id="SITE-002",
        trial_id="TRIAL-TEST-001",
        name="Clean Site",
        city="Munich",
        country="Germany",
        principal_investigator="Dr. Clean",
        status="ACTIVE",
        enrolled_count=9,
        target_enrollment=10,
    )
    db.add_all([site1, site2])

    patient = Patient(
        id="PT-TEST-001",
        site_id="SITE-001",
        trial_id="TRIAL-TEST-001",
        age=55,
        sex="M",
        ecog_score=1,
        diagnosis_confirmed=True,
        active_infection=False,
        pregnant_or_breastfeeding=False,
        consent_signed_before_procedure=True,
        enrollment_date=datetime.date(2023, 2, 1),
        status="ENROLLED",
    )
    db.add(patient)

    visit = Visit(
        patient_id="PT-TEST-001",
        site_id="SITE-001",
        visit_number=1,
        visit_name="Screening",
        visit_type="SCHEDULED",
        scheduled_date=datetime.date(2023, 1, 15),
        actual_date=datetime.date(2023, 1, 20),
        window_deviation_days=5,
        completed_assessments=json.dumps(["vitals", "labs"]),
    )
    db.add(visit)
    db.flush()

    lab = LabResult(
        patient_id="PT-TEST-001",
        visit_id=visit.id,
        test_name="wbc",
        display_name="WBC",
        value=2.5,
        unit="10^9/L",
        reference_low=3.5,
        reference_high=10.5,
        collection_date=datetime.date(2023, 1, 20),
        is_out_of_range=True,
    )
    db.add(lab)

    ae = AdverseEvent(
        patient_id="PT-TEST-001",
        site_id="SITE-001",
        description="Grade 2 fatigue",
        onset_date=datetime.date(2023, 3, 1),
        sae_flag=False,
        expected_flag=True,
        reporting_delay_hours=12.0,
        severity_grade=2,
    )
    db.add(ae)

    dev = Deviation(
        patient_id="PT-TEST-001",
        site_id="SITE-001",
        rule_id="INC-01",
        deviation_type="Eligibility Criterion Violation",
        description="Patient age 76 exceeds maximum 75",
        severity=DeviationSeverity.MAJOR,
        status=DeviationStatus.OPEN,
        detected_date=datetime.date(2023, 2, 1),
        visit_id=None,
    )
    db.add(dev)
    db.flush()

    capa = CAPA(
        deviation_id=dev.id,
        site_id="SITE-001",
        status=CAPAStatus.OPEN,
        root_cause="Protocol not reviewed before enrollment",
        corrective_action="Review patient eligibility",
        preventive_action="Implement pre-enrollment checklist",
    )
    db.add(capa)

    risk = SiteRiskScore(
        site_id="SITE-001",
        score_date=today,
        major_open_count=3,
        minor_open_count=5,
        admin_open_count=1,
        avg_capa_age_days=45.0,
        data_query_rate_pct=60.0,
        enrollment_deviation_pct=50.0,
        total_score=75.5,
        risk_tier=RiskTier.HIGH,
    )
    db.add(risk)

    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_endpoint_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_status_ok(self, client):
        data = resp = client.get("/health")
        assert resp.json()["status"] == "ok"

    def test_root_endpoint(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        # Root endpoint returns HTML (React app) when frontend build exists,
        # otherwise returns JSON service info
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            # React frontend is being served
            assert b"<!doctype html>" in resp.content or b"<!DOCTYPE html>" in resp.content
        else:
            # Fallback JSON response
            assert resp.json()["service"] == "TrialGuard"


# ─────────────────────────────────────────────────────────────────────────────
# Trials
# ─────────────────────────────────────────────────────────────────────────────

class TestTrialsEndpoints:
    def test_list_trials(self, client):
        resp = client.get("/api/trials")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_get_trial(self, client):
        resp = client.get("/api/trials/TRIAL-TEST-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "TRIAL-TEST-001"

    def test_get_trial_not_found(self, client):
        resp = client.get("/api/trials/DOES-NOT-EXIST")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Sites
# ─────────────────────────────────────────────────────────────────────────────

class TestSitesEndpoints:
    def test_list_sites(self, client):
        resp = client.get("/api/sites")
        assert resp.status_code == 200
        sites = resp.json()
        assert len(sites) >= 2

    def test_site_has_risk_data(self, client):
        resp = client.get("/api/sites/SITE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latest_risk_score"] == 75.5
        assert data["latest_risk_tier"] == "High"   # RiskTier.HIGH.value == "High"

    def test_site_not_found(self, client):
        resp = client.get("/api/sites/SITE-999")
        assert resp.status_code == 404

    def test_site_risk_history(self, client):
        resp = client.get("/api/sites/SITE-001/risk-history")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_site_risk_history_has_score(self, client):
        resp = client.get("/api/sites/SITE-001/risk-history")
        scores = resp.json()
        assert scores[0]["total_score"] == 75.5

    def test_clean_site_has_no_risk_score(self, client):
        resp = client.get("/api/sites/SITE-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latest_risk_score"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Patients
# ─────────────────────────────────────────────────────────────────────────────

class TestPatientsEndpoints:
    def test_list_patients(self, client):
        resp = client.get("/api/patients")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_filter_patients_by_site(self, client):
        resp = client.get("/api/patients?site_id=SITE-001")
        assert resp.status_code == 200
        patients = resp.json()
        assert all(p["site_id"] == "SITE-001" for p in patients)

    def test_get_patient(self, client):
        resp = client.get("/api/patients/PT-TEST-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "PT-TEST-001"

    def test_patient_not_found(self, client):
        resp = client.get("/api/patients/PT-DOES-NOT-EXIST")
        assert resp.status_code == 404

    def test_patient_timeline(self, client):
        resp = client.get("/api/patients/PT-TEST-001/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert "visits" in data
        assert "all_deviations" in data
        assert "adverse_events" in data

    def test_patient_timeline_visits_count(self, client):
        resp = client.get("/api/patients/PT-TEST-001/timeline")
        data = resp.json()
        assert len(data["visits"]) >= 1

    def test_patient_timeline_deviations_attached(self, client):
        resp = client.get("/api/patients/PT-TEST-001/timeline")
        data = resp.json()
        assert len(data["all_deviations"]) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Deviations
# ─────────────────────────────────────────────────────────────────────────────

class TestDeviationsEndpoints:
    def test_list_deviations(self, client):
        resp = client.get("/api/deviations")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_filter_by_site(self, client):
        resp = client.get("/api/deviations?site_id=SITE-001")
        assert resp.status_code == 200
        devs = resp.json()
        assert all(d["site_id"] == "SITE-001" for d in devs)

    def test_filter_by_severity(self, client):
        resp = client.get("/api/deviations?severity=MAJOR")
        assert resp.status_code == 200
        devs = resp.json()
        assert all(d["severity"] == "Major" for d in devs)  # enum value is "Major"

    def test_filter_by_status(self, client):
        resp = client.get("/api/deviations?status=OPEN")
        assert resp.status_code == 200
        devs = resp.json()
        assert all(d["status"] == "Open" for d in devs)  # enum value is "Open"

    def test_get_deviation_by_id(self, client):
        # Get the first deviation's id
        devs = client.get("/api/deviations").json()
        dev_id = devs[0]["id"]
        resp = client.get(f"/api/deviations/{dev_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == dev_id

    def test_get_deviation_not_found(self, client):
        resp = client.get("/api/deviations/999999")
        assert resp.status_code == 404

    def test_patch_deviation_status(self, client):
        devs = client.get("/api/deviations").json()
        dev_id = devs[0]["id"]
        resp = client.patch(
            f"/api/deviations/{dev_id}",
            json={"status": "Pending Review"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Pending Review"
        # Restore
        client.patch(f"/api/deviations/{dev_id}", json={"status": "Open"})

    def test_patch_invalid_status(self, client):
        devs = client.get("/api/deviations").json()
        dev_id = devs[0]["id"]
        resp = client.patch(f"/api/deviations/{dev_id}", json={"status": "INVALID_STATUS_XYZ"})
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# CAPA
# ─────────────────────────────────────────────────────────────────────────────

class TestCapaEndpoints:
    def test_list_capas(self, client):
        resp = client.get("/api/capa")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_capas_by_site(self, client):
        resp = client.get("/api/capa?site_id=SITE-001")
        assert resp.status_code == 200
        capas = resp.json()
        assert all(c["site_id"] == "SITE-001" for c in capas)

    def test_get_capa_by_id(self, client):
        capas = client.get("/api/capa").json()
        if capas:
            capa_id = capas[0]["id"]
            resp = client.get(f"/api/capa/{capa_id}")
            assert resp.status_code == 200

    def test_update_capa(self, client):
        capas = client.get("/api/capa").json()
        if capas:
            capa_id = capas[0]["id"]
            resp = client.put(
                f"/api/capa/{capa_id}",
                json={"root_cause": "Updated root cause"},
            )
            assert resp.status_code == 200
            assert resp.json()["root_cause"] == "Updated root cause"

    def test_generate_capa_fallback(self, client):
        """Without watsonx API key, should return fallback narrative."""
        devs = client.get("/api/deviations").json()
        dev_id = devs[0]["id"]
        resp = client.post("/api/capa/generate", json={"deviation_id": dev_id})
        assert resp.status_code == 200
        data = resp.json()
        assert "narrative" in data
        assert len(data["narrative"]) > 50
        assert data["source"] in ("watsonx", "fallback")

    def test_generate_capa_invalid_deviation(self, client):
        resp = client.post("/api/capa/generate", json={"deviation_id": 999999})
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────────────────────

class TestReportsEndpoints:
    def test_get_site_report(self, client):
        resp = client.get("/api/reports/site/SITE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "report_markdown" in data
        assert "SITE-001" in data["report_markdown"]

    def test_report_contains_risk_section(self, client):
        resp = client.get("/api/reports/site/SITE-001")
        md = resp.json()["report_markdown"]
        assert "Risk Score" in md

    def test_report_not_found(self, client):
        resp = client.get("/api/reports/site/SITE-999")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# MCP
# ─────────────────────────────────────────────────────────────────────────────

class TestMcpEndpoints:
    def test_tools_list(self, client):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        tools = data["result"]["tools"]
        assert len(tools) == 6
        tool_names = [t["name"] for t in tools]
        assert "get_site_risk_detail" in tool_names
        assert "query_deviations" in tool_names
        assert "generate_capa" in tool_names
        assert "get_protocol_rule" in tool_names
        assert "analyse_site_trends" in tool_names
        assert "get_patient_timeline" in tool_names

    def test_tool_get_site_risk_detail(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "get_site_risk_detail", "arguments": {"site_id": "SITE-001"}}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        content = data["result"]["content"]
        json_content = next(c for c in content if c["type"] == "json")
        site_data = json_content["data"]
        assert site_data["site_id"] == "SITE-001"
        assert site_data["risk_tier"] == "High"   # RiskTier.HIGH.value == "High"

    def test_tool_query_deviations(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "query_deviations", "arguments": {"site_id": "SITE-001"}}
        })
        assert resp.status_code == 200
        data = resp.json()
        result = next(c for c in data["result"]["content"] if c["type"] == "json")["data"]
        assert "deviations" in result
        assert result["count"] >= 1

    def test_tool_get_patient_timeline(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "get_patient_timeline", "arguments": {"patient_id": "PT-TEST-001"}}
        })
        assert resp.status_code == 200
        data = resp.json()
        result = next(c for c in data["result"]["content"] if c["type"] == "json")["data"]
        assert result["patient_id"] == "PT-TEST-001"
        assert "visits" in result

    def test_tool_analyse_site_trends(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "analyse_site_trends", "arguments": {}}
        })
        assert resp.status_code == 200
        data = resp.json()
        result = next(c for c in data["result"]["content"] if c["type"] == "json")["data"]
        assert "sites" in result
        assert result["total_sites"] >= 2

    def test_tool_not_found(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 6, "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_unknown_method(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 7, "method": "unknown/method", "params": {}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    def test_tool_get_protocol_rule(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 8, "method": "tools/call",
            "params": {"name": "get_protocol_rule", "arguments": {"rule_id": "INC-01"}}
        })
        assert resp.status_code == 200
        data = resp.json()
        result = next(c for c in data["result"]["content"] if c["type"] == "json")["data"]
        assert result["rule_id"] == "INC-01"
        assert "open_violation_count" in result


# ─────────────────────────────────────────────────────────────────────────────
# Ask Bob (NVIDIA + fallback)
# ─────────────────────────────────────────────────────────────────────────────

class TestBobEndpoints:
    def test_bob_ask_site_risk_fallback(self, client, monkeypatch):
        """Ask Bob should use fallback when NVIDIA is not configured."""
        # Mock settings to ensure NVIDIA is not configured
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "")
        monkeypatch.setattr(config.settings, "nvidia_model", "")
        monkeypatch.setattr(config.settings, "nvidia_base_url", "")
        
        resp = client.post("/api/bob/ask", json={"question": "Why is SITE-001 at High risk?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "source" in data
        assert "tool_used" in data
        assert "tool_result" not in data  # Removed for security
        assert data["source"] == "fallback"  # NVIDIA not configured in tests
        assert data["tool_used"] == "get_site_risk_detail"
        assert "SITE-001" in data["response"]
        assert "High" in data["response"]

    def test_bob_ask_deviations_fallback(self, client, monkeypatch):
        """Ask Bob should handle deviation queries with fallback."""
        # Mock settings to ensure NVIDIA is not configured
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "")
        
        resp = client.post("/api/bob/ask", json={"question": "Show me deviations for SITE-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "source" in data
        assert "tool_used" in data
        assert "tool_result" not in data  # Removed for security
        assert data["source"] == "fallback"
        assert data["tool_used"] == "query_deviations"
        assert "deviation" in data["response"].lower()

    def test_bob_ask_empty_question(self, client):
        """Ask Bob should reject empty questions."""
        resp = client.post("/api/bob/ask", json={"question": ""})
        assert resp.status_code == 400

    def test_bob_ask_unintelligible(self, client):
        """Ask Bob should handle unintelligible questions gracefully."""
        resp = client.post("/api/bob/ask", json={"question": "xyzabc123 nonsense"})
        # Currently falls back to analyse_site_trends with 200
        assert resp.status_code in (200, 400)
        if resp.status_code == 200:
            data = resp.json()
            assert "response" in data
            assert "source" in data

    def test_bob_ask_greeting(self, client):
        """Ask Bob should handle greetings without calling tools."""
        resp = client.post("/api/bob/ask", json={"question": "hi"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "source" in data
        assert "tool_used" in data
        assert data["tool_used"] == "none"
        assert "Hello" in data["response"]
        assert "TrialGuard AI" in data["response"]
        # Should NOT contain reasoning text
        assert "thinking" not in data["response"].lower()
        assert "analyze" not in data["response"].lower()

    def test_bob_no_reasoning_in_response(self, client, monkeypatch):
        """Ask Bob responses should not contain visible reasoning."""
        # Mock settings to ensure NVIDIA is not configured
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "")
        
        resp = client.post("/api/bob/ask", json={"question": "Why is SITE-001 at High risk?"})
        assert resp.status_code == 200
        data = resp.json()
        response = data["response"]
        
        # Should NOT contain reasoning prefixes
        reasoning_prefixes = [
            "Here's a thinking process",
            "Thinking process",
            "Chain of thought",
            "Analysis:",
            "Let me think",
            "Let me analyze",
            "Step 1:",
            "Wait,",
            "I need to",
        ]
        
        for prefix in reasoning_prefixes:
            assert prefix not in response
        
        # Should contain actual content
        assert "SITE-001" in response
        assert "High" in response

    def test_bob_identity_question(self, client, monkeypatch):
        """Ask Bob should handle identity questions without calling MCP tools."""
        # Mock settings to ensure NVIDIA is not configured
        from src.backend import config
        monkeypatch.setattr(config.settings, "nvidia_api_key", "")
        
        resp = client.post("/api/bob/ask", json={"question": "which ai assistant model are you?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "source" in data
        assert "tool_used" in data
        assert data["tool_used"] == "none"
        assert "TrialGuard AI" in data["response"]
        assert data["source"] == "system"
        # Should NOT contain trial risk data
        assert "SITE-003" not in data["response"]
        assert "risk score" not in data["response"].lower()

    def test_bob_capability_question(self, client):
        """Ask Bob should handle capability questions without calling MCP tools."""
        resp = client.post("/api/bob/ask", json={"question": "what can you do?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "source" in data
        assert "tool_used" in data
        assert data["tool_used"] == "none"
        assert "TrialGuard AI" in data["response"]
        assert "site risk" in data["response"].lower()
        assert data["source"] == "system"

    def test_bob_unsupported_question(self, client):
        """Ask Bob should handle unsupported questions without calling MCP tools."""
        resp = client.post("/api/bob/ask", json={"question": "What is the weather?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "source" in data
        assert "tool_used" in data
        assert data["tool_used"] == "none"
        assert "TrialGuard AI" in data["response"]
        assert "clinical-trial risk monitoring" in data["response"].lower()
        assert data["source"] == "system"
