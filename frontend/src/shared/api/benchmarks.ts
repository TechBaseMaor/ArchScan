import api from './client';
import type { BenchmarkRun, BenchmarkSummary } from './types';

export async function runBenchmark(): Promise<BenchmarkRun> {
  const { data } = await api.post<BenchmarkRun>('/benchmarks/run');
  return data;
}

export async function listBenchmarks(): Promise<BenchmarkSummary[]> {
  const { data } = await api.get<BenchmarkSummary[]>('/benchmarks');
  return data;
}

export async function getBenchmark(id: string): Promise<BenchmarkRun> {
  const { data } = await api.get<BenchmarkRun>(`/benchmarks/${id}`);
  return data;
}

export async function syncDataset(dryRun = false, force = false) {
  const { data } = await api.post('/benchmarks/dataset/sync', null, {
    params: { dry_run: dryRun, force },
  });
  return data;
}

export async function getDatasetStatus() {
  const { data } = await api.get('/benchmarks/dataset/status');
  return data;
}
