import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  Ruler,
  Building2,
  DoorOpen,
  Layers,
  ShieldCheck,
  GitCompare,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useState } from 'react';
import { getRevisionSummary } from '../../shared/api/projects';
import { useI18n } from '../../shared/i18n';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';
import type { SummaryMetric, ReconciliationEntry, AgreementStatus } from '../../shared/api/types';

export default function RevisionInsightsPage() {
  const { projectId, revisionId } = useParams<{ projectId: string; revisionId: string }>();
  const { t, formatNumber } = useI18n();

  const { data: summary, isLoading } = useQuery({
    queryKey: ['revisionSummary', projectId, revisionId],
    queryFn: () => getRevisionSummary(projectId!, revisionId!),
    enabled: !!projectId && !!revisionId,
  });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spinner size={32} />
      </div>
    );
  }

  if (!summary) {
    return <EmptyState icon={<Building2 size={48} />} message={t('insights.notFound')} />;
  }

  const hasData =
    summary.areas.length > 0 ||
    summary.heights.length > 0 ||
    summary.floors.length > 0 ||
    summary.openings.length > 0 ||
    summary.setbacks.length > 0;

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link
          to={`/projects/${projectId}`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            color: 'var(--color-text-dim)',
          }}
        >
          <ArrowLeft size={14} /> {t('insights.backToProject')}
        </Link>
      </div>

      <div className="page-header">
        <div>
          <h1>{t('insights.title')}</h1>
          <p style={{ color: 'var(--color-text-dim)', fontSize: 14, marginTop: 4 }}>
            {t('insights.subtitle', { count: String(summary.total_facts), sources: String(summary.sources_used.length) })}
          </p>
        </div>
      </div>

      {!hasData ? (
        <EmptyState icon={<Building2 size={48} />} message={t('insights.noData')} />
      ) : (
        <div style={{ display: 'grid', gap: 20 }}>
          {summary.areas.length > 0 && (
            <MetricSection
              icon={<Ruler size={18} />}
              title={t('insights.areas')}
              metrics={summary.areas}
              formatNumber={formatNumber}
              t={t}
            />
          )}

          {summary.heights.length > 0 && (
            <MetricSection
              icon={<Building2 size={18} />}
              title={t('insights.heights')}
              metrics={summary.heights}
              formatNumber={formatNumber}
              t={t}
            />
          )}

          {summary.floors.length > 0 && (
            <MetricSection
              icon={<Layers size={18} />}
              title={t('insights.floors')}
              metrics={summary.floors}
              formatNumber={formatNumber}
              t={t}
            />
          )}

          {summary.openings.length > 0 && (
            <MetricSection
              icon={<DoorOpen size={18} />}
              title={t('insights.openings')}
              metrics={summary.openings}
              formatNumber={formatNumber}
              t={t}
            />
          )}

          {summary.setbacks.length > 0 && (
            <MetricSection
              icon={<ShieldCheck size={18} />}
              title={t('insights.setbacks')}
              metrics={summary.setbacks}
              formatNumber={formatNumber}
              t={t}
            />
          )}

          {summary.reconciliation.length > 0 && (
            <ReconciliationSection
              entries={summary.reconciliation}
              title={t('insights.reconciliation')}
              formatNumber={formatNumber}
              t={t}
            />
          )}
        </div>
      )}
    </>
  );
}

function MetricSection({
  icon,
  title,
  metrics,
  formatNumber,
  t,
}: {
  icon: React.ReactNode;
  title: string;
  metrics: SummaryMetric[];
  formatNumber: (n: number) => string;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="card">
      <h3
        style={{
          fontSize: 15,
          fontWeight: 600,
          marginBottom: expanded ? 16 : 0,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        {icon} {title} ({metrics.length})
        <span style={{ marginInlineStart: 'auto' }}>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </span>
      </h3>
      {expanded && (
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>{t('insights.label')}</th>
                <th>{t('insights.value')}</th>
                <th>{t('insights.unit')}</th>
                <th>{t('insights.source')}</th>
                <th>{t('insights.confidence')}</th>
                <th>{t('insights.reference')}</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m, idx) => (
                <tr key={idx}>
                  <td>{m.label}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {typeof m.value === 'number' ? formatNumber(m.value) : String(m.value)}
                  </td>
                  <td style={{ color: 'var(--color-text-dim)', fontSize: 12 }}>{m.unit}</td>
                  <td>
                    <span className={`badge badge-${m.source === 'ifc' ? 'info' : 'warning'}`}>
                      {m.source.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <ConfidenceBar value={m.confidence} />
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {m.raw_source_ref}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 90 ? 'var(--color-success)' : pct >= 70 ? 'var(--color-warning)' : 'var(--color-error)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div
        style={{
          width: 48,
          height: 6,
          borderRadius: 3,
          background: 'var(--color-surface-2)',
          overflow: 'hidden',
        }}
      >
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 3, background: color }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--color-text-dim)' }}>
        {pct}%
      </span>
    </div>
  );
}

const AGREEMENT_COLORS: Record<AgreementStatus, { bg: string; text: string }> = {
  matched: { bg: 'var(--color-success)', text: '#fff' },
  minor_deviation: { bg: 'var(--color-warning)', text: '#000' },
  major_deviation: { bg: 'var(--color-error)', text: '#fff' },
  single_source: { bg: 'var(--color-info)', text: '#fff' },
};

const AGREEMENT_KEYS: Record<AgreementStatus, string> = {
  matched: 'insights.agreement.matched',
  minor_deviation: 'insights.agreement.minorDeviation',
  major_deviation: 'insights.agreement.majorDeviation',
  single_source: 'insights.agreement.singleSource',
};

function ReconciliationSection({
  entries,
  title,
  formatNumber,
  t,
}: {
  entries: ReconciliationEntry[];
  title: string;
  formatNumber: (n: number) => string;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  return (
    <div className="card">
      <h3
        style={{
          fontSize: 15,
          fontWeight: 600,
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <GitCompare size={18} /> {title}
      </h3>
      <div className="table-responsive">
        <table>
          <thead>
            <tr>
              <th>{t('insights.reconciliation.category')}</th>
              <th>{t('insights.reconciliation.ifcValue')}</th>
              <th>{t('insights.reconciliation.pdfValue')}</th>
              <th>{t('insights.reconciliation.chosen')}</th>
              <th>{t('insights.unit')}</th>
              <th>{t('insights.reconciliation.agreement')}</th>
              <th>{t('insights.reconciliation.deviation')}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, idx) => {
              const colors = AGREEMENT_COLORS[e.agreement];
              return (
                <tr key={idx}>
                  <td style={{ fontWeight: 500 }}>{e.category}</td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>
                    {e.ifc_value != null ? (typeof e.ifc_value === 'number' ? formatNumber(e.ifc_value) : String(e.ifc_value)) : '\u2014'}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>
                    {e.pdf_value != null ? (typeof e.pdf_value === 'number' ? formatNumber(e.pdf_value) : String(e.pdf_value)) : '\u2014'}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {typeof e.chosen_value === 'number' ? formatNumber(e.chosen_value) : String(e.chosen_value ?? '')}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{e.unit}</td>
                  <td>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                        background: colors.bg,
                        color: colors.text,
                      }}
                    >
                      {t(AGREEMENT_KEYS[e.agreement])}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-text-dim)' }}>
                    {e.deviation_pct != null ? `${e.deviation_pct}%` : '\u2014'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
