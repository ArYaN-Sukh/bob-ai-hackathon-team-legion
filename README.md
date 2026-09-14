# TrialGuard — Clinical Trial Risk Monitor & Protocol Deviation Detector
### IBM Bob AI Hackathon — Team Legion

---

## 👥 Team

| Field | Value |
|---|---|
| Team Name | Team Legion |
| Track | AI |
| Team Lead | [Rohit Gohil] — [ACTUAL EMAIL] |
| Members | [Aryan Sukhadia], [Ved Vyas], [Aditya Shevale] |

---

## Overview

**TrialGuard** is an AI-augmented Clinical Trial Risk Monitor that automatically detects protocol deviations, classifies them by severity, scores sites for monitoring priority, and generates CAPA reports — all integrated with IBM Bob via Model Context Protocol (MCP).

> **Problem Statement:** P1 — Clinical Trial Risk Monitor & Protocol Deviation Detector

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Deterministic Deviation Engine** | 7 rule categories evaluated against protocol JSON — zero AI in compliance decisions |
| **Site Risk Scoring** | Weighted formula producing High/Medium/Low tier with explainable component breakdown |
| **IBM Bob MCP Integration** | 6 tools enabling natural language queries over live clinical trial data |
| **watsonx.ai CAPA Generator** | AI-drafted CAPA narratives with graceful fallback when API unavailable |
| **React Dashboard** | Site heatmap, patient timelines, deviation log, CAPA editor, Bob chat |

---

## Quick Start

```bash
# 1. Clone and set up Python environment
git clone <repo-url>
cd bob-ai-hackathon-team-legion
python3.11 -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r src/backend/requirements.txt

# 2. Seed the database
python -m src.backend.seed.seed

# 3. Run analysis (generate deviations + risk scores)
python -m src.backend.services.run_analysis

# 4. Start the API server
uvicorn src.backend.main:app --reload --port 8000

# 5. Start the frontend (separate terminal)
cd src/frontend
npm install --ignore-scripts && node node_modules/esbuild/install.js
npm run dev

# 6. Open http://localhost:5173
```

Full setup instructions: [docs/setup-guide.md](docs/setup-guide.md)

---

## 🖥️ Live Demo

| Demo Video | Live Demo |
|---|---|
| [🎥 Watch Demo on YouTube](https://youtu.be/y_KLZJUZFHQ) | [🌐 Open Live Demo](https://bob-ai-hackathon-team-legion-kohl.vercel.app) |


## 📸 Screenshots

| Dashboard | Site Risk & Deviations |
|---|---|
| <img src="demo/screenshots/Screenshot%202026-09-15%20032320.png" alt="TrialGuard Dashboard" width="500"> | <img src="demo/screenshots/Screenshot%202026-09-15%20032335.png" alt="Site Risk and Deviations" width="500"> |

| Patient Timeline | Ask Bob |
|---|---|
| <img src="demo/screenshots/Screenshot%202026-09-15%20032402.png" alt="Patient Timeline" width="500"> | <img src="demo/screenshots/Screenshot%202026-09-15%20032412.png" alt="Ask Bob" width="500"> |

## 🖥️ Presentation

| Presentation |
|---|
| 📊 **[View TrialGuard Hackathon Presentation](presentation/slides.pptx)** |


---

## Architecture

```
┌─────────────────────────────────────┐
│         React Frontend              │  Port 5173
│  Dashboard · Timeline · DevLog      │
│  CAPA Panel · Bob Chat              │
└──────────────┬──────────────────────┘
               │ REST /api/*  +  /mcp
┌──────────────▼──────────────────────┐
│         FastAPI Backend             │  Port 8000
│                                     │
│  ┌─────────────────────────────┐   │
│  │ Deterministic Rule Engine   │   │
│  │  - Protocol Loader          │   │
│  │  - Deviation Engine (7 cats)│   │
│  │  - Severity Classifier      │   │
│  │  - Risk Scorer              │   │
│  └────────────┬────────────────┘   │
│               │                     │
│  ┌────────────▼────────────────┐   │
│  │ SQLite Database (ORM)       │   │
│  │ 9 entities · 60 patients    │   │
│  │ 158+ deviations seeded      │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ IBM Bob MCP Server (/mcp)   │   │
│  │ 6 tools · JSON-RPC 2.0      │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ watsonx.ai Client           │   │
│  │ Granite-13B CAPA Generator  │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

---

## Technology Stack

- **Backend:** Python 3.11 · FastAPI · SQLAlchemy · SQLite · pydantic-settings
- **Frontend:** React 18 · TypeScript · Vite · Tailwind CSS · TanStack Query
- **AI:** IBM watsonx.ai (Granite-13B) · IBM Bob MCP integration
- **Testing:** pytest · 314 tests · FastAPI TestClient

---

## Demo Scenario

1. Open dashboard → 6 sites, Site 003 (London) shows red **High** badge (score 627)
2. Click Site 003 → 30 Major deviations, CAPA breakdown
3. Click Patient PT-0042 → eligibility breach (age 76), missed tumor assessment
4. Click "Generate CAPA" → watsonx.ai drafts root cause + corrective + preventive action
5. Open Bob Chat → ask "Why is Site 003 at High risk?" → Bob calls `get_site_risk_detail` MCP tool

---

## Project Structure

```
src/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── models.py            # 9 ORM entities
│   ├── schemas.py           # Pydantic response models
│   ├── engine/              # Deterministic rule engine
│   ├── routers/             # 8 API routers + MCP server
│   ├── services/            # Analysis, CAPA, watsonx client
│   ├── seed/                # Synthetic data generator
│   ├── data/                # protocol.json
│   └── tests/               # 314 pytest tests
├── frontend/                # React/TypeScript/Vite app
└── bob/                     # MCP configuration
    └── mcp-config.json
```

---

*Team Legion · IBM Bob AI Hackathon · P1 Clinical Trial Risk Monitor*
