import api, { resolveBaseURL } from './client';
import type { ValidationRun, Finding, ComplianceReport } from './types';

export async function listValidations(): Promise<ValidationRun[]> {
  const { data } = await api.get<ValidationRun[]>('/validations');
  return data;
}

export async function startValidation(
  projectId: string,
  revisionId: string,
  rulesetId: string,
): Promise<ValidationRun> {
  const { data } = await api.post<ValidationRun>('/validations', {
    project_id: projectId,
    revision_id: revisionId,
    ruleset_id: rulesetId,
  });
  return data;
}

export async function getValidation(id: string): Promise<ValidationRun> {
  const { data } = await api.get<ValidationRun>(`/validations/${id}`);
  return data;
}

export async function getFindings(validationId: string): Promise<Finding[]> {
  const { data } = await api.get<Finding[]>(`/validations/${validationId}/findings`);
  return data;
}

export async function getComplianceReport(validationId: string): Promise<ComplianceReport> {
  const { data } = await api.get<ComplianceReport>(`/validations/${validationId}/compliance`);
  return data;
}

export function getReportUrl(validationId: string): string {
  const base = resolveBaseURL();
  return `${base}/validations/${validationId}/report`;
}