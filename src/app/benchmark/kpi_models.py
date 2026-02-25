"""KPI models for benchmark evaluation."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class MetricResult(BaseModel):
    name: str
    value: float
    threshold: float
    status: GateStatus
    unit: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class EntryResult(BaseModel):
    entry_id: str
    category: str
    source_format: str
    baseline_status: str = "exploratory"
    ingestion_time_ms: float = 0.0
    validation_time_ms: float = 0.0
    facts_extracted: int = 0
    findings_produced: int = 0
    area_error_pct: Optional[float] = None
    height_error_m: Optional[float] = None
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    errors: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRun(BaseModel):
    benchmark_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_entries: int = 0
    processed_entries: int = 0
    skipped_entries: int = 0
    metrics: list[MetricResult] = Field(default_factory=list)
    entry_results: list[EntryResult] = Field(default_factory=list)
    gate_status: GateStatus = GateStatus.SKIP
    error_message: Optional[str] = None


class BenchmarkSummary(BaseModel):
    benchmark_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    gate_status: GateStatus
    total_entries: int
    processed_entries: int
    metrics: list[MetricResult] = Field(default_factory=list)
