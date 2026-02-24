"""Postgres-backed repository (Phase 1) — JSONB storage with key columns for lookup."""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

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

# Filesystem helpers re-exported so callers can use the same interface.
from src.app.storage.file_repo import (  # noqa: F401
    compute_file_hash,
    get_source_file_path,
    report_path,
    store_source_file,
)

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
        logger.info("Postgres connection pool created (min=1, max=10)")
    return _pool


def _dump(model) -> Jsonb:
    """Serialize a Pydantic model to a psycopg Jsonb wrapper."""
    return Jsonb(model.model_dump(mode="json"))


@contextmanager
def _conn():
    """Yield a connection from the pool (returned automatically on exit)."""
    with _get_pool().connection() as conn:
        yield conn


# ── Schema bootstrap ──────────────────────────────────────────────────────

SCHEMA_DDL = """\
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS revisions (
    revision_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS validations (
    validation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    validation_id TEXT PRIMARY KEY,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS rulesets (
    ruleset_id TEXT NOT NULL,
    version TEXT NOT NULL,
    data JSONB NOT NULL,
    PRIMARY KEY (ruleset_id, version)
);

CREATE TABLE IF NOT EXISTS facts (
    fact_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    created_date DATE NOT NULL DEFAULT CURRENT_DATE,
    data JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_revisions_project_id ON revisions (project_id);
CREATE INDEX IF NOT EXISTS idx_validations_project_id ON validations (project_id);
CREATE INDEX IF NOT EXISTS idx_facts_project_revision ON facts (project_id, revision_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_date ON audit_events (created_date);
"""


def bootstrap_schema() -> None:
    with _conn() as conn:
        conn.execute(SCHEMA_DDL)
        conn.commit()
    logger.info("Postgres schema bootstrapped")


# ── Projects ───────────────────────────────────────────────────────────────

def save_project(project: Project) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO projects (project_id, data) VALUES (%s, %s) "
            "ON CONFLICT (project_id) DO UPDATE SET data = EXCLUDED.data",
            (project.project_id, _dump(project)),
        )
        conn.commit()
    _log_audit("create", "project", project.project_id)


def get_project(project_id: str) -> Project | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT data FROM projects WHERE project_id = %s", (project_id,)
        ).fetchone()
    if not row:
        return None
    return Project.model_validate(row["data"])


def list_projects() -> list[Project]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT data FROM projects ORDER BY project_id"
        ).fetchall()
    return [Project.model_validate(r["data"]) for r in rows]


# ── Revisions (append-only) ───────────────────────────────────────────────

def save_revision(revision: Revision) -> None:
    with _conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM revisions WHERE revision_id = %s",
            (revision.revision_id,),
        ).fetchone()
        if exists:
            raise ValueError(
                f"Revision {revision.revision_id} already exists; overwrite is forbidden."
            )
        conn.execute(
            "INSERT INTO revisions (revision_id, project_id, data) VALUES (%s, %s, %s)",
            (revision.revision_id, revision.project_id, _dump(revision)),
        )
        conn.commit()
    _log_audit("create", "revision", revision.revision_id, {"project_id": revision.project_id})


def get_revision(project_id: str, revision_id: str) -> Revision | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT data FROM revisions WHERE revision_id = %s AND project_id = %s",
            (revision_id, project_id),
        ).fetchone()
    if not row:
        return None
    return Revision.model_validate(row["data"])


def list_revisions(project_id: str) -> list[Revision]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT data FROM revisions WHERE project_id = %s ORDER BY revision_id",
            (project_id,),
        ).fetchall()
    return [Revision.model_validate(r["data"]) for r in rows]


# ── Extracted facts ────────────────────────────────────────────────────────

def save_facts(project_id: str, revision_id: str, facts: list[ExtractedFact]) -> None:
    if not facts:
        return
    with _conn() as conn:
        for f in facts:
            conn.execute(
                "INSERT INTO facts (fact_id, project_id, revision_id, data) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (fact_id) DO UPDATE SET data = EXCLUDED.data",
                (f.fact_id, project_id, revision_id, _dump(f)),
            )
        conn.commit()


def load_facts(project_id: str, revision_id: str) -> list[ExtractedFact]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT data FROM facts WHERE project_id = %s AND revision_id = %s ORDER BY fact_id",
            (project_id, revision_id),
        ).fetchall()
    return [ExtractedFact.model_validate(r["data"]) for r in rows]


# ── Validations ────────────────────────────────────────────────────────────

def save_validation(run: ValidationRun) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO validations (validation_id, project_id, data) VALUES (%s, %s, %s) "
            "ON CONFLICT (validation_id) DO UPDATE SET data = EXCLUDED.data",
            (run.validation_id, run.project_id, _dump(run)),
        )
        conn.commit()


def get_validation(validation_id: str) -> ValidationRun | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT data FROM validations WHERE validation_id = %s",
            (validation_id,),
        ).fetchone()
    if not row:
        return None
    return ValidationRun.model_validate(row["data"])


def list_validations_for_project(project_id: str) -> list[ValidationRun]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT data FROM validations WHERE project_id = %s ORDER BY validation_id",
            (project_id,),
        ).fetchall()
    return [ValidationRun.model_validate(r["data"]) for r in rows]


# ── Findings ───────────────────────────────────────────────────────────────

def save_findings(validation_id: str, findings: list[Finding]) -> None:
    payload = [f.model_dump(mode="json") for f in findings]
    with _conn() as conn:
        conn.execute(
            "INSERT INTO findings (validation_id, data) VALUES (%s, %s) "
            "ON CONFLICT (validation_id) DO UPDATE SET data = EXCLUDED.data",
            (validation_id, Jsonb(payload)),
        )
        conn.commit()


def load_findings(validation_id: str) -> list[Finding]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT data FROM findings WHERE validation_id = %s",
            (validation_id,),
        ).fetchone()
    if not row:
        return []
    raw = row["data"]
    if isinstance(raw, str):
        raw = json.loads(raw)
    return [Finding.model_validate(item) for item in raw]


# ── RuleSets ───────────────────────────────────────────────────────────────

def save_ruleset(ruleset: RuleSet) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO rulesets (ruleset_id, version, data) VALUES (%s, %s, %s) "
            "ON CONFLICT (ruleset_id, version) DO UPDATE SET data = EXCLUDED.data",
            (ruleset.ruleset_id, ruleset.version, _dump(ruleset)),
        )
        conn.commit()
    _log_audit("create", "ruleset", ruleset.ruleset_id, {"version": ruleset.version})


def get_ruleset(ruleset_id: str, version: str | None = None) -> RuleSet | None:
    with _conn() as conn:
        if version:
            row = conn.execute(
                "SELECT data FROM rulesets WHERE ruleset_id = %s AND version = %s",
                (ruleset_id, version),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT data FROM rulesets WHERE ruleset_id = %s ORDER BY version DESC LIMIT 1",
                (ruleset_id,),
            ).fetchone()
    if not row:
        return None
    return RuleSet.model_validate(row["data"])


def list_rulesets() -> list[RuleSet]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ON (ruleset_id) data "
            "FROM rulesets ORDER BY ruleset_id, version DESC"
        ).fetchall()
    return [RuleSet.model_validate(r["data"]) for r in rows]


# ── Audit trail ────────────────────────────────────────────────────────────

def _log_audit(
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    event = AuditEvent(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO audit_events (event_id, created_date, data) VALUES (%s, %s, %s)",
                (event.event_id, date.today(), _dump(event)),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)


def log_audit_event(
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    _log_audit(action, resource_type, resource_id, details)
