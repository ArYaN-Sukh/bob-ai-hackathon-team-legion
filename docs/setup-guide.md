# Setup Guide — TrialGuard

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11 | 3.14 not supported (pydantic-core wheel unavailable) |
| Node.js | 18+ | For the React frontend |
| Git | Any | |
| IBM Cloud account | Optional | Required for watsonx.ai CAPA generation |

---

## Step 1: Clone the Repository

```bash
git clone <repo-url>
cd bob-ai-hackathon-team-legion
```

---

## Step 2: Set Up the Python Backend

### 2a. Create virtual environment with Python 3.11

**Windows (PowerShell):**
```powershell
python3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2b. Install Python dependencies

```bash
pip install -r src/backend/requirements.txt
```

This installs: FastAPI, uvicorn, SQLAlchemy, pydantic, pydantic-settings, httpx, pytest, python-dotenv.

---

## Step 3: Configure Environment Variables

```bash
cp src/.env.example src/.env
```

Edit `src/.env`:

```bash
# Required for the backend to run (all have defaults if not set)
DATABASE_PATH=src/backend/data/trialguard.db
PROTOCOL_PATH=src/backend/data/protocol.json
APP_PORT=8000
APP_ENV=development

# Optional — required for AI-powered CAPA generation
# Without these, the CAPA endpoint returns a fallback template
WATSONX_API_KEY=your_ibm_cloud_api_key_here
WATSONX_PROJECT_ID=your_watsonx_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

> **Note:** The application works fully without watsonx.ai credentials. CAPA generation falls back to a structured template. Only the "Generate with AI" feature requires a real API key.

---

## Step 4: Seed the Database

```bash
python -m src.backend.seed.seed
```

This will:
- Drop and recreate all database tables
- Insert 1 trial, 6 sites, 60 patients, 240 visits, 1200 lab results, 125 adverse events
- Print a summary confirming all records were created

Expected output:
```
[OK] Trial: TRIAL-TG-001
[OK] Sites: 6
[OK] Patients: 60
...
```

---

## Step 5: Run Deviation Analysis

```bash
python -m src.backend.services.run_analysis
```

This will:
- Evaluate all 60 patients against the protocol
- Create ~158 deviation records
- Score all 6 sites (Site 003 should score ~628, High tier)
- Print the site risk summary table

Expected output (last section):
```
Site risk scores (highest first):
  Site            Score  Tier        Major  Minor  Admin
  SITE-003        627.9  High           30     31      0
  SITE-004        384.7  High           11     15      0
  ...
```

---

## Step 6: Start the Backend API Server

```bash
uvicorn src.backend.main:app --reload --port 8000
```

The API is now available at:
- **API Docs (Swagger UI):** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health
- **MCP endpoint:** http://localhost:8000/mcp

Test the health endpoint:
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"1.0.0","protocol_loaded":true}
```

---

## Step 7: Set Up the React Frontend

Open a **new terminal**:

```bash
cd src/frontend

# Install dependencies (ignore-scripts handles Node.js version compatibility)
npm install --ignore-scripts

# Fix esbuild binary (required after --ignore-scripts)
node node_modules/esbuild/install.js

# Start the development server
npm run dev
```

The dashboard is now at **http://localhost:5173**

---

## Step 8: Run the Test Suite

```bash
# From the repository root
python -m pytest src/backend/tests/ -v
```

Expected: **314 tests pass, 0 failures**.

---

## Step 9: Configure IBM Bob MCP Integration (Optional)

To connect IBM Bob to TrialGuard:

1. Copy `src/bob/mcp-config.json` to your Bob configuration directory
2. The MCP server URL is `http://localhost:8000/mcp`
3. In the Bob CLI, you can now use:
   - "Why is Site 003 at High risk?"
   - "Show Major deviations at SITE-003"
   - "Draft a CAPA for deviation #42"
   - "What is protocol rule INC-01?"

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: pydantic_core` | Use Python 3.11, not 3.14: `python3.11 -m venv .venv` |
| Windows encoding errors in seed | Set `$env:PYTHONIOENCODING="utf-8"` before running |
| `no such table` in tests | Tests use in-memory SQLite — this is expected; run pytest from repo root |
| Frontend CORS errors | Ensure backend is running on port 8000; Vite proxy handles CORS |
| esbuild binary missing | Run `node node_modules/esbuild/install.js` from src/frontend |
| CAPA shows fallback template | Set `WATSONX_API_KEY` and `WATSONX_PROJECT_ID` in .env |

---

## Re-seeding (Idempotent)

The seed script is fully idempotent. Run it any time to reset to a clean state:

```bash
python -m src.backend.seed.seed        # Reset data
python -m src.backend.services.run_analysis  # Re-run deviation detection
```

---

## Production Deployment Notes

For a production deployment (beyond hackathon scope):

1. Replace SQLite with PostgreSQL: change `DATABASE_PATH` to `postgresql://...`
2. Add authentication middleware (e.g., IBM App ID)
3. Build the React app: `npm run build` in `src/frontend`
4. Serve the `dist/` folder with nginx or similar
5. Use environment secrets management for watsonx.ai credentials
