"""CLI script to sync the golden dataset from manifest sources."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app.config import settings
from src.app.dataset.source_registry import load_manifest, validate_manifest
from src.app.dataset.fetcher import sync_dataset
from src.app.dataset.validator import validate_dataset


def main():
    parser = argparse.ArgumentParser(description="Sync golden dataset from manifest")
    parser.add_argument("--manifest", default=str(settings.golden_dataset_dir / "manifest.json"),
                        help="Path to manifest.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded")
    parser.add_argument("--force", action="store_true", help="Re-download all entries")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing dataset")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    print(f"Loading manifest from {manifest_path}")
    manifest = load_manifest(manifest_path)

    schema_errors = validate_manifest(manifest)
    if schema_errors:
        print(f"Manifest warnings ({len(schema_errors)}):")
        for err in schema_errors:
            print(f"  - {err}")

    if args.validate_only:
        result = validate_dataset(manifest)
        print(f"\nDataset Status:")
        print(json.dumps(result.to_dict(), indent=2))
        sys.exit(0 if result.is_complete else 1)

    print(f"\nSyncing {len(manifest.entries)} entries (dry_run={args.dry_run}, force={args.force})")
    records = sync_dataset(manifest, dry_run=args.dry_run, force=args.force)

    for rec in records:
        status_icon = {
            "downloaded": "+",
            "pending": "?",
            "manual_required": "!",
            "checksum_mismatch": "X",
            "failed": "E",
        }.get(rec.status.value, "?")
        print(f"  [{status_icon}] {rec.entry_id}: {rec.status.value}")
        if rec.error_message:
            print(f"      Error: {rec.error_message}")

    downloaded = sum(1 for r in records if r.status.value == "downloaded")
    manual = sum(1 for r in records if r.status.value == "manual_required")
    failed = sum(1 for r in records if r.status.value in ("failed", "checksum_mismatch"))
    print(f"\nSummary: {downloaded} downloaded, {manual} manual required, {failed} failed/mismatch")


if __name__ == "__main__":
    main()
