# Solution Overview — TrialGuard

## Product Name: TrialGuard — Clinical Trial Risk Monitor & Protocol Deviation Detector

## Core Architectural Principle

TrialGuard is built on a deliberate separation of concerns that matters deeply in regulated clinical software:

> **All clinical compliance decisions are deterministic and rule-based.  
> AI (watsonx.ai via IBM Bob) is used exclusively for language tasks.**

This principle mirrors how GCP-compliant clinical software is actually built in regulated environments:
- Compliance decisions must be auditable, reproducible, and explainable to an FDA inspector
- AI narrative generation (CAPA text, risk explanation) is appropriate and valuable
- AI classification of whether a patient violated an eligibility criterion is NOT appropriate

---

## Two-Layer Architecture

### Layer 1: Deterministic Compliance Engine

The compliance engine compares patient/visit/lab records against a **versioned protocol JSON file** and produces structured deviation records. It:

1. **Loads the protocol** from `data/protocol.json` — inclusion/exclusion criteria, visit windows, lab thresholds, dosing rules, SAE reporting requirements
2. **Evaluates 7 rule categories** per patient:
   - Eligibility criteria (INC/EXC rules)
   - Visit window violations (±N days tolerance)
   - Missing required assessments
   - Lab threshold violations (severity-coded)
   - SAE reporting delays (> 24 hours)
   - Dosing compliance
3. **Classifies severity** from protocol rule definitions — Major/Minor/Administrative is defined in the protocol, not inferred
4. **Scores site risk** using a weighted formula: `(major×10) + (minor×3) + (admin×1) + (CAPA_age_months×5) + bounded_enrollment + bounded_data_query_rate`
5. **Persists results** to SQLite via SQLAlchemy ORM

### Layer 2: AI Narrative Layer (watsonx.ai + IBM Bob)

Once deviations are detected and classified deterministically, AI handles the language tasks:

1. **CAPA Narrative Generation:** A structured prompt including trial context, site risk tier, deviation details, and evidence is sent to IBM watsonx.ai (Granite-13B). The model generates a formatted CAPA report with root cause analysis, corrective action, and preventive action.

2. **IBM Bob MCP Integration:** 6 MCP tools expose live deviation data to IBM Bob, enabling conversational queries:
   - "Why is Site 003 at High risk?" → `get_site_risk_detail`
   - "Show me open Major deviations at Site 003" → `query_deviations`
   - "Draft a CAPA for the SAE reporting delay" → `generate_capa`
   - "What is rule INC-01?" → `get_protocol_rule`
   - "Summarise trends across all sites" → `analyse_site_trends`
   - "Walk me through PT-0042's visit history" → `get_patient_timeline`

---

## The Demo Story

The synthetic dataset is designed to tell a clear story:

**Site 003 — Royal London Hospital (Problem Site)**
- Risk score: **627.9** (High tier)
- 30 open Major deviations, 31 Minor
- Patient PT-0042: age 76, violating INC-01 (max age 75) + multiple lab violations
- CAPA age: ~400 days (deviations detected but unresolved)

**Site 005 — Munich University Clinic (Clean Site)**
- Risk score: **370.9** (High — purely from random lab deviations, demonstrating that even "clean" sites with high CAPA ages score High)
- No intentional violations seeded

**Site 003 vs All Others:** Site 003 scores 627 vs ≤390 for all other sites, making it unambiguously the highest priority monitoring target.

---

## Fallback Design

- If `WATSONX_API_KEY` is not set, `POST /api/capa/generate` returns a deterministic template CAPA text (not an error)
- If the MCP server is not reachable, the Bob Chat UI shows an appropriate error message
- All GET endpoints return real data from the SQLite database at all times

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Deterministic engine, not ML model | GCP compliance requires auditable, reproducible deviation detection |
| Protocol as JSON (not hardcoded) | Protocol versions change; serialised JSON supports versioning |
| Severity defined in protocol rules | Ensures severity mapping is auditable and not model-dependent |
| SQLite for demo | Simplifies setup; schema is PostgreSQL-compatible with engine URL change |
| MCP JSON-RPC 2.0 | Standard interface for IBM Bob tool integration |
| Piecewise enrollment risk model | Prevents enrollment shortfall from dominating risk score over compliance violations |
