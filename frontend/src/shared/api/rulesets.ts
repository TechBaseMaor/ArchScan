import api from './client';
import type { RuleSet } from './types';

export async function listRulesets(): Promise<RuleSet[]> {
  const { data } = await api.get<RuleSet[]>('/rulesets');
  return data;
}

export async function getRuleset(id: string, version?: string): Promise<RuleSet> {
  const params = version ? { version } : {};
  const { data } = await api.get<RuleSet>(`/rulesets/${id}`, { params });
  return data;
}

export async function createRuleset(ruleset: RuleSet): Promise<RuleSet> {
  const { data } = await api.post<RuleSet>('/rulesets', ruleset);
  return data;
}
