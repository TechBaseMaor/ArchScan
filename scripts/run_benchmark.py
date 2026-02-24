"""CLI script to run the golden dataset benchmark and evaluate KPIs."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app.config import settings
from src.app.dataset.source_registry import load_manifest
from src.app.benchmark.runner import run_benchmark


def main():
    parser = argparse.ArgumentParser(description="Run golden dataset benchmark")
    parser.add_argument("--manifest", default=str(settings.golden_dataset_dir / "manifest.json"),
                        help="Path to manifest.json")
    parser.add_argument("--output", default=None, help="Output JSON path (default: data/benchmarks/<id>.json)")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    print(f"Loading manifest from {manifest_path}")
    manifest = load_manifest(manifest_path)

    print(f"Running benchmark on {len(manifest.entries)} entries...")
    result = run_benchmark(manifest)

    print(f"\n{'='*60}")
    print(f"Benchmark ID: {result.benchmark_id}")
    print(f"Gate Status:  {result.gate_status.value.upper()}")
    print(f"Processed:    {result.processed_entries}/{result.total_entries}")
    print(f"Skipped:      {result.skipped_entries}")

    if result.error_message:
        print(f"Error:        {result.error_message}")

    if result.metrics:
        print(f"\nKPI Results:")
        for m in result.metrics:
            status_icon = "PASS" if m.status.value == "pass" else "FAIL"
            threshold_str = f" (threshold: {m.threshold}{m.unit})" if m.threshold > 0 else ""
            print(f"  [{status_icon}] {m.name}: {m.value}{m.unit}{threshold_str}")

    if result.entry_results:
        gating = [er for er in result.entry_results if er.baseline_status == "gating"]
        exploratory = [er for er in result.entry_results if er.baseline_status != "gating"]

        if gating:
            print(f"\nGating Entries ({len(gating)}):")
            for er in gating:
                errors_str = f" ERRORS: {er.errors}" if er.errors else ""
                print(f"  {er.entry_id}: facts={er.facts_extracted} findings={er.findings_produced} "
                      f"ingest={er.ingestion_time_ms:.0f}ms val={er.validation_time_ms:.0f}ms"
                      f" TP={er.true_positives} FP={er.false_positives} FN={er.false_negatives}{errors_str}")

        if exploratory:
            print(f"\nExploratory Entries ({len(exploratory)}) - not gate-blocking:")
            for er in exploratory:
                errors_str = f" ERRORS: {er.errors}" if er.errors else ""
                print(f"  {er.entry_id}: facts={er.facts_extracted} findings={er.findings_produced} "
                      f"ingest={er.ingestion_time_ms:.0f}ms val={er.validation_time_ms:.0f}ms"
                      f" TP={er.true_positives} FP={er.false_positives} FN={er.false_negatives}{errors_str}")

    if args.output:
        from src.app.storage.file_repo import _JSONEncoder
        Path(args.output).write_text(
            json.dumps(result.model_dump(), cls=_JSONEncoder, indent=2),
            encoding="utf-8",
        )
        print(f"\nResults saved to {args.output}")

    sys.exit(0 if result.gate_status.value == "pass" else 1)


if __name__ == "__main__":
    main()
