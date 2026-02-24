# ArchScan Deterministic

Deterministic architectural plan analysis and regulatory compliance checking.

## Quick Start

```bash
# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the service locally
python run.py
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs

# Run tests
python -m pytest tests/ -v
```

## Frontend (React UI)

```bash
cd frontend
npm install
npm run dev
# UI available at http://localhost:5173
```

The frontend connects to the backend at `http://localhost:8000`. Run both simultaneously:

```bash
# Terminal 1 — Backend
python run.py

# Terminal 2 — Frontend
cd frontend && npm run dev
```

### UI Screens

| Screen | Path | Description |
|--------|------|-------------|
| Projects | `/` | List, create, and manage projects |
| Project Detail | `/projects/:id` | Revisions, history, launch validation |
| Upload & Validate | `/projects/:id/validate` | Upload files, select ruleset, run validation |
| Findings | `/validations/:id/findings` | View findings, download PDF/JSON reports |
| Rulesets | `/rulesets` | List, create, inspect regulatory rulesets |
| Benchmarks | `/benchmarks` | Run benchmarks, view KPI metrics and gate status |

## Golden Dataset and Benchmarks

```bash
# Generate synthetic test PDFs
python scripts/generate_synthetic_pdfs.py

# Sync golden dataset (auto-download stable sources, flag manual ones)
python scripts/sync_dataset.py

# Dry-run (shows what would be downloaded without downloading)
python scripts/sync_dataset.py --dry-run

# Validate dataset completeness and checksums only
python scripts/sync_dataset.py --validate-only

# Run KPI benchmark against golden dataset
python scripts/run_benchmark.py

# Run golden regression tests
python -m pytest tests/golden/ -v
```

### KPI Release Gates

The benchmark evaluates these metrics and blocks release if any gate fails:

| Metric | Threshold | Unit |
|--------|-----------|------|
| Area MAE | <= 0.5 | % |
| Height/Distance MAE | <= 0.01 | m |
| Precision | >= 0.95 | ratio |
| Recall | >= 0.90 | ratio |

### Dataset Download Policy

Each entry in `golden-dataset/manifest.json` has a download policy:
- **auto** — stable GitHub/public sources fetched automatically with checksum verification
- **manual** — sources requiring license review or unstable links; place the file at the indicated path manually

Provenance is tracked in `golden-dataset/provenance.json` (auto-generated).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/projects` | Create a project |
| GET | `/projects` | List all projects |
| GET | `/projects/{id}` | Get project details |
| POST | `/projects/{id}/revisions` | Upload files (IFC/PDF) as a new revision |
| GET | `/projects/{id}/revisions` | List revisions |
| GET | `/projects/{id}/history` | Full project history |
| POST | `/validations` | Start a validation run |
| GET | `/validations/{id}` | Get validation status |
| GET | `/validations/{id}/findings` | Get validation findings |
| GET | `/validations/{id}/report` | Download PDF report |
| POST | `/rulesets` | Create a ruleset |
| GET | `/rulesets` | List rulesets |
| GET | `/rulesets/{id}` | Get ruleset (optionally by version) |
| POST | `/benchmarks/run` | Run KPI benchmark |
| GET | `/benchmarks` | List benchmark runs |
| GET | `/benchmarks/{id}` | Get benchmark results |
| POST | `/benchmarks/dataset/sync` | Sync golden dataset |
| GET | `/benchmarks/dataset/status` | Check dataset completeness |

## Deployment

The system runs on **Render** (backend) + **Netlify** (frontend) + **Neon** (Postgres).

| Service | URL | Auto-deploy |
|---------|-----|-------------|
| Backend API | `https://archscan.onrender.com` | On push to `main` |
| Frontend | `https://archscan-planandgo.netlify.app` | On push to `main` |
| Database | Neon Postgres (pooled) | N/A |

### Deploy flow

```
git push origin main
  ├── Render: builds & deploys backend (auto-deploy from main)
  ├── Netlify: builds & deploys frontend (auto-deploy from main)
  └── GitHub Actions: runs benchmark gate + smoke tests
```

### Environment variables

**Render** (backend only):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Neon pooled connection string |
| `ALLOWED_ORIGINS` | Comma-separated frontend domain(s) |

**Netlify** (frontend only):

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE_URL` | Backend URL (e.g. `https://archscan.onrender.com`) |

### Pre-deployment checklist

Before deploying, verify these environment variables are configured correctly:

| Where | Variable | Required value |
|-------|----------|---------------|
| Netlify → Environment variables | `VITE_API_BASE_URL` | `https://archscan.onrender.com` |
| Render → Environment | `DATABASE_URL` | Neon pooled connection string |
| Render → Environment | `ALLOWED_ORIGINS` | `https://archscan-planandgo.netlify.app` |

The frontend build will fail in CI if `VITE_API_BASE_URL` is missing or points to localhost (see `frontend/scripts/validate-env.js`). The backend logs a warning at startup if `ALLOWED_ORIGINS` is missing in production.

### Post-deploy verification

```bash
# Quick health check
curl https://archscan.onrender.com/health
# Expected: {"status":"ok","storage":"postgres"}

# Full smoke test
./scripts/smoke_prod.sh

# Custom API base
./scripts/smoke_prod.sh https://your-service.onrender.com
```

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `"storage":"file"` | `DATABASE_URL` not set in Render | Add env var in Render → Environment |
| CORS errors in browser | `ALLOWED_ORIGINS` missing or wrong | Set to Netlify domain in Render → Environment |
| Frontend shows blank / localhost errors | `VITE_API_BASE_URL` not set in Netlify | Add env var in Netlify → Environment variables, re-deploy |
| `channel_binding` error | Neon URL incompatibility | Already handled in code (`config.py`) |
| Deploy not triggered | Auto-deploy off | Check Render Settings → Build & Deploy → Auto-Deploy = Yes |

## ENV Security Policy

### Principles

- **Secrets live only in deploy platforms** (Render, Netlify) — never in the repo.
- **Frontend (VITE_\*)** vars are public by design — they are embedded into the JS bundle. Never put API keys, tokens, passwords, or DB URLs in `VITE_*` vars.
- **Backend** reads secrets from runtime environment only (`DATABASE_URL`, etc.). Logs mask sensitive values.

### What goes where

| Variable | Where to set | Public? |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Netlify env vars | Yes (just a URL) |
| `DATABASE_URL` | Render env vars | **No** (contains credentials) |
| `ALLOWED_ORIGINS` | Render env vars | Yes (just domain names) |
| Future API keys | Render env vars | **No** |

### Guardrails in place

| Guard | What it does |
|-------|-------------|
| `frontend/scripts/validate-env.js` | Fails build if `VITE_API_BASE_URL` is missing/localhost in CI, or if secret-looking `VITE_*` vars are detected |
| `src/app/config.py` | Warns at startup if production is missing `ALLOWED_ORIGINS`; masks DB URL in logs |
| `scripts/check_env_safety.sh` | Scans for secrets in frontend source, verifies .env files aren't staged in git |
| `scripts/init_env.sh` | Creates local `.env` from `.env.example` templates (never overwrites) |
| `.gitignore` | Blocks all `.env` files; only `.env.example` templates are tracked |

### Local setup

```bash
# First time: generate .env files from templates
./scripts/init_env.sh

# Before committing: run safety check
./scripts/check_env_safety.sh
```

## Project Structure

```
src/app/
  main.py              # FastAPI entrypoint
  config.py            # Tolerance, KPI thresholds, paths
  api/                 # HTTP endpoint handlers
  domain/models.py     # Pydantic domain contracts
  storage/repo.py      # Unified repository (auto-selects file vs Postgres)
  storage/pg_repo.py   # Postgres/Neon persistence (JSONB)
  storage/file_repo.py # JSON file-based persistence (local fallback)
  ingestion/           # IFC + PDF parsing adapters
  engine/              # Geometry engine + rule engine
  validation/          # Async validation worker
  reporting/           # PDF report generation
  dataset/             # Golden dataset manifest, fetcher, validator
  benchmark/           # KPI evaluator + benchmark runner
frontend/              # React + TypeScript UI (Vite)
data/                  # Local file-backed storage (auto-created)
data/benchmarks/       # Benchmark run results
rulesets/              # Versioned JSON rule definitions
golden-dataset/        # Golden dataset files + manifest + provenance
scripts/               # CLI tools (sync_dataset, run_benchmark, generate_synthetic_pdfs)
tests/                 # Unit + integration + golden regression tests
```

## Key Design Decisions

- **Dual storage** — Postgres (Neon) in production via `DATABASE_URL`, JSON files locally as fallback
- **Append-only revisions** — no overwrite allowed
- **Deterministic rule engine** — AI is only used for text extraction, never for compliance decisions
- **Full traceability** — every finding links to rule version, input facts, computation trace, and source files
- **Versioned rules** — rules filtered by effective date, can compare same project against different rule versions
- **KPI-gated releases** — benchmark must pass MAE/precision/recall/performance thresholds before deployment
- **Mixed download governance** — auto-fetch stable sources, flag manual ones with provenance tracking
