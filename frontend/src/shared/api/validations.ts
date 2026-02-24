import api from './client';
import type { ValidationRun, Finding } from './types';

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

export function getReportUrl(validationId: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${base}/validations/${validationId}/report`;
}
