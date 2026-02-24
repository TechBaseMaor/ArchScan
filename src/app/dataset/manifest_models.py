"""Golden dataset manifest schema and source governance models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DownloadPolicy(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


class BaselineStatus(str, Enum):
    GATING = "gating"
    EXPLORATORY = "exploratory"


class DatasetCategory(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    DIRTY = "dirty"
    REGULATORY_TEXT = "regulatory_text"


class SourceFormat(str, Enum):
    IFC = "ifc"
    PDF = "pdf"
    DWG = "dwg"


class GroundTruth(BaseModel):
    """Expected geometric measurements for KPI evaluation."""
    gross_area: Optional[float] = None
    net_area: Optional[float] = None
    max_height: Optional[float] = None
    min_height: Optional[float] = None
    min_setback: Optional[float] = None
    level_count: Optional[int] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ExpectedFinding(BaseModel):
    """Expected compliance finding for precision/recall evaluation."""
    rule_id: str
    rule_version: str
    severity: str
    expected: bool = True
    description: str = ""


class DatasetEntry(BaseModel):
    """A single test artifact in the golden dataset."""
    entry_id: str
    name: str
    category: DatasetCategory
    source_format: SourceFormat
    source_url: str
    download_policy: DownloadPolicy
    license_note: str = ""
    expected_checksum: Optional[str] = None
    ifc_version: Optional[str] = None
    file_size_hint: Optional[str] = None
    ground_truth: Optional[GroundTruth] = None
    expected_findings: list[ExpectedFinding] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    baseline_status: BaselineStatus = BaselineStatus.EXPLORATORY


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"


class ProvenanceRecord(BaseModel):
    """Tracks download provenance for a dataset entry."""
    entry_id: str
    status: DownloadStatus
    local_path: Optional[str] = None
    actual_checksum: Optional[str] = None
    downloaded_at: Optional[datetime] = None
    error_message: Optional[str] = None
    file_size_bytes: Optional[int] = None


class DatasetManifest(BaseModel):
    """Top-level golden dataset manifest."""
    version: str = "1.0.0"
    description: str = "ArchScan Golden Dataset"
    entries: list[DatasetEntry] = Field(default_factory=list)
    ruleset_id: str = "israel_residential_v1"
    ruleset_version: str = "1.0.0"
    created_at: Optional[datetime] = None
