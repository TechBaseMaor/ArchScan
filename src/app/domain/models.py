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


class DocumentRole(str, Enum):
    REGULATION = "regulation"
    SUBMISSION = "submission"
    SUPPORTING = "supporting"
    UNKNOWN = "unknown"


class OfficialityStatus(str, Enum):
    PENDING = "pending"
    VERIFIED_OFFICIAL = "verified_official"
    LIKELY_OFFICIAL = "likely_official"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


class ReviewStatus(str, Enum):
    AUTO_APPROVED = "auto_approved"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReadabilityGrade(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNREADABLE = "unreadable"


class LegalStatus(str, Enum):
    SPATIAL_DIRECTIVE = "הנחיה מרחבית"
    POLICY = "מדיניות"
    STATUTORY = "statutory"
    UNKNOWN = "unknown"


class SourceFormat(str, Enum):
    IFC = "ifc"
    PDF = "pdf"
    DWG = "dwg"
    DWFX = "dwfx"


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
    document_role: DocumentRole = DocumentRole.UNKNOWN
    document_type: str = ""
    officiality_status: OfficialityStatus = OfficialityStatus.PENDING
    officiality_confidence: float = 0.0
    officiality_signals: Dict[str, Any] = Field(default_factory=dict)
    readability_grade: ReadabilityGrade = ReadabilityGrade.HIGH
    legal_status: LegalStatus = LegalStatus.UNKNOWN


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
    category: str          # e.g. "area", "height", "setback", "opening_window", "opening_door", "floor_summary"
    label: str             # human-readable description
    value: Any             # numeric or string
    unit: str = ""
    geometry_wkt: str = "" # optional WKT for spatial reference
    confidence: float = 1.0
    extraction_method: str = "deterministic"
    raw_source_ref: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Revision summary (client-facing) ──────────────────────────────────────

class AgreementStatus(str, Enum):
    MATCHED = "matched"
    MINOR_DEVIATION = "minor_deviation"
    MAJOR_DEVIATION = "major_deviation"
    SINGLE_SOURCE = "single_source"


class SummaryMetric(BaseModel):
    label: str
    value: Any
    unit: str = ""
    confidence: float = 1.0
    source: str = ""           # "ifc" | "pdf" | "reconciled"
    raw_source_ref: str = ""
    fact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReconciliationEntry(BaseModel):
    category: str
    label: str
    ifc_value: Optional[Any] = None
    pdf_value: Optional[Any] = None
    chosen_value: Any = None
    unit: str = ""
    agreement: AgreementStatus = AgreementStatus.SINGLE_SOURCE
    deviation_pct: Optional[float] = None


class RevisionSummary(BaseModel):
    project_id: str
    revision_id: str
    areas: list[SummaryMetric] = Field(default_factory=list)
    heights: list[SummaryMetric] = Field(default_factory=list)
    floors: list[SummaryMetric] = Field(default_factory=list)
    openings: list[SummaryMetric] = Field(default_factory=list)
    setbacks: list[SummaryMetric] = Field(default_factory=list)
    parking: list[SummaryMetric] = Field(default_factory=list)
    dwelling_units: list[SummaryMetric] = Field(default_factory=list)
    regulatory_thresholds: list[SummaryMetric] = Field(default_factory=list)
    reconciliation: list[ReconciliationEntry] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    total_facts: int = 0
    sources_used: list[str] = Field(default_factory=list)


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
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    section_ref: str = ""
    regulation_basis: str = ""
    expected_value: Optional[Any] = None
    observed_value: Optional[Any] = None
    deviation: Optional[float] = None
    explanation: str = ""


# ── Grouped Compliance Report ─────────────────────────────────────────────

class ComplianceGroup(BaseModel):
    """Findings grouped by rule layer and discipline."""
    layer: str = ""                           # statutory / municipal_policy / cross_document
    discipline: str = ""                      # parking / design / environment / waste / green / general
    findings: list[Finding] = Field(default_factory=list)
    pass_count: int = 0
    fail_count: int = 0
    warning_count: int = 0


class DocumentCoverage(BaseModel):
    """Tracks which source documents contributed facts for validation."""
    file_name: str
    document_role: str
    document_type: str
    facts_extracted: int = 0
    rules_evaluated: int = 0
    officiality_status: str = "pending"
    officiality_confidence: float = 0.0
    readability_grade: str = "high"
    legal_status: str = "unknown"


class MissingEvidence(BaseModel):
    """Explicit record of a parameter that could not be verified."""
    category: str
    expected_source: str
    reason: str
    severity: Severity = Severity.WARNING
    section_ref: str = ""
    regulation_section: str = ""
    manual_intervention_required: bool = False


class ExtractedMetricSummary(BaseModel):
    """Aggregated metric for the pilot compliance report."""
    category: str
    label: str
    value: Any = None
    unit: str = ""
    source_file: str = ""
    source_role: str = ""
    confidence: float = 1.0
    is_missing: bool = False
    missing_reason: str = ""


class SectionComparison(BaseModel):
    """Requirement-vs-submission comparison for a single section/parameter."""
    section_id: str = ""
    section_title: str = ""
    category: str = ""
    regulation_source: str = ""
    regulation_section_ref: str = ""
    regulation_value: Optional[Any] = None
    regulation_text: str = ""
    submission_source: str = ""
    submission_value: Optional[Any] = None
    unit: str = ""
    status: str = "pending"  # pass / fail / warn / missing / manual_review
    deviation: Optional[float] = None
    explanation: str = ""
    legal_status: str = "unknown"
    evidence_links: List[str] = Field(default_factory=list)


class ComplianceReport(BaseModel):
    """Bundle-level compliance report with grouped findings."""
    validation_id: str
    project_id: str
    revision_id: str
    groups: list[ComplianceGroup] = Field(default_factory=list)
    document_coverage: list[DocumentCoverage] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    missing_evidence: list[MissingEvidence] = Field(default_factory=list)
    extracted_metrics: list[ExtractedMetricSummary] = Field(default_factory=list)
    section_comparisons: list[SectionComparison] = Field(default_factory=list)
    total_findings: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    total_info: int = 0
    has_pending_reviews: bool = False


# ── Audit ──────────────────────────────────────────────────────────────────

class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_now)
    actor: str = "system"
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)


# ── Manual Review Queue ───────────────────────────────────────────────────

class ReviewItem(BaseModel):
    """A document or finding flagged for manual review."""
    review_id: str = Field(default_factory=_new_id)
    project_id: str
    revision_id: str
    file_name: str = ""
    source_hash: str = ""
    review_type: str = ""  # "officiality" | "contradiction" | "missing_data"
    reason: str = ""
    confidence: float = 0.0
    status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    reviewer: str = ""
    decision_notes: str = ""
    created_at: datetime = Field(default_factory=_now)
    resolved_at: Optional[datetime] = None
    context: Dict[str, Any] = Field(default_factory=dict)


# ── API request / response helpers ────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class StartValidationRequest(BaseModel):
    project_id: str
    revision_id: str
    ruleset_id: str


class ReviewDecisionRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    reviewer: str = "anonymous"
    notes: str = ""


class ProjectHistoryEntry(BaseModel):
    revision_id: str
    created_at: datetime
    source_count: int
    validation_count: int
