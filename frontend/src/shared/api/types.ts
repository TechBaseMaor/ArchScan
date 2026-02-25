export interface Project {
  project_id: string;
  tenant_id: string;
  name: string;
  description: string;
  created_at: string;
}

export interface SourceFile {
  file_name: string;
  source_format: 'ifc' | 'pdf' | 'dwg';
  source_hash: string;
  size_bytes: number;
  stored_path: string;
}

export interface Revision {
  revision_id: string;
  project_id: string;
  sources: SourceFile[];
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface ProjectHistoryEntry {
  revision_id: string;
  created_at: string;
  source_count: number;
  validation_count: number;
}

export type ValidationStatus = 'queued' | 'running' | 'done' | 'failed';
export type Severity = 'error' | 'warning' | 'info';

export interface ValidationRun {
  validation_id: string;
  project_id: string;
  revision_id: string;
  ruleset_id: string;
  status: ValidationStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  findings_count: number;
}

export interface ComputationTrace {
  formula: string;
  inputs: Record<string, unknown>;
  result: unknown;
  tolerance_applied: Record<string, number>;
}

export interface Finding {
  finding_id: string;
  validation_id: string;
  rule_ref: string;
  severity: Severity;
  message: string;
  input_facts: string[];
  computation_trace: ComputationTrace;
  project_id: string;
  revision_id: string;
  source_hashes: string[];
  created_at: string;
  section_ref: string;
  regulation_basis: string;
  expected_value: unknown | null;
  observed_value: unknown | null;
  deviation: number | null;
  explanation: string;
}

export interface RulePrecondition {
  fact_category: string;
  operator: string;
  value: unknown;
  value_max: unknown;
}

export interface RuleComputation {
  formula: string;
  parameters: Record<string, unknown>;
}

export interface EvidenceTemplate {
  description: string;
  required_fact_categories: string[];
}

export interface Rule {
  rule_id: string;
  version: string;
  jurisdiction: string;
  effective_from: string | null;
  effective_to: string | null;
  severity: Severity;
  description: string;
  preconditions: RulePrecondition[];
  computation: RuleComputation;
  evidence_template: EvidenceTemplate;
}

export interface RuleSet {
  ruleset_id: string;
  name: string;
  jurisdiction: string;
  version: string;
  effective_date: string;
  rules: Rule[];
  created_at: string;
}

// ── Extracted Facts & Revision Summary ────────────────────────────────────

export interface ExtractedFact {
  fact_id: string;
  revision_id: string;
  source_hash: string;
  fact_type: 'geometric' | 'textual';
  category: string;
  label: string;
  value: unknown;
  unit: string;
  geometry_wkt: string;
  confidence: number;
  extraction_method: string;
  raw_source_ref: string;
  metadata: Record<string, unknown>;
}

export type AgreementStatus = 'matched' | 'minor_deviation' | 'major_deviation' | 'single_source';

export interface SummaryMetric {
  label: string;
  value: unknown;
  unit: string;
  confidence: number;
  source: string;
  raw_source_ref: string;
  fact_ids: string[];
  metadata: Record<string, unknown>;
}

export interface ReconciliationEntry {
  category: string;
  label: string;
  ifc_value: unknown | null;
  pdf_value: unknown | null;
  chosen_value: unknown;
  unit: string;
  agreement: AgreementStatus;
  deviation_pct: number | null;
}

export interface RevisionSummary {
  project_id: string;
  revision_id: string;
  areas: SummaryMetric[];
  heights: SummaryMetric[];
  floors: SummaryMetric[];
  openings: SummaryMetric[];
  setbacks: SummaryMetric[];
  reconciliation: ReconciliationEntry[];
  total_facts: number;
  sources_used: string[];
}

// ── Compliance Report ─────────────────────────────────────────────────────

export interface ComplianceGroup {
  layer: string;
  discipline: string;
  findings: Finding[];
  pass_count: number;
  fail_count: number;
  warning_count: number;
}

export interface DocumentCoverage {
  file_name: string;
  document_role: string;
  document_type: string;
  facts_extracted: number;
  rules_evaluated: number;
  officiality_status: string;
  officiality_confidence: number;
  readability_grade: string;
  legal_status: string;
}

export interface MissingEvidence {
  category: string;
  expected_source: string;
  reason: string;
  severity: Severity;
  section_ref: string;
  regulation_section: string;
  manual_intervention_required: boolean;
}

export interface ExtractedMetricSummary {
  category: string;
  label: string;
  value: unknown | null;
  unit: string;
  source_file: string;
  source_role: string;
  confidence: number;
  is_missing: boolean;
  missing_reason: string;
}

export interface SectionComparison {
  section_id: string;
  section_title: string;
  category: string;
  regulation_source: string;
  regulation_section_ref: string;
  regulation_value: unknown | null;
  regulation_text: string;
  submission_source: string;
  submission_value: unknown | null;
  unit: string;
  status: string;
  deviation: number | null;
  explanation: string;
  legal_status: string;
  evidence_links: string[];
}

export type ReviewStatusType = 'pending_review' | 'approved' | 'rejected' | 'auto_approved';

export interface ReviewItem {
  review_id: string;
  project_id: string;
  revision_id: string;
  file_name: string;
  source_hash: string;
  review_type: string;
  reason: string;
  confidence: number;
  status: ReviewStatusType;
  reviewer: string;
  decision_notes: string;
  created_at: string;
  resolved_at: string | null;
  context: Record<string, unknown>;
}

export interface ReviewCounts {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
}

export interface ComplianceReport {
  validation_id: string;
  project_id: string;
  revision_id: string;
  groups: ComplianceGroup[];
  document_coverage: DocumentCoverage[];
  missing_documents: string[];
  missing_evidence: MissingEvidence[];
  extracted_metrics: ExtractedMetricSummary[];
  section_comparisons: SectionComparison[];
  total_findings: number;
  total_errors: number;
  total_warnings: number;
  total_info: number;
  has_pending_reviews: boolean;
}

// ── Demo / Sample Files ───────────────────────────────────────────────────

export interface SampleFileInfo {
  name: string;
  description: string;
  format: string;
  size_hint: string;
  download_url: string;
}

export type GateStatus = 'pass' | 'fail' | 'skip';

export interface MetricResult {
  name: string;
  value: number;
  threshold: number;
  status: GateStatus;
  unit: string;
  details: Record<string, unknown>;
}

export interface EntryResult {
  entry_id: string;
  category: string;
  source_format: string;
  baseline_status: string;
  ingestion_time_ms: number;
  validation_time_ms: number;
  facts_extracted: number;
  findings_produced: number;
  area_error_pct: number | null;
  height_error_m: number | null;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  errors: string[];
}

export interface BenchmarkRun {
  benchmark_id: string;
  started_at: string;
  completed_at: string | null;
  total_entries: number;
  processed_entries: number;
  skipped_entries: number;
  metrics: MetricResult[];
  entry_results: EntryResult[];
  gate_status: GateStatus;
  error_message: string | null;
}

export interface BenchmarkSummary {
  benchmark_id: string;
  started_at: string;
  completed_at: string | null;
  gate_status: GateStatus;
  total_entries: number;
  processed_entries: number;
  metrics: MetricResult[];
}
