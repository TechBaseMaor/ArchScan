import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, BarChart3, CheckCircle2, XCircle, MinusCircle } from 'lucide-react';
import { getBenchmark } from '../../shared/api/benchmarks';
import { useI18n } from '../../shared/i18n';
import Spinner from '../../shared/components/Spinner';
import StatusBadge from '../../shared/components/StatusBadge';
import EmptyState from '../../shared/components/EmptyState';

export default function BenchmarkDetailPage() {
  const { benchmarkId } = useParams<{ benchmarkId: string }>();
  const { t, formatDateTime } = useI18n();

  const { data: run, isLoading } = useQuery({
    queryKey: ['benchmark', benchmarkId],
    queryFn: () => getBenchmark(benchmarkId!),
    enabled: !!benchmarkId,
  });

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}><Spinner size={32} /></div>;
  }

  if (!run) {
    return <EmptyState icon={<BarChart3 size={48} />} message={t('benchmarks.notFound')} />;
  }

  const gateIcon = run.gate_status === 'pass' ? <CheckCircle2 size={24} color="var(--color-success)" />
    : run.gate_status === 'fail' ? <XCircle size={24} color="var(--color-error)" />
    : <MinusCircle size={24} color="var(--color-text-dim)" />;

  const gatingEntries = run.entry_results.filter((e) => e.baseline_status === 'gating');
  const exploratoryEntries = run.entry_results.filter((e) => e.baseline_status !== 'gating');

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link to="/advanced/benchmarks" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--color-text-dim)' }}>
          <ArrowLeft size={14} /> {t('benchmarks.backToBenchmarks')}
        </Link>
      </div>

      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {gateIcon}
          <div>
            <h1 style={{ textTransform: 'uppercase' }}>{run.gate_status}</h1>
            <div style={{ fontSize: 13, color: 'var(--color-text-dim)', marginTop: 2 }}>
              {run.benchmark_id} &middot; {formatDateTime(run.started_at)}
            </div>
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: '1 1 120px', textAlign: 'center' }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{run.processed_entries}</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('benchmarks.processed')}</div>
        </div>
        <div className="card" style={{ flex: '1 1 120px', textAlign: 'center' }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{run.total_entries}</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('benchmarks.total')}</div>
        </div>
        <div className="card" style={{ flex: '1 1 120px', textAlign: 'center' }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{run.skipped_entries}</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('benchmarks.skipped')}</div>
        </div>
        <div className="card" style={{ flex: '1 1 120px', textAlign: 'center' }}>
          <div style={{ fontSize: 28, fontWeight: 700 }}>
            {run.completed_at ? `${((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1)}s` : '-'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('benchmarks.duration')}</div>
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>{t('benchmarks.kpiMetrics')}</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
          {run.metrics.map((m) => (
            <div key={m.name} style={{
              padding: 16, borderRadius: 'var(--radius)',
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{m.name}</span>
                <StatusBadge status={m.status} />
              </div>
              <div style={{ fontSize: 24, fontWeight: 700 }}>
                {m.value.toFixed(4)}{m.unit && <span style={{ fontSize: 14, color: 'var(--color-text-dim)' }}> {m.unit}</span>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 4 }}>
                {t('benchmarks.threshold')}: {m.threshold.toFixed(4)}{m.unit && ` ${m.unit}`}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Gating entries */}
      {gatingEntries.length > 0 && (
        <div className="card" style={{ marginBottom: 24, padding: 0 }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--color-border)' }}>
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>{t('benchmarks.gatingEntries')} ({gatingEntries.length})</h3>
          </div>
          <div className="table-responsive">
            <table>
              <thead>
                <tr><th>{t('benchmarks.entry')}</th><th>{t('benchmarks.category')}</th><th>{t('benchmarks.format')}</th><th>{t('benchmarks.facts')}</th><th>{t('benchmarks.findingsCol')}</th><th>{t('benchmarks.tp')}</th><th>{t('benchmarks.fp')}</th><th>{t('benchmarks.fn')}</th><th>{t('findings.errors')}</th></tr>
              </thead>
              <tbody>
                {gatingEntries.map((e) => (
                  <tr key={e.entry_id}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{e.entry_id}</td>
                    <td>{e.category}</td>
                    <td><span className="badge badge-info">{e.source_format}</span></td>
                    <td>{e.facts_extracted}</td>
                    <td>{e.findings_produced}</td>
                    <td style={{ color: 'var(--color-success)' }}>{e.true_positives}</td>
                    <td style={{ color: 'var(--color-error)' }}>{e.false_positives}</td>
                    <td style={{ color: 'var(--color-warning)' }}>{e.false_negatives}</td>
                    <td>{e.errors.length > 0 ? <span className="badge badge-error">{e.errors.length}</span> : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Exploratory entries */}
      {exploratoryEntries.length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--color-border)' }}>
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>{t('benchmarks.exploratoryEntries')} ({exploratoryEntries.length})</h3>
          </div>
          <div className="table-responsive">
            <table>
              <thead>
                <tr><th>{t('benchmarks.entry')}</th><th>{t('benchmarks.category')}</th><th>{t('benchmarks.format')}</th><th>{t('benchmarks.facts')}</th><th>{t('benchmarks.findingsCol')}</th><th>{t('findings.errors')}</th></tr>
              </thead>
              <tbody>
                {exploratoryEntries.map((e) => (
                  <tr key={e.entry_id}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{e.entry_id}</td>
                    <td>{e.category}</td>
                    <td><span className="badge badge-info">{e.source_format}</span></td>
                    <td>{e.facts_extracted}</td>
                    <td>{e.findings_produced}</td>
                    <td>{e.errors.length > 0 ? <span className="badge badge-error">{e.errors.length}</span> : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
