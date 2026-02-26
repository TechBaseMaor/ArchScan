import api from './client';
import type {
  AiAgentStatus,
  AiEnrichmentRequest,
  AiProposal,
  AiProposalDecision,
  LearnedMapping,
  LearningEvent,
} from './types';

export async function getAiStatus(): Promise<AiAgentStatus> {
  const { data } = await api.get<AiAgentStatus>('/ai/status');
  return data;
}

export async function runEnrichment(request: AiEnrichmentRequest): Promise<AiProposal[]> {
  const { data } = await api.post<AiProposal[]>('/ai/enrich', request);
  return data;
}

export async function listProposals(
  projectId: string,
  revisionId: string,
  status?: string,
): Promise<AiProposal[]> {
  const params = status ? `?status=${status}` : '';
  const { data } = await api.get<AiProposal[]>(
    `/ai/proposals/${projectId}/${revisionId}${params}`,
  );
  return data;
}

export async function decideProposal(
  projectId: string,
  revisionId: string,
  proposalId: string,
  decision: AiProposalDecision,
): Promise<AiProposal> {
  const { data } = await api.post<AiProposal>(
    `/ai/proposals/${projectId}/${revisionId}/${proposalId}/decide`,
    decision,
  );
  return data;
}

export async function listLearningEvents(
  eventType?: string,
  category?: string,
  limit = 100,
): Promise<LearningEvent[]> {
  const params = new URLSearchParams();
  if (eventType) params.set('event_type', eventType);
  if (category) params.set('category', category);
  params.set('limit', String(limit));
  const { data } = await api.get<LearningEvent[]>(`/ai/learning/events?${params}`);
  return data;
}

export async function listLearnedMappings(promotedOnly = false): Promise<LearnedMapping[]> {
  const params = promotedOnly ? '?promoted_only=true' : '';
  const { data } = await api.get<LearnedMapping[]>(`/ai/learning/mappings${params}`);
  return data;
}
