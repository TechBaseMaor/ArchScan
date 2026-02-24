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

## Project Structure

```
src/app/
  main.py              # FastAPI entrypoint
  config.py            # Tolerance, KPI thresholds, paths
  api/                 # HTTP endpoint handlers
  domain/models.py     # Pydantic domain contracts
  storage/file_repo.py # JSON file-based persistence (no DB)
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

- **No database** — all state stored as JSON files under `data/`
- **Append-only revisions** — no overwrite allowed
- **Deterministic rule engine** — AI is only used for text extraction, never for compliance decisions
- **Full traceability** — every finding links to rule version, input facts, computation trace, and source files
- **Versioned rules** — rules filtered by effective date, can compare same project against different rule versions
- **KPI-gated releases** — benchmark must pass MAE/precision/recall/performance thresholds before deployment
- **Mixed download governance** — auto-fetch stable sources, flag manual ones with provenance tracking
