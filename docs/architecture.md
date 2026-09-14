# Architecture — TrialGuard

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         IBM Bob CLI / Chat                        │
│              Natural language queries + CAPA requests             │
└────────────────────────────────┬─────────────────────────────────┘
                                  │  MCP JSON-RPC 2.0
                                  │  POST /mcp
┌──────────────────────────────────────────────────────────────────┐
│                   React Frontend (Vite + TypeScript)              │
│                          localhost:5173                           │
│                                                                   │
│  ┌───────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │  Dashboard    │  │ PatientTimeline│  │   BobChat (MCP)    │  │
│  │  (Risk Heatmap│  │ (Visit + Devs) │  │   (6 MCP tools)    │  │
│  │   + KPI Cards)│  │                │  │                    │  │
│  └───────────────┘  └────────────────┘  └────────────────────┘  │
│  ┌───────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │  SiteDetail   │  │  DeviationLog  │  │   CapaReport       │  │
│  │  + RiskCard   │  │  (Filter/Sort) │  │   + AI Narrative   │  │
│  └───────────────┘  └────────────────┘  └────────────────────┘  │
└────────────────────────────────┬─────────────────────────────────┘
                                  │  REST API + Vite proxy
                                  │  /api/* + /mcp
┌──────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (uvicorn)                       │
│                          localhost:8000                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     API Routers                           │   │
│  │  /api/trials  /api/sites  /api/patients  /api/deviations │   │
│  │  /api/capa    /api/analysis/run  /api/reports  /mcp      │   │
│  └───────────────┬──────────────────────────────────────────┘   │
│                  │                                                │
│  ┌───────────────┼──────────────────────────────────────────┐   │
│  │               │    Core Services                          │   │
│  │  ┌────────────▼───────────┐  ┌─────────────────────────┐ │   │
│  │  │  analysis_service.py   │  │  capa_generator.py      │ │   │
│  │  │  - run_full_analysis() │  │  - build_prompt()       │ │   │
│  │  │  - run_patient_analysis│  │  - generate_narrative() │ │   │
│  │  └────────────┬───────────┘  └──────────┬──────────────┘ │   │
│  │               │                          │                 │   │
│  └───────────────┼──────────────────────────┼─────────────── ┘   │
│                  │                          │                     │
│  ┌───────────────▼──────────────────┐  ┌───▼─────────────────┐  │
│  │    Deterministic Engine          │  │ watsonx_client.py   │  │
│  │                                  │  │                     │  │
│  │  protocol_loader.py              │  │ POST /ml/v1/text/   │  │
│  │  ├── load_protocol()             │  │   generation        │  │
│  │  └── Protocol dataclass          │  │                     │  │
│  │                                  │  │ Model:              │  │
│  │  deviation_engine.py             │  │ granite-13b-instruct│  │
│  │  ├── check_eligibility()         │  │ -v2                 │  │
│  │  ├── check_visit_windows()       │  │                     │  │
│  │  ├── check_lab_thresholds()      │  │ Fallback: template  │  │
│  │  ├── check_sae_reporting()       │  │ CAPA when no key    │  │
│  │  ├── check_dosing()              │  └─────────────────────┘  │
│  │  └── check_missing_assessments() │                            │
│  │                                  │                            │
│  │  severity_classifier.py          │                            │
│  │  └── classify(rule_id) → enum    │                            │
│  │                                  │                            │
│  │  risk_scorer.py                  │                            │
│  │  └── score_site(SiteInputs)      │                            │
│  │      → SiteRiskResult            │                            │
│  └───────────────┬──────────────────┘                            │
│                  │                                                │
│  ┌───────────────▼──────────────────────────────────────────┐   │
│  │                  SQLAlchemy ORM                           │   │
│  │  SQLite: src/backend/data/trialguard.db                   │   │
│  │                                                           │   │
│  │  ClinicalTrial → Site → Patient → Visit → LabResult      │   │
│  │                                  └──── AdverseEvent       │   │
│  │  Deviation ── Site + Patient + Visit                      │   │
│  │  CAPA ─────── Deviation                                   │   │
│  │  SiteRiskScore ── Site                                    │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow: Deviation Detection

```
1. Seed Script
   synthetic_data.py → 60 patients, 240 visits, 1200 lab results, 125 AEs
         │
         ▼
2. Analysis Trigger (POST /api/analysis/run or CLI)
         │
         ▼
3. For each Patient:
   protocol_loader.get_protocol() ──► Protocol dataclass (cached)
         │
         ▼
   evaluate_patient(patient, visits, labs, AEs, protocol)
         │
         ├── check_eligibility() ──── INC-01..05, EXC-01..03
         ├── check_visit_windows() ── Visit 1..4 ± tolerance
         ├── check_lab_thresholds() ─ WBC, Hgb, Plt, ALT, Cr
         ├── check_sae_reporting() ── delay > 24h → REP-01
         ├── check_dosing() ───────── DOS-01..03
         └── check_missing_assessments() ── required_assessments
                   │
                   ▼
            [DeviationResult, ...] ── dedup check ── INSERT Deviation rows
         │
         ▼
4. For each Site:
   _build_site_inputs(site, db) → SiteInputs
         │
         ▼
   score_site(SiteInputs) → SiteRiskResult
         │
         ▼
   UPSERT SiteRiskScore (score_date = today)
```

## Key Component Inventory

| Component | File | Purpose |
|-----------|------|---------|
| Protocol Loader | `engine/protocol_loader.py` | Parse protocol.json → Protocol dataclass |
| Deviation Engine | `engine/deviation_engine.py` | 7 rule evaluators, evaluate_patient() |
| Severity Classifier | `engine/severity_classifier.py` | rule_id → Major/Minor/Administrative |
| Risk Scorer | `engine/risk_scorer.py` | SiteInputs → SiteRiskResult + tier |
| Analysis Service | `services/analysis_service.py` | Connects engine to DB |
| CAPA Generator | `services/capa_generator.py` | Builds prompt + calls watsonx |
| watsonx Client | `services/watsonx_client.py` | IBM Cloud IAM + text generation |
| MCP Server | `routers/mcp.py` | 6 tools via JSON-RPC 2.0 |
| FastAPI App | `main.py` | CORS, lifespan, router mounts |
| ORM Models | `models.py` | 9 entities, enums, indexes |
| Seed Script | `seed/seed.py` | Idempotent synthetic data load |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `WATSONX_API_KEY` | For AI | IBM Cloud API key |
| `WATSONX_PROJECT_ID` | For AI | watsonx.ai project ID |
| `WATSONX_URL` | For AI | Regional endpoint (default: us-south) |
| `DATABASE_PATH` | Optional | SQLite file path (default: src/backend/data/trialguard.db) |
| `PROTOCOL_PATH` | Optional | Protocol JSON path |
| `APP_PORT` | Optional | Server port (default: 8000) |

## Test Coverage

- **314 pytest tests** across 10 test files
- Phase 1: `test_protocol.py` (30), `test_db.py` (5), `test_models.py` (18), `test_seed.py` (33)
- Phase 2: `test_protocol_loader.py` (43), `test_severity_classifier.py` (32), `test_deviation_engine.py` (57), `test_risk_scorer.py` (57)
- Phase 3: `test_api_endpoints.py` (44), `test_capa_generator.py` (15)
