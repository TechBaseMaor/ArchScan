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
  ├── Netlify: builds & deploys frontend (npm ci, lockfile-driven)
  └── GitHub Actions:
       ├── Benchmark KPI Gate (tests + benchmarks)
       └── Production Release (preflight → deploy verify → smoke tests → fallback)
```

### Canonical release path

The **Production Release** workflow (`.github/workflows/release-production.yml`) is the
single source of truth for release health. Every push to `main` triggers it automatically.

**To release:**

```bash
git push origin main
# Watch: GitHub → Actions → "Production Release"
# Status: preflight → deploy-verify → smoke-tests → release-status
```

**To force a Netlify redeploy (incident recovery):**

```bash
# Go to GitHub → Actions → "Production Release" → Run workflow
# Check "Force Netlify redeploy" → Run
```

This triggers a CLI-based deploy that bypasses Netlify's auto-deploy pipeline entirely.

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
| Netlify deploy canceled | Concurrent builds or platform issue | Trigger manual redeploy via GitHub Actions |
| Backend 502/timeout after deploy | Render cold start (free tier) | Wait 2-3 min, or check Production Release workflow for auto-retry |
| Smoke tests fail but site looks fine | Transient network / cold start | Re-run Production Release via workflow_dispatch |

### Emergency redeploy procedure

If production is down and auto-deploy is not recovering:

1. **Frontend (Netlify):**
   - Go to GitHub → Actions → "Production Release" → Run workflow
   - Check "Force Netlify redeploy" → Run
   - This builds from the current `main` and deploys via `netlify-cli`, bypassing auto-deploy

2. **Backend (Render):**
   - Go to Render Dashboard → archscan → Manual Deploy → Deploy latest commit
   - Or: push an empty commit: `git commit --allow-empty -m "redeploy" && git push`

3. **Verify recovery:**
   ```bash
   curl https://archscan.onrender.com/health
   curl -s https://archscan-planandgo.netlify.app | grep ArchScan
   ```

### Rollback checklist

If a bad commit reaches production:

1. `git revert HEAD` (or the offending commit)
2. `git push origin main` — triggers auto-deploy + release workflow
3. Monitor GitHub Actions → "Production Release" for green status
4. Verify with `curl /health` and frontend bundle check

### Day-2 ops quick triage

Run these checks in order when something seems wrong:

```bash
# 1. Backend alive?
curl -sf https://archscan.onrender.com/health | python3 -c "import sys,json; print(json.load(sys.stdin))"

# 2. Postgres connected?
curl -sf https://archscan.onrender.com/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('storage')=='postgres', f'BAD: {d}'"

# 3. CORS allows frontend?
curl -s -D - -o /dev/null -X OPTIONS -H "Origin: https://archscan-planandgo.netlify.app" -H "Access-Control-Request-Method: GET" https://archscan.onrender.com/health | grep -i access-control

# 4. Frontend serving correct API target?
curl -sf https://archscan-planandgo.netlify.app | grep -c "localhost:8000" && echo "BAD: localhost in bundle" || echo "OK: no localhost"

# 5. API endpoints responding?
for p in /projects /rulesets; do echo -n "$p: "; curl -s -o /dev/null -w "%{http_code}" "https://archscan.onrender.com$p"; echo; done
```

### Known failure signatures

| Signature | Classification | Resolution |
|-----------|---------------|------------|
| `npm ci` fails with "missing lockfile" | Build config | Run `npm install` locally, commit `package-lock.json` |
| `VITE_API_BASE_URL` not set error | Env config | Set in Netlify → Site settings → Environment variables |
| `NETLIFY_AUTH_TOKEN secret not configured` | CI secret | Add `NETLIFY_AUTH_TOKEN` in GitHub → Settings → Secrets |
| Backend 503 for 5+ minutes | Platform issue | Check Render status page, try manual deploy |
| CORS header missing frontend origin | Backend env | Set `ALLOWED_ORIGINS` in Render to include Netlify domain |
| Smoke tests pass but frontend is blank | Frontend build error | Check Netlify deploy logs for build output |

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

### GitHub Secrets (for CI/CD)

| Secret | Purpose | Where to set |
|--------|---------|--------------|
| `NETLIFY_AUTH_TOKEN` | Enables fallback CLI deploy from GitHub Actions | GitHub → Settings → Secrets → Actions |

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
