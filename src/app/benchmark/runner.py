"""Benchmark runner — executes the golden dataset through the full pipeline and evaluates KPIs."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.app.benchmark.evaluator import evaluate_all
from src.app.benchmark.kpi_models import (
    BenchmarkRun,
    BenchmarkSummary,
    EntryResult,
    GateStatus,
)
from src.app.config import settings
from src.app.dataset.fetcher import get_ready_entries
from src.app.dataset.manifest_models import (
    DatasetEntry,
    DatasetManifest,
    ExpectedFinding,
    SourceFormat,
)
from src.app.domain.models import (
    ExtractedFact,
    Finding,
    Revision,
    RuleSet,
    SourceFile,
    ValidationRun,
)
from src.app.engine.rule_engine import evaluate_ruleset
from src.app.ingestion.ifc_adapter import extract_facts_from_ifc
from src.app.ingestion.pdf_adapter import extract_facts_from_pdf
from src.app.ingestion.dwfx_adapter import extract_facts_from_dwfx
from src.app.storage import repo

logger = logging.getLogger(__name__)


def run_benchmark(manifest: DatasetManifest, ruleset: Optional[RuleSet] = None) -> BenchmarkRun:
    """Execute full benchmark: ingest, validate, evaluate KPIs."""
    benchmark_id = uuid.uuid4().hex[:12]
    started_at = datetime.utcnow()

    if ruleset is None:
        ruleset = repo.get_ruleset(manifest.ruleset_id, manifest.ruleset_version)
        if ruleset is None:
            ruleset = repo.get_ruleset(manifest.ruleset_id)
        if ruleset is None:
            return BenchmarkRun(
                benchmark_id=benchmark_id,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                gate_status=GateStatus.FAIL,
                error_message=f"RuleSet {manifest.ruleset_id} not found",
            )

    ready_entries = get_ready_entries(manifest)
    entry_results: list[EntryResult] = []

    run = BenchmarkRun(
        benchmark_id=benchmark_id,
        started_at=started_at,
        total_entries=len(manifest.entries),
        skipped_entries=len(manifest.entries) - len(ready_entries),
    )

    for entry, file_path in ready_entries:
        result = _process_entry(entry, file_path, ruleset)
        entry_results.append(result)

    run.processed_entries = len(entry_results)
    run.entry_results = entry_results

    metrics, gate_status = evaluate_all(entry_results)
    run.metrics = metrics
    run.gate_status = gate_status
    run.completed_at = datetime.utcnow()

    _save_benchmark(run)
    return run


def _process_entry(entry: DatasetEntry, file_path: Path, ruleset: RuleSet) -> EntryResult:
    result = EntryResult(
        entry_id=entry.entry_id,
        category=entry.category.value,
        source_format=entry.source_format.value,
        baseline_status=entry.baseline_status.value,
    )

    try:
        t0 = time.monotonic()
        facts = _extract_facts(entry, file_path)
        result.ingestion_time_ms = (time.monotonic() - t0) * 1000
        result.facts_extracted = len(facts)

        t0 = time.monotonic()
        findings = evaluate_ruleset(
            ruleset=ruleset,
            facts=facts,
            project_id="benchmark",
            revision_id=entry.entry_id,
            validation_id=f"bench-{entry.entry_id}",
        )
        result.validation_time_ms = (time.monotonic() - t0) * 1000
        result.findings_produced = len(findings)

        _compute_geometry_errors(entry, facts, result)
        _compute_confusion_matrix(entry, findings, result)

    except Exception as exc:
        logger.exception("Error processing entry %s: %s", entry.entry_id, exc)
        result.errors.append(str(exc))

    return result


def _extract_facts(entry: DatasetEntry, file_path: Path) -> list[ExtractedFact]:
    if entry.source_format == SourceFormat.IFC:
        return extract_facts_from_ifc(str(file_path), entry.entry_id, entry.entry_id)
    elif entry.source_format == SourceFormat.PDF:
        return extract_facts_from_pdf(str(file_path), entry.entry_id, entry.entry_id)
    elif entry.source_format == SourceFormat.DWFX:
        return extract_facts_from_dwfx(str(file_path), entry.entry_id, entry.entry_id)
    return []


def _compute_geometry_errors(entry: DatasetEntry, facts: list[ExtractedFact], result: EntryResult) -> None:
    gt = entry.ground_truth
    if not gt:
        return

    area_facts = [f for f in facts if f.category == "area"]
    if gt.gross_area is not None and area_facts:
        measured = max(float(f.value) for f in area_facts)
        if gt.gross_area > 0:
            result.area_error_pct = abs(measured - gt.gross_area) / gt.gross_area * 100

    height_facts = [f for f in facts if f.category == "height"]
    if gt.max_height is not None and height_facts:
        measured = max(float(f.value) for f in height_facts)
        result.height_error_m = abs(measured - gt.max_height)


def _compute_confusion_matrix(entry: DatasetEntry, findings: list[Finding], result: EntryResult) -> None:
    """Compare produced findings against expected findings to get TP/FP/FN."""
    expected = entry.expected_findings
    if not expected:
        result.false_positives = len(findings)
        return

    produced_rules = {f.rule_ref.split(":")[0] for f in findings}
    expected_positive = {ef.rule_id for ef in expected if ef.expected}
    expected_negative = {ef.rule_id for ef in expected if not ef.expected}

    for rule_id in expected_positive:
        if rule_id in produced_rules:
            result.true_positives += 1
        else:
            result.false_negatives += 1

    for rule_ref in produced_rules:
        rule_id = rule_ref.split(":")[0] if ":" in rule_ref else rule_ref
        if rule_id not in expected_positive and rule_id not in expected_negative:
            result.false_positives += 1


def _save_benchmark(run: BenchmarkRun) -> None:
    import json
    from src.app.storage.file_repo import _JSONEncoder

    out_dir = settings.benchmark_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{run.benchmark_id}.json"
    path.write_text(
        json.dumps(run.model_dump(), cls=_JSONEncoder, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Benchmark %s saved to %s", run.benchmark_id, path)


def load_benchmark(benchmark_id: str) -> Optional[BenchmarkRun]:
    path = settings.benchmark_dir / f"{benchmark_id}.json"
    if not path.exists():
        return None
    import json
    raw = json.loads(path.read_text(encoding="utf-8"))
    return BenchmarkRun.model_validate(raw)


def list_benchmarks() -> list[BenchmarkSummary]:
    d = settings.benchmark_dir
    if not d.exists():
        return []
    results = []
    for f in sorted(d.glob("*.json")):
        import json
        raw = json.loads(f.read_text(encoding="utf-8"))
        run = BenchmarkRun.model_validate(raw)
        results.append(BenchmarkSummary(
            benchmark_id=run.benchmark_id,
            started_at=run.started_at,
            completed_at=run.completed_at,
            gate_status=run.gate_status,
            total_entries=run.total_entries,
            processed_entries=run.processed_entries,
            metrics=run.metrics,
        ))
    return results
