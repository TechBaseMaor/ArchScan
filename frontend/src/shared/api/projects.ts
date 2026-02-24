import api from './client';
import type { Project, Revision, ProjectHistoryEntry } from './types';

export async function listProjects(): Promise<Project[]> {
  const { data } = await api.get<Project[]>('/projects');
  return data;
}

export async function getProject(id: string): Promise<Project> {
  const { data } = await api.get<Project>(`/projects/${id}`);
  return data;
}

export async function createProject(name: string, description = ''): Promise<Project> {
  const { data } = await api.post<Project>('/projects', { name, description });
  return data;
}

export async function listRevisions(projectId: string): Promise<Revision[]> {
  const { data } = await api.get<Revision[]>(`/projects/${projectId}/revisions`);
  return data;
}

export async function createRevision(projectId: string, files: File[]): Promise<Revision> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const { data } = await api.post<Revision>(`/projects/${projectId}/revisions`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function getProjectHistory(projectId: string): Promise<ProjectHistoryEntry[]> {
  const { data } = await api.get<ProjectHistoryEntry[]>(`/projects/${projectId}/history`);
  return data;
}
