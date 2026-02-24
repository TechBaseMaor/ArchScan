import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { BarChart3, Play, RefreshCw, Database } from 'lucide-react';
import { listBenchmarks, runBenchmark, syncDataset, getDatasetStatus } from '../../shared/api/benchmarks';
import { useToast } from '../../shared/components/Toast';
import Spinner from '../../shared/components/Spinner';
import StatusBadge from '../../shared/components/StatusBadge';
import EmptyState from '../../shared/components/EmptyState';

export default function BenchmarksPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showError, showSuccess } = useToast();
  const [syncing, setSyncing] = useState(false);

  const { data: benchmarks, isLoading } = useQuery({
    queryKey: ['benchmarks'],
    queryFn: listBenchmarks,
  });

  const { data: datasetStatus } = useQuery({
    queryKey: ['dataset-status'],
    queryFn: getDatasetStatus,
  });

  const runMut = useMutation({
    mutationFn: runBenchmark,
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ['benchmarks'] });
      showSuccess('Benchmark completed');
      navigate(`/benchmarks/${run.benchmark_id}`);
    },
    onError: () => showError('Benchmark run failed'),
  });

  const handleSync = async () => {
    setSyncing(true);
    try {
      await syncDataset();
      queryClient.invalidateQueries({ queryKey: ['dataset-status'] });
      showSuccess('Dataset sync completed');
    } catch {
      showError('Dataset sync failed');
    } finally {
      setSyncing(false);
    }
  };

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}><Spinner size={32} /></div>;
  }

  return (
    <>
      <div className="page-header">
        <h1>Benchmarks</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-secondary" onClick={handleSync} disabled={syncing} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <RefreshCw size={14} className={syncing ? 'spinning' : ''} /> Sync Dataset
          </button>
          <button className="btn-primary" onClick={() => runMut.mutate()} disabled={runMut.isPending}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            {runMut.isPending ? <Spinner size={14} /> : <Play size={14} />} Run Benchmark
          </button>
        </div>
      </div>

      {/* Dataset status */}
      {datasetStatus && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Database size={16} /> Golden Dataset Status
          </h3>
          <div style={{ display: 'flex', gap: 24, fontSize: 13 }}>
            <div>
              <span style={{ color: 'var(--color-text-dim)' }}>Total entries: </span>
              <strong>{datasetStatus.total_entries ?? '-'}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-dim)' }}>Available: </span>
              <strong>{datasetStatus.available ?? '-'}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-dim)' }}>Missing: </span>
              <strong>{datasetStatus.missing ?? '-'}</strong>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-dim)' }}>Checksum OK: </span>
              <strong>{datasetStatus.checksum_ok ?? '-'}</strong>
            </div>
          </div>
        </div>
      )}

      {/* Benchmarks list */}
      {!benchmarks?.length ? (
        <EmptyState
          icon={<BarChart3 size={48} />}
          message="No benchmark runs yet. Run your first benchmark to see KPI results."
          action={
            <button className="btn-primary" onClick={() => runMut.mutate()} disabled={runMut.isPending}>
              Run Benchmark
            </button>
          }
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr><th>Benchmark</th><th>Gate</th><th>Entries</th><th>Metrics</th><th>Started</th><th>Duration</th></tr>
            </thead>
            <tbody>
              {benchmarks.map((b) => (
                <tr key={b.benchmark_id} style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/benchmarks/${b.benchmark_id}`)}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{b.benchmark_id.slice(0, 10)}</td>
                  <td><StatusBadge status={b.gate_status} /></td>
                  <td>{b.processed_entries} / {b.total_entries}</td>
                  <td>
                    {b.metrics.slice(0, 3).map((m) => (
                      <span key={m.name} className={`badge badge-${m.status}`} style={{ marginRight: 4, fontSize: 10 }}>
                        {m.name}: {m.value.toFixed(3)}
                      </span>
                    ))}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{new Date(b.started_at).toLocaleString()}</td>
                  <td style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>
                    {b.completed_at
                      ? `${((new Date(b.completed_at).getTime() - new Date(b.started_at).getTime()) / 1000).toFixed(1)}s`
                      : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
