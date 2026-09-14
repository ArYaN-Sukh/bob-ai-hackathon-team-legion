# TrialGuard — Clinical Trial Risk Monitor & Protocol Deviation Detector
## IBM Bob AI Hackathon — Team Legion — Implementation Plan

> **Phase 1 STATUS: COMPLETE** — All 86 tests pass. Seed script verified.

---

## Overview

**Product name:** TrialGuard
**Problem statement:** P1 — Clinical Trial Risk Monitor & Protocol Deviation Detector
**Core architecture decision:** Deterministic rule-based logic handles all compliance classifications (auditable, explainable, appropriate for regulated clinical software). AI (watsonx.ai via IBM Bob) is used exclusively for language tasks: CAPA narrative generation, risk explanation, and natural language Q&A over structured data.

**Stack:** Python 3.11 + FastAPI + SQLAlchemy + SQLite (backend) | React 18 + Vite + TypeScript + TailwindCSS (frontend) | IBM Bob MCP integration | watsonx.ai Granite model

---

## Sub-Task 1 — Protocol Definition and Data Model

**Status:** [x] done

**Intent:**
Define the trial protocol as a versioned JSON file and create all SQLAlchemy ORM models. This is the foundation everything else depends on.

**Expected Outcomes:**
- `src/backend/data/protocol.json` exists with a complete Phase II Oncology trial definition including inclusion/exclusion criteria, visit schedule, lab thresholds, dosing rules, and SAE reporting rules.
- `src/backend/models.py` defines all ORM tables: ClinicalTrial, Site, Patient, Visit, LabResult, AdverseEvent, Deviation, CAPA, SiteRiskScore.
- `src/backend/db.py` creates the SQLite engine and session factory.
- `src/backend/config.py` loads environment variables using pydantic-settings.

**Todo list:**
- [ ] Create `src/backend/data/protocol.json` with trial metadata, 3+ inclusion criteria, 2+ exclusion criteria, 4-visit schedule with window tolerances, 3+ lab thresholds, 2+ dosing rules, SAE reporting rule
- [ ] Create `src/backend/config.py` loading env vars: WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_URL, DATABASE_PATH, PROTOCOL_PATH, APP_PORT
- [ ] Create `src/backend/db.py` with SQLAlchemy engine pointed at DATABASE_PATH, session factory, and Base declarative class
- [ ] Create `src/backend/models.py` with all 9 ORM models
- [ ] Create `src/backend/requirements.txt` with: fastapi, uvicorn, sqlalchemy, pydantic, pydantic-settings, httpx, pytest, pytest-asyncio

**Relevant context:**
- Protocol JSON schema is defined in the Implementation Plan section 7.
- All entity fields and types are defined in section 6.
- DATABASE_PATH defaults to `src/backend/data/trialguard.db` (gitignored).

---

## Sub-Task 2 — Synthetic Data Seed Script

**Status:** [x] done

**Intent:**
Generate a deterministic, story-driven synthetic dataset that gives the demo a clear narrative: one problem site (Site 003 — London), one clean site (Site 005 — Munich), and one patient (PT-0042) with multiple documented deviations.

**Expected Outcomes:**
- Running `python src/backend/seed/seed.py` creates a fresh SQLite database and populates it with the full synthetic dataset.
- The script is idempotent: re-running drops and recreates all data.
- Dataset produces 2 High-risk sites, 2 Medium-risk sites, and 2 Low-risk sites when the risk scorer runs.
- Patient PT-0042 at Site 003 has an eligibility breach (age 76, rule INC-01) and a missed primary endpoint assessment.
- At least 2 SAE records exist, one with a reporting delay > 24 hours.

**Todo list:**
- [ ] Create `src/backend/seed/synthetic_data.py` with generator functions for each entity type
- [ ] Seed 1 trial, 6 sites, 60 patients (10 per site), 4 visits per patient
- [ ] Seed 2 lab results per visit (~ 480 total), with ~8% out-of-range
- [ ] Seed ~30 adverse events with ~5 flagged as SAE, 2 with reporting delay > 24h
- [ ] Ensure Site 003 patients have intentional visit window violations (3+ days late) and missing assessments
- [ ] Ensure Site 005 patients have clean data (all visits on time, all assessments complete)
- [ ] Create `src/backend/seed/seed.py` as the orchestrator: drops tables, recreates schema, calls all generators
- [ ] Add seed invocation instructions to `src/README.md`

**Relevant context:**
- Site 003 must score >= 60 (High) after risk scoring. Pre-seed with major_open_deviations = 3, avg_capa_age_days = 47, data_query_rate = 15%.
- Site 005 must score < 30 (Low). Pre-seed with 1 minor deviation, all CAPAs closed.
- Patient PT-0042 age must be set to 76 (violates INC-01 which requires 18-75).

---

## Sub-Task 3 — Deviation Detection Engine

**Status:** [x] done

**Intent:**
Implement the deterministic rule evaluator that compares patient/visit/lab records against the loaded protocol and produces Deviation records. This is the technical core of the system.

**Expected Outcomes:**
- `src/backend/engine/protocol_loader.py` parses and validates protocol.json into a Protocol dataclass.
- `src/backend/engine/deviation_engine.py` evaluates 6 rule categories and returns DeviationResult objects.
- `src/backend/engine/severity_classifier.py` maps rule_id to Major/Minor/Administrative.
- `src/backend/engine/risk_scorer.py` applies the weighted formula and returns a risk score + tier.
- Unit tests pass for all engine modules.

**Todo list:**
- [ ] Create `src/backend/engine/protocol_loader.py` with Protocol and Rule dataclasses, JSON parser, validation
- [ ] Create `src/backend/engine/deviation_engine.py` with evaluators for: visit window, missing assessments, lab thresholds, eligibility criteria, SAE reporting delay, dosing violations
- [ ] Create `src/backend/engine/severity_classifier.py` with rule_id → severity lookup
- [ ] Create `src/backend/engine/risk_scorer.py` with the weighted formula: major*10 + minor*3 + admin*1 + capa_age_months*5 + data_query_rate*2 + enrollment_deviation*2
- [ ] Create `src/backend/tests/test_protocol_loader.py`
- [ ] Create `src/backend/tests/test_deviation_engine.py` (test each rule type; verify PT-0042 eligibility breach detected as Major)
- [ ] Create `src/backend/tests/test_severity_classifier.py`
- [ ] Create `src/backend/tests/test_risk_scorer.py` (verify Site 003 = High, Site 005 = Low)

**Relevant context:**
- Risk score formula: (major_open * 10) + (minor_open * 3) + (admin_open * 1) + (avg_capa_age_days/30 * 5) + (data_query_rate_pct * 2) + (enrollment_deviation_pct * 2)
- Tier thresholds: >= 60 = High, 30-59 = Medium, < 30 = Low
- Severity is assigned at rule level in protocol.json ("severity_if_violated"), not inferred by AI.

---

## Sub-Task 4 — FastAPI Backend and All Routers

**Status:** [x] done

**Intent:**
Wire up all FastAPI routers and connect them to the database and engine modules. At the end of this phase, the backend serves real data for all dashboard views.

**Expected Outcomes:**
- `uvicorn src.backend.main:app --reload` starts successfully.
- All GET endpoints return correctly shaped JSON from the SQLite database.
- `POST /api/analysis/run` runs the deviation engine across all patients and stores results.
- `POST /api/patients/{id}/analyse` runs analysis for one patient.
- CORS is configured to allow the Vite dev server (localhost:5173).

**Todo list:**
- [ ] Create `src/backend/main.py` with FastAPI app, CORS middleware, router mounts, startup event that loads protocol
- [ ] Create `src/backend/routers/trials.py`: GET /api/trials, GET /api/trials/{id}/protocol
- [ ] Create `src/backend/routers/sites.py`: GET /api/sites, GET /api/sites/{id}, GET /api/sites/{id}/risk-history
- [ ] Create `src/backend/routers/patients.py`: GET /api/patients, GET /api/patients/{id}, GET /api/patients/{id}/timeline, POST /api/patients/{id}/analyse
- [ ] Create `src/backend/routers/deviations.py`: GET /api/deviations (filterable by severity, status, site_id, patient_id), GET /api/deviations/{id}
- [ ] Create `src/backend/routers/capa.py`: GET /api/capa, GET /api/capa/{id}, PUT /api/capa/{id}, POST /api/capa/generate (calls watsonx)
- [ ] Create `src/backend/routers/reports.py`: GET /api/reports/site/{id} (returns markdown report)
- [ ] Create `src/backend/routers/analysis.py`: POST /api/analysis/run
- [ ] Add `src/backend/tests/test_api_endpoints.py` using httpx AsyncClient

**Relevant context:**
- All routers use SQLAlchemy session via FastAPI dependency injection (Depends(get_db)).
- The analysis/run endpoint should call deviation_engine, write Deviation rows, then call risk_scorer, write SiteRiskScore rows.
- Response models should use Pydantic schemas (separate from ORM models).

---

## Sub-Task 5 — watsonx.ai Integration and CAPA Generator

**Status:** [ ] pending

**Intent:**
Implement the watsonx.ai client and CAPA narrative generator. This enables the AI-powered features: CAPA report drafting and natural language site risk explanation.

**Expected Outcomes:**
- `POST /api/capa/generate` with a deviation_id calls watsonx.ai and returns a structured CAPA narrative.
- If watsonx.ai is unavailable (no API key), the endpoint returns a fallback template string (not an error).
- The prompt includes: trial name, site name, patient ID, deviation description, rule ID, site risk history.
- The watsonx response is stored in `CAPA.watsonx_narrative`.

**Todo list:**
- [ ] Create `src/backend/services/watsonx_client.py` wrapping the watsonx.ai REST inference endpoint (POST to /ml/v1/text/generation)
- [ ] Create `src/backend/services/capa_generator.py` with: template selector (deviation_type → template category), prompt builder, watsonx call, response parser
- [ ] Wire `POST /api/capa/generate` in capa.py router to call capa_generator
- [ ] Implement graceful fallback: if WATSONX_API_KEY is empty, return placeholder CAPA text
- [ ] Create `src/backend/tests/test_capa_generator.py` with mocked watsonx call

**Relevant context:**
- Model: `ibm/granite-13b-instruct-v2` (or `ibm/granite-20b-multilingual`).
- watsonx.ai endpoint: `{WATSONX_URL}/ml/v1/text/generation?version=2023-05-29`
- Request body requires: `model_id`, `input`, `parameters` (max_new_tokens, temperature).
- Prompt template is defined in Implementation Plan section 11.

---

## Sub-Task 6 — IBM Bob MCP Server

**Status:** [ ] pending

**Intent:**
Expose a JSON-RPC MCP endpoint so IBM Bob can call TrialGuard tools conversationally. This is the primary IBM Bob integration and the most judged component of the submission.

**Expected Outcomes:**
- `POST /mcp` handles MCP JSON-RPC tool calls from Bob.
- 6 tools are registered and functional: get_site_risk_detail, query_deviations, generate_capa, get_protocol_rule, analyse_site_trends, get_patient_timeline.
- `src/bob/mcp-config.json` contains the MCP server registration pointing to localhost:8000/mcp.
- Bob can answer "Why is Site 003 at High risk?" using live data from the MCP tool.

**Todo list:**
- [ ] Create `src/backend/routers/mcp.py` with MCP JSON-RPC handler (POST /mcp)
- [ ] Implement tool: `get_site_risk_detail(site_id)` — returns risk score breakdown, open deviation counts, CAPA status
- [ ] Implement tool: `query_deviations(site_id?, patient_id?, severity?, status?)` — returns filtered deviation list
- [ ] Implement tool: `generate_capa(deviation_id)` — triggers CAPA generator, returns narrative
- [ ] Implement tool: `get_protocol_rule(rule_id)` — returns rule definition and violation count
- [ ] Implement tool: `analyse_site_trends(days, deviation_type?)` — returns cross-site summary
- [ ] Implement tool: `get_patient_timeline(patient_id)` — returns ordered visit + deviation timeline
- [ ] Create `src/bob/mcp-config.json` with server registration
- [ ] Register mcp router in main.py

**Relevant context:**
- MCP server config format:
  ```json
  {
    "mcpServers": {
      "trialguard": {
        "type": "http",
        "url": "http://localhost:8000/mcp",
        "description": "TrialGuard clinical trial risk monitor"
      }
    }
  }
  ```
- MCP tools must return structured JSON (not plain text) so Bob's model can process and narrate.
- The MCP endpoint should list available tools when called with method "tools/list".

---

## Sub-Task 7 — React Frontend

**Status:** [ ] pending

**Intent:**
Build the React dashboard that visualises all compliance data. This is the primary interface for the demo video and screenshots.

**Expected Outcomes:**
- `npm run dev` starts the Vite dev server on localhost:5173.
- Dashboard page shows 6 sites with risk tier colour coding (red/yellow/green).
- Site detail page shows deviation list and risk breakdown.
- Patient timeline page shows visit-by-visit compliance with deviation badges.
- CAPA panel shows generated narrative with edit capability.
- All pages load real data from the FastAPI backend.

**Todo list:**
- [ ] Scaffold Vite + React + TypeScript project in `src/frontend/`
- [ ] Install: tailwindcss, shadcn/ui, @tanstack/react-query, recharts, axios, react-router-dom
- [ ] Create `src/frontend/src/api/client.ts` with typed API call functions for all endpoints
- [ ] Create `src/frontend/src/types/index.ts` mirroring all backend entity shapes
- [ ] Create Dashboard.tsx: site list table with risk tier badge, KPI cards (total deviations, open CAPAs, high-risk sites)
- [ ] Create SiteDetail.tsx: deviation list table, risk score card, enrolment table, CAPA status list
- [ ] Create PatientTimeline.tsx: vertical visit timeline with deviation badges colour-coded by severity
- [ ] Create DeviationLog.tsx: filterable/sortable table with severity filter, status filter
- [ ] Create CapaReport.tsx: deviation detail + AI-generated CAPA with edit fields + download button
- [ ] Create BobChat.tsx: simple chat interface that calls the MCP endpoint directly for demo purposes
- [ ] Create shared components: RiskScoreCard, DeviationBadge, Navbar, EmptyState
- [ ] Add React Router routes for all pages
- [ ] Create `src/frontend/package.json` with all dependencies

**Relevant context:**
- Severity colour coding: Major = red (#EF4444), Minor = amber (#F59E0B), Administrative = blue (#3B82F6).
- Risk tier colour coding: High = red, Medium = yellow, Low = green.
- Use TanStack Query for all data fetching with loading and error states.
- The BobChat page is for demo purposes to show Bob interaction in the UI; the primary Bob interaction is via the Bob CLI.

---

## Sub-Task 8 — Documentation, Screenshots, and Submission Files

**Status:** [ ] pending

**Intent:**
Complete all required documentation files, take the 5 planned screenshots, and fill in submission.yaml and README.md so the GitHub Actions CI passes.

**Expected Outcomes:**
- `submission.yaml` fully populated, GitHub Actions Validate Submission is green.
- `README.md` has no placeholder brackets remaining.
- All four docs/ files contain real content (not template text).
- `demo/screenshots/` contains at least 3 PNG screenshots of the running application.
- `demo/demo-video-link.txt` contains a real video URL.
- `src/.env.example` updated with all real variable names.

**Todo list:**
- [ ] Fill in `submission.yaml`: team details, title "TrialGuard", track "AI", problem_statement, solution_summary, key_features (5), tech_stack
- [ ] Rewrite `README.md`: replace all placeholders with real TrialGuard content
- [ ] Write `docs/problem-statement.md`: reference ICH E6 GCP guidelines, FDA inspection findings, clinical trial deviation rates
- [ ] Write `docs/solution-overview.md`: describe deterministic engine + AI narrative layer architecture
- [ ] Write `docs/architecture.md`: replace generic Mermaid with real TrialGuard component diagram
- [ ] Write `docs/setup-guide.md`: step-by-step from git clone to running dashboard + Bob demo
- [ ] Update `src/.env.example` with all real variable names and descriptions
- [ ] Update `src/README.md` with actual src/ layout
- [ ] Take 5 screenshots per the screenshot plan (section 21 of this plan)
- [ ] Record 3-5 minute demo video per the demo scenario (section 20 of this plan)
- [ ] Update `demo/demo-video-link.txt` with real video URL
- [ ] Update `demo/live-demo-url.txt` with "NOT DEPLOYED — run locally using docs/setup-guide.md"
- [ ] Add `presentation/slides.pdf` (or .pptx)
- [ ] Verify GitHub Actions CI is green on push

**Relevant context:**
- submission.yaml track must be exactly "AI" (one of: AI | DevOps | Sustainability | Open).
- CI checks: README.md must not contain "[Your Project Title Here]" or "[Your Team Name]".
- CI checks: demo/demo-video-link.txt line 1 must not contain "your-demo-video-link-here".
- CI checks: src/ must have at least 1 file that is not README.md or .env.example.
- Screenshot plan is in section 21 of this document.
- Demo scenario script is in section 20 of this document.

---

## Demo Scenario Script

Narrative: "Sarah, a CRA, reviews TrialGuard before a monitoring visit to Site 003 in London."

| Step | Action | Expected Result |
|---|---|---|
| 1 | Open http://localhost:5173 | Risk dashboard with 6 sites; Site 003 shows red High badge |
| 2 | Click Site 003 | Site detail: 12 open deviations, 3 Major, CAPA age 47 days, risk score 74 |
| 3 | Click Patient PT-0042 | Timeline: Visit 1 eligibility breach (red Major badge), Visit 2 missed ECG (amber Minor badge) |
| 4 | Click "Generate CAPA" on eligibility breach | Loading spinner, then watsonx.ai-generated root cause + corrective + preventive action text |
| 5 | Go to Deviation Log, filter Major + Open | Table of 8 major deviations across all sites |
| 6 | Open Bob CLI, type: "Why is Site 003 at High risk?" | Bob calls get_site_risk_detail MCP tool, returns narrative explanation citing 3 major deviations and 47-day CAPA age |
| 7 | Type: "Draft a CAPA for the SAE reporting delay at Site 003" | Bob calls generate_capa, returns drafted CAPA |
| 8 | Go to Reports, click "Generate Site Report" for Site 003 | Markdown monitoring report with all deviations, risk score, and open CAPAs |

---

## Screenshot Plan

| # | Filename | Content |
|---|---|---|
| 01 | `01-site-risk-dashboard.png` | Full dashboard: 6 sites, risk heatmap, KPI cards (total deviations, open CAPAs, high-risk sites) |
| 02 | `02-site-003-detail.png` | Site 003 detail page: deviation list, risk score 74 (High), CAPA status table |
| 03 | `03-patient-timeline.png` | PT-0042 visit timeline with red eligibility breach badge and amber missed assessment badge |
| 04 | `04-capa-generation.png` | CAPA panel with watsonx.ai-generated narrative visible on screen |
| 05 | `05-bob-interaction.png` | Bob CLI or BobChat UI showing the question and AI response about Site 003 |

---

## Risk Score Formula Reference

```
risk_score = (major_open_deviations   * 10)
           + (minor_open_deviations   *  3)
           + (admin_open_deviations   *  1)
           + (avg_capa_age_days / 30  *  5)
           + (data_query_rate_pct     *  2)
           + (enrollment_deviation_pct*  2)

Tier: >= 60 = High | 30-59 = Medium | < 30 = Low
```

---

## Environment Variables Reference

```bash
# IBM watsonx.ai
WATSONX_API_KEY=your_ibm_cloud_api_key
WATSONX_PROJECT_ID=your_watsonx_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com

# Backend
APP_PORT=8000
APP_ENV=development
DATABASE_PATH=src/backend/data/trialguard.db
PROTOCOL_PATH=src/backend/data/protocol.json

# Frontend (Vite)
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## Judging Criteria Mapping

| Criterion | Points | How TrialGuard addresses it |
|---|---|---|
| Technical Implementation Quality | 25 | Deterministic rule engine, typed FastAPI, SQLAlchemy ORM, React+TypeScript, pytest suite with 6+ test files, real watsonx.ai calls |
| Innovation and Differentiation | 25 | Separation of deterministic compliance logic from AI narrative layer (correct architecture for regulated software); leading-indicator risk scoring |
| Problem Depth and Vision | 15 | docs/problem-statement.md references ICH E6 GCP guidelines and real FDA inspection failure modes; data model uses correct clinical operations terminology |
| Working Demo and Functionality | 15 | Seed data tells a designed story; demo scenario is scripted and produces visible non-trivial output at every step |
| IBM Bob Integration | 10 | Bob is registered as MCP consumer with 6 real tools; performs analytical queries and CAPA generation from live data |
| Documentation and Reproducibility | 10 | setup-guide.md tested end-to-end; seed script is idempotent; .env.example complete; GitHub Actions CI green |
