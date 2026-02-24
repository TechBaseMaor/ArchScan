from __future__ import annotations

import uuid
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.utcnow()


# ── Enums ──────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class FactType(str, Enum):
    GEOMETRIC = "geometric"
    TEXTUAL = "textual"


class SourceFormat(str, Enum):
    IFC = "ifc"
    PDF = "pdf"
    DWG = "dwg"


# ── Core entities ──────────────────────────────────────────────────────────

class Tenant(BaseModel):
    tenant_id: str = Field(default_factory=_new_id)
    name: str
    created_at: datetime = Field(default_factory=_now)


class User(BaseModel):
    user_id: str = Field(default_factory=_new_id)
    tenant_id: str
    email: str
    role: UserRole = UserRole.VIEWER
    created_at: datetime = Field(default_factory=_now)


class Project(BaseModel):
    project_id: str = Field(default_factory=_new_id)
    tenant_id: str = "default"
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=_now)


class SourceFile(BaseModel):
    file_name: str
    source_format: SourceFormat
    source_hash: str
    size_bytes: int
    stored_path: str


class Revision(BaseModel):
    revision_id: str = Field(default_factory=_new_id)
    project_id: str
    sources: list[SourceFile] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Facts ──────────────────────────────────────────────────────────────────

class ExtractedFact(BaseModel):
    fact_id: str = Field(default_factory=_new_id)
    revision_id: str
    source_hash: str
    fact_type: FactType
    category: str          # e.g. "area", "height", "setback", "text_clause"
    label: str             # human-readable description
    value: Any             # numeric or string
    unit: str = ""
    geometry_wkt: str = "" # optional WKT for spatial reference
    confidence: float = 1.0
    extraction_method: str = "deterministic"
    raw_source_ref: str = ""


# ── Rules ──────────────────────────────────────────────────────────────────

class RulePrecondition(BaseModel):
    fact_category: str
    operator: str   # "exists", "gt", "lt", "eq", "gte", "lte", "between", "contains"
    value: Any = None
    value_max: Any = None


class RuleComputation(BaseModel):
    formula: str    # identifier for the computation, e.g. "area_check", "height_check"
    parameters: dict[str, Any] = Field(default_factory=dict)


class EvidenceTemplate(BaseModel):
    description: str
    required_fact_categories: list[str] = Field(default_factory=list)


class Rule(BaseModel):
    rule_id: str
    version: str
    jurisdiction: str = "IL"
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    severity: Severity = Severity.ERROR
    description: str = ""
    preconditions: list[RulePrecondition] = Field(default_factory=list)
    computation: RuleComputation
    evidence_template: EvidenceTemplate = Field(default_factory=lambda: EvidenceTemplate(description=""))


class RuleSet(BaseModel):
    ruleset_id: str = Field(default_factory=_new_id)
    name: str
    jurisdiction: str = "IL"
    version: str = "1.0.0"
    effective_date: date = Field(default_factory=lambda: date.today())
    rules: list[Rule] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


# ── Validation ─────────────────────────────────────────────────────────────

class ValidationRun(BaseModel):
    validation_id: str = Field(default_factory=_new_id)
    project_id: str
    revision_id: str
    ruleset_id: str
    status: ValidationStatus = ValidationStatus.QUEUED
    created_at: datetime = Field(default_factory=_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    findings_count: int = 0


class ComputationTrace(BaseModel):
    formula: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    tolerance_applied: dict[str, float] = Field(default_factory=dict)


class Finding(BaseModel):
    finding_id: str = Field(default_factory=_new_id)
    validation_id: str
    rule_ref: str                       # "ruleId:version"
    severity: Severity
    message: str
    input_facts: list[str]              # fact IDs used
    computation_trace: ComputationTrace
    project_id: str
    revision_id: str
    source_hashes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


# ── Audit ──────────────────────────────────────────────────────────────────

class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_now)
    actor: str = "system"
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)


# ── API request / response helpers ────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class StartValidationRequest(BaseModel):
    project_id: str
    revision_id: str
    ruleset_id: str


class ProjectHistoryEntry(BaseModel):
    revision_id: str
    created_at: datetime
    source_count: int
    validation_count: int
