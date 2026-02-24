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
