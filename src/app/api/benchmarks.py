"""Benchmark API endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Request

from src.app.benchmark.kpi_models import BenchmarkRun, BenchmarkSummary
from src.app.benchmark.runner import list_benchmarks, load_benchmark, run_benchmark
from src.app.config import settings
from src.app.dataset.manifest_models import DatasetManifest
from src.app.dataset.source_registry import load_manifest
from src.app.dataset.fetcher import sync_dataset
from src.app.dataset.validator import validate_dataset
from src.app.i18n import resolve_locale, t

router = APIRouter()


@router.post("/run", response_model=BenchmarkRun)
async def start_benchmark(request: Request):
    locale = resolve_locale(request)
    manifest_path = settings.golden_dataset_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=t("error.manifest_not_found", locale))

    manifest = load_manifest(manifest_path)
    result = run_benchmark(manifest)
    return result


@router.get("", response_model=List[BenchmarkSummary])
async def get_benchmarks():
    return list_benchmarks()


@router.get("/{benchmark_id}", response_model=BenchmarkRun)
async def get_benchmark(benchmark_id: str, request: Request):
    locale = resolve_locale(request)
    run = load_benchmark(benchmark_id)
    if not run:
        raise HTTPException(status_code=404, detail=t("error.benchmark_not_found", locale))
    return run


@router.post("/dataset/sync")
async def sync_golden_dataset(request: Request, dry_run: bool = False, force: bool = False):
    locale = resolve_locale(request)
    manifest_path = settings.golden_dataset_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=t("error.manifest_not_found", locale))

    manifest = load_manifest(manifest_path)
    records = sync_dataset(manifest, dry_run=dry_run, force=force)
    return {
        "total": len(records),
        "results": [r.model_dump() for r in records],
    }


@router.get("/dataset/status")
async def dataset_status(request: Request):
    locale = resolve_locale(request)
    manifest_path = settings.golden_dataset_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=t("error.manifest_not_found", locale))

    manifest = load_manifest(manifest_path)
    result = validate_dataset(manifest)
    return result.to_dict()
