from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import TypeVar, Type

from pydantic import BaseModel

from src.app.config import settings
from src.app.domain.models import (
    AuditEvent,
    ExtractedFact,
    Finding,
    Project,
    Revision,
    RuleSet,
    ValidationRun,
)

T = TypeVar("T", bound=BaseModel)


class _JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, cls=_JSONEncoder, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_model(path: Path, model_cls: Type[T]) -> T:
    return model_cls.model_validate(_read_json(path))


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()[:16]


# ── Projects ───────────────────────────────────────────────────────────────

def _project_dir(project_id: str) -> Path:
    return settings.data_dir / "projects" / project_id


def save_project(project: Project) -> None:
    _write_json(_project_dir(project.project_id) / "project.json", project.model_dump())
    _log_audit("create", "project", project.project_id)


def get_project(project_id: str) -> Project | None:
    p = _project_dir(project_id) / "project.json"
    return _load_model(p, Project) if p.exists() else None


def list_projects() -> list[Project]:
    base = settings.data_dir / "projects"
    if not base.exists():
        return []
    projects = []
    for d in sorted(base.iterdir()):
        pf = d / "project.json"
        if pf.exists():
            projects.append(_load_model(pf, Project))
    return projects


# ── Revisions (append-only) ───────────────────────────────────────────────

def _revisions_dir(project_id: str) -> Path:
    return _project_dir(project_id) / "revisions"


def save_revision(revision: Revision) -> None:
    path = _revisions_dir(revision.project_id) / f"{revision.revision_id}.json"
    if path.exists():
        raise ValueError(f"Revision {revision.revision_id} already exists; overwrite is forbidden.")
    _write_json(path, revision.model_dump())
    _log_audit("create", "revision", revision.revision_id, {"project_id": revision.project_id})


def get_revision(project_id: str, revision_id: str) -> Revision | None:
    p = _revisions_dir(project_id) / f"{revision_id}.json"
    return _load_model(p, Revision) if p.exists() else None


def list_revisions(project_id: str) -> list[Revision]:
    d = _revisions_dir(project_id)
    if not d.exists():
        return []
    return [_load_model(f, Revision) for f in sorted(d.glob("*.json"))]


# ── Source files ───────────────────────────────────────────────────────────

def _sources_dir(project_id: str) -> Path:
    return _project_dir(project_id) / "sources"


def store_source_file(project_id: str, file_name: str, file_bytes: bytes) -> tuple[str, str]:
    """Returns (source_hash, stored_path)."""
    source_hash = compute_file_hash(file_bytes)
    dest = _sources_dir(project_id) / f"{source_hash}_{file_name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(file_bytes)
    return source_hash, str(dest)


def get_source_file_path(project_id: str, source_hash: str, file_name: str) -> Path | None:
    p = _sources_dir(project_id) / f"{source_hash}_{file_name}"
    return p if p.exists() else None


# ── Extracted facts ────────────────────────────────────────────────────────

def _facts_dir(project_id: str, revision_id: str) -> Path:
    return _project_dir(project_id) / "revisions" / f"{revision_id}_facts"


def save_facts(project_id: str, revision_id: str, facts: list[ExtractedFact]) -> None:
    d = _facts_dir(project_id, revision_id)
    d.mkdir(parents=True, exist_ok=True)
    for f in facts:
        _write_json(d / f"{f.fact_id}.json", f.model_dump())


def load_facts(project_id: str, revision_id: str) -> list[ExtractedFact]:
    d = _facts_dir(project_id, revision_id)
    if not d.exists():
        return []
    return [_load_model(fp, ExtractedFact) for fp in sorted(d.glob("*.json"))]


# ── Validations ────────────────────────────────────────────────────────────

def _validation_path(validation_id: str) -> Path:
    return settings.data_dir / "validations" / f"{validation_id}.json"


def save_validation(run: ValidationRun) -> None:
    _write_json(_validation_path(run.validation_id), run.model_dump())


def get_validation(validation_id: str) -> ValidationRun | None:
    p = _validation_path(validation_id)
    return _load_model(p, ValidationRun) if p.exists() else None


def list_validations_for_project(project_id: str) -> list[ValidationRun]:
    d = settings.data_dir / "validations"
    if not d.exists():
        return []
    results = []
    for f in sorted(d.glob("*.json")):
        v = _load_model(f, ValidationRun)
        if v.project_id == project_id:
            results.append(v)
    return results


def list_all_validations() -> list[ValidationRun]:
    d = settings.data_dir / "validations"
    if not d.exists():
        return []
    return [_load_model(f, ValidationRun) for f in sorted(d.glob("*.json"))]


# ── Findings ───────────────────────────────────────────────────────────────

def _findings_path(validation_id: str) -> Path:
    return settings.data_dir / "findings" / f"{validation_id}.json"


def save_findings(validation_id: str, findings: list[Finding]) -> None:
    _write_json(_findings_path(validation_id), [f.model_dump() for f in findings])


def load_findings(validation_id: str) -> list[Finding]:
    p = _findings_path(validation_id)
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    return [Finding.model_validate(item) for item in raw]


# ── Reports ────────────────────────────────────────────────────────────────

def report_path(validation_id: str) -> Path:
    return settings.data_dir / "reports" / f"{validation_id}.pdf"


# ── RuleSets ───────────────────────────────────────────────────────────────

def _ruleset_dir(ruleset_id: str) -> Path:
    return settings.rulesets_dir / ruleset_id


def save_ruleset(ruleset: RuleSet) -> None:
    _write_json(_ruleset_dir(ruleset.ruleset_id) / f"{ruleset.version}.json", ruleset.model_dump())
    _log_audit("create", "ruleset", ruleset.ruleset_id, {"version": ruleset.version})


def get_ruleset(ruleset_id: str, version: str | None = None) -> RuleSet | None:
    d = _ruleset_dir(ruleset_id)
    if not d.exists():
        return None
    if version:
        p = d / f"{version}.json"
        return _load_model(p, RuleSet) if p.exists() else None
    versions = sorted(d.glob("*.json"))
    if not versions:
        return None
    return _load_model(versions[-1], RuleSet)


def list_rulesets() -> list[RuleSet]:
    base = settings.rulesets_dir
    if not base.exists():
        return []
    results = []
    for d in sorted(base.iterdir()):
        if d.is_dir():
            versions = sorted(d.glob("*.json"))
            if versions:
                results.append(_load_model(versions[-1], RuleSet))
    return results


# ── Audit trail (append-only JSONL) ───────────────────────────────────────

def _log_audit(action: str, resource_type: str, resource_id: str, details: dict | None = None) -> None:
    event = AuditEvent(action=action, resource_type=resource_type, resource_id=resource_id, details=details or {})
    log_file = settings.data_dir / "audit" / f"{date.today().isoformat()}.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event.model_dump(), cls=_JSONEncoder, ensure_ascii=False) + "\n")


def log_audit_event(action: str, resource_type: str, resource_id: str, details: dict | None = None) -> None:
    _log_audit(action, resource_type, resource_id, details)
