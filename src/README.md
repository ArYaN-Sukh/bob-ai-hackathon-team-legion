# TrialGuard — Source Code

> **All data in this project is entirely synthetic.**
> No real patients, investigators, or clinical trial data are represented.
> This project is built for the IBM Bob AI Hackathon demo only.

---

## Backend Structure

```
src/backend/
├── config.py               # Environment variable loading (pydantic-settings)
├── db.py                   # SQLAlchemy engine, session factory, Base
├── models.py               # All ORM entities (9 models)
├── requirements.txt        # Python dependencies
│
├── data/
│   ├── protocol.json       # Trial protocol definition (committed to git)
│   └── trialguard.db       # SQLite database — gitignored, created by seed script
│
├── engine/                 # Deterministic compliance logic (Phase 2+)
│   └── __init__.py
│
├── routers/                # FastAPI route handlers (Phase 3+)
│   └── __init__.py
│
├── seed/
│   ├── synthetic_data.py   # Deterministic synthetic data generators
│   └── seed.py             # Orchestrates DB creation and data population
│
├── services/               # External service clients (Phase 4+)
│   └── __init__.py
│
└── tests/
    ├── test_protocol.py    # Protocol JSON structure tests
    ├── test_db.py          # Database initialization tests
    ├── test_models.py      # ORM model creation tests
    └── test_seed.py        # Seed script determinism and correctness tests
```

---

## Prerequisites

- **Python 3.11+**

Check your version:
```bash
python --version
```

---

## Setup

### 1. Create a virtual environment

```bash
# From the repository root
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (macOS / Linux)
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r src/backend/requirements.txt
```

### 3. Configure environment variables

```bash
# Copy the example file
cp src/.env.example .env

# Edit .env and fill in your watsonx.ai credentials
# (Required for Phase 4+ CAPA generation; not needed for Phase 1)
```

---

## Seed the Database

Run from the repository root:

```bash
python -m src.backend.seed.seed
```

This will:
1. Drop and recreate all tables in the SQLite database.
2. Populate the database with the complete synthetic dataset.
3. Print a verification summary.

**Expected output (excerpt):**
```
Verification summary:
  trials               1
  sites                6
  patients             60
  visits               240
  lab_results          1200
  adverse_events       ~30

  PT-0042:
    age       = 76  ✓
    site_id   = SITE-003  ✓

  SITE-003: ✓ found — Royal London Hospital — Phase II Oncology Unit
  SITE-005: ✓ found — Munich University Clinic — Thoracic Oncology
```

### Database location

The SQLite database is created at `src/backend/data/trialguard.db`.
This file is listed in `.gitignore` and is never committed to git.

---

## Protocol location

The trial protocol is stored at `src/backend/data/protocol.json`.
This file IS committed to git and defines all compliance rules used by the deviation engine.

---

## Run Tests

```bash
# From the repository root
pytest src/backend/tests/ -v
```

---

## Entities

| Model | Description |
|---|---|
| `ClinicalTrial` | Top-level trial (1 per demo dataset) |
| `Site` | Clinical research site (6 in demo) |
| `Patient` | Synthetic enrolled patient (60 in demo) |
| `Visit` | Protocol-defined visit per patient (4 per patient) |
| `LabResult` | Laboratory test result per visit |
| `AdverseEvent` | AE/SAE records |
| `Deviation` | Detected protocol deviation (written by engine) |
| `CAPA` | Corrective and Preventive Action record |
| `SiteRiskScore` | Computed site risk snapshot (written by engine) |
