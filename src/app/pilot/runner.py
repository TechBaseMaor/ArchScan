"""Pilot learning program runner — executes Stage 0 end-to-end.

Usage:
    python -m src.app.pilot.runner [--corpus-dir DIR] [--output-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.app.pilot.corpus_manifest import build_manifest, save_manifest
from src.app.pilot.coverage_audit import run_coverage_audit, save_coverage_report
from src.app.pilot.ontology import build_seed_ontology, save_ontology

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CORPUS_DIR = "golden-dataset/from_alon_for_test"
DEFAULT_OUTPUT_DIR = "data/pilot-analysis"


def main(corpus_dir: str = DEFAULT_CORPUS_DIR, output_dir: str = DEFAULT_OUTPUT_DIR) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    logger.info("=== Stage 0: Pilot Learning Program ===")

    logger.info("--- Step 1: Building corpus manifest ---")
    manifest = build_manifest(corpus_dir)
    manifest_path = save_manifest(manifest, out / "pilot_corpus_manifest.json")
    logger.info("Manifest: %d files across %d formats", manifest.total_files, len(manifest.format_summary))

    logger.info("--- Step 2: Running extraction coverage audit ---")
    coverage = run_coverage_audit(manifest)
    coverage_path = save_coverage_report(coverage, out / "pilot_coverage_report.json")
    logger.info(
        "Coverage: %d facts from %d files, %d missing categories, %d gaps",
        coverage.total_facts_extracted,
        coverage.total_files_processed,
        len(coverage.missing_categories),
        len(coverage.gap_backlog),
    )

    logger.info("--- Step 3: Building seed ontology ---")
    ontology = build_seed_ontology()
    ontology_path = save_ontology(ontology, out / "planning_ontology_v1.json")
    logger.info("Ontology: %d terms across %d categories", len(ontology.terms), len(ontology.category_index))

    logger.info("--- Step 4: Generating rule gap backlog ---")
    gap_path = out / "rule_gap_backlog.json"
    gap_path.write_text(
        json.dumps(coverage.gap_backlog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Gap backlog: %d items saved to %s", len(coverage.gap_backlog), gap_path)

    logger.info("=== Stage 0 Complete ===")
    logger.info("Outputs written to: %s", out.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run pilot learning program (Stage 0)")
    parser.add_argument("--corpus-dir", default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    main(args.corpus_dir, args.output_dir)
