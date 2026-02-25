import api, { resolveBaseURL } from './client';
import type { ValidationRun, Finding, ComplianceReport, ReviewItem, ReviewCounts } from './types';

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

export async function listReviewItems(
  projectId?: string,
  status?: string,
): Promise<ReviewItem[]> {
  const params = new URLSearchParams();
  if (projectId) params.set('project_id', projectId);
  if (status) params.set('status', status);
  const query = params.toString();
  const { data } = await api.get<ReviewItem[]>(`/reviews${query ? `?${query}` : ''}`);
  return data;
}

export async function getReviewItem(reviewId: string): Promise<ReviewItem> {
  const { data } = await api.get<ReviewItem>(`/reviews/${reviewId}`);
  return data;
}

export async function decideReview(
  reviewId: string,
  decision: 'approved' | 'rejected',
  reviewer: string = '',
  notes: string = '',
): Promise<ReviewItem> {
  const { data } = await api.post<ReviewItem>(`/reviews/${reviewId}/decide`, {
    decision,
    reviewer,
    notes,
  });
  return data;
}

export async function getReviewCounts(projectId?: string): Promise<ReviewCounts> {
  const params = projectId ? `?project_id=${projectId}` : '';
  const { data } = await api.get<ReviewCounts>(`/reviews/summary/counts${params}`);
  return data;
}