import { useState, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  FileText,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Download,
  ChevronDown,
  ChevronUp,
  FileWarning,
  Ruler,
  Building2,
  ParkingCircle,
  Home,
  Search,
} from 'lucide-react';
import { listValidations, getComplianceReport } from '../../shared/api/validations';
import { useI18n } from '../../shared/i18n';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';
import StatusBadge from '../../shared/components/StatusBadge';
import AiProposalsPanel from '../ai/AiProposalsPanel';
import type {
  ComplianceReport,
  ComplianceGroup,
  DocumentCoverage,
  MissingEvidence,
  ExtractedMetricSummary,
  Finding,
  SectionComparison,
} from '../../shared/api/types';

const CATEGORY_ICONS: Record<string, typeof Ruler> = {
  area: Ruler,
  height: Building2,
  setback: Ruler,
  parking: ParkingCircle,
  dwelling_units: Home,
};

const CATEGORY_LABELS_HE: Record<string, string> = {
  area: 'שטחים',
  height: 'גבהים',
  setback: 'קווי בניין',
  parking: 'חניות',
  dwelling_units: 'יחידות דיור',
  sheet_info: 'מידע גליונות',
  sheet_dimensions: 'מידות גליונות',
  regulatory_threshold: 'ספי רגולציה',
  text_clause: 'סעיפי טקסט',
};

const LAYER_LABELS_HE: Record<string, string> = {
  statutory: 'חוקי (תב"ע)',
  municipal_policy: 'מדיניות עירונית',
  cross_document: 'השוואה בין מסמכים',
  general: 'כללי',
};

export default function PilotAlonReportPage() {
  const { validationId } = useParams<{ validationId: string }>();
  const { t } = useI18n();
  const navigate = useNavigate();

  if (!validationId) {
    return <ValidationPicker navigate={navigate} t={t} />;
  }

  return <ComplianceReportView validationId={validationId} t={t} />;
}

function ValidationPicker({
  navigate,
  t,
}: {
  navigate: ReturnType<typeof useNavigate>;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const { data: validations, isLoading } = useQuery({
    queryKey: ['allValidations'],
    queryFn: listValidations,
  });

  const doneValidations = useMemo(
    () => (validations ?? []).filter((v) => v.status === 'done'),
    [validations],
  );

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spinner size={32} />
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>{t('pilotAlon.title')}</h1>
          <p style={{ color: 'var(--color-text-dim)', fontSize: 14, marginTop: 4 }}>
            {t('pilotAlon.selectValidation')}
          </p>
        </div>
      </div>

      {doneValidations.length === 0 ? (
        <EmptyState
          icon={<FileText size={48} />}
          message={t('pilotAlon.noValidations')}
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>{t('pilotAlon.validationId')}</th>
                  <th>{t('pilotAlon.ruleset')}</th>
                  <th>{t('pilotAlon.findings')}</th>
                  <th>{t('pilotAlon.status')}</th>
                  <th>{t('pilotAlon.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {doneValidations.map((v) => (
                  <tr key={v.validation_id}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                      {v.validation_id}
                    </td>
                    <td>{v.ruleset_id}</td>
                    <td>{v.findings_count}</td>
                    <td><StatusBadge status={v.status} /></td>
                    <td>
                      <button
                        className="btn-primary btn-sm"
                        onClick={() => navigate(`/advanced/reports/pilot-alon/${v.validation_id}`)}
                      >
                        {t('pilotAlon.viewReport')}
                      </button>
                    </td>
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

function ComplianceReportView({
  validationId,
  t,
}: {
  validationId: string;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const { data: report, isLoading, error } = useQuery({
    queryKey: ['complianceReport', validationId],
    queryFn: () => getComplianceReport(validationId),
  });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spinner size={32} />
      </div>
    );
  }

  if (error || !report) {
    return <EmptyState icon={<AlertCircle size={48} />} message={t('pilotAlon.loadError')} />;
  }

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pilot_alon_report_${validationId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link
          to="/advanced/reports/pilot-alon"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            color: 'var(--color-text-dim)',
          }}
        >
          <ArrowLeft size={14} /> {t('pilotAlon.backToList')}
        </Link>
      </div>

      <div className="page-header">
        <div>
          <h1>{t('pilotAlon.reportTitle')}</h1>
          <p style={{ color: 'var(--color-text-dim)', fontSize: 14, marginTop: 4 }}>
            {t('pilotAlon.reportSubtitle', {
              findings: String(report.total_findings),
              errors: String(report.total_errors),
              warnings: String(report.total_warnings),
            })}
          </p>
        </div>
        <button
          className="btn-secondary"
          onClick={downloadJson}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <Download size={14} /> JSON
        </button>
      </div>

      {report.has_pending_reviews && (
        <div
          style={{
            background: 'var(--color-warning)15',
            border: '1px solid var(--color-warning)',
            borderRadius: 'var(--radius)',
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 16,
            fontSize: 13,
          }}
        >
          <AlertTriangle size={16} color="var(--color-warning)" />
          {t('pilotAlon.pendingReviewsBanner')}
        </div>
      )}

      {/* Summary counters */}
      <SummaryCards report={report} t={t} />

      <div style={{ display: 'grid', gap: 20, marginTop: 20 }}>
        {/* Section comparisons */}
        {report.section_comparisons && report.section_comparisons.length > 0 && (
          <SectionComparisonsTable comparisons={report.section_comparisons} t={t} />
        )}

        {/* Extracted metrics */}
        <MetricsSection metrics={report.extracted_metrics} t={t} />

        {/* Compliance groups */}
        {report.groups.length > 0 && (
          <ComplianceGroupsSection groups={report.groups} t={t} />
        )}

        {/* Document coverage */}
        {report.document_coverage.length > 0 && (
          <CoverageSection coverage={report.document_coverage} t={t} />
        )}

        {/* Missing evidence */}
        {(report.missing_evidence.length > 0 || report.missing_documents.length > 0) && (
          <MissingSection
            evidence={report.missing_evidence}
            documents={report.missing_documents}
            t={t}
          />
        )}
      </div>

      {/* AI Enrichment Panel */}
      <AiProposalsPanel
        projectId={report.project_id}
        revisionId={report.revision_id}
      />
    </>
  );
}

function SummaryCards({
  report,
  t,
}: {
  report: ComplianceReport;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const metricsCount = report.extracted_metrics.filter((m) => !m.is_missing).length;
  const missingCount = report.missing_evidence.length + report.missing_documents.length;

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      <SummaryCard
        icon={<CheckCircle2 size={20} color="var(--color-success)" />}
        value={metricsCount}
        label={t('pilotAlon.metricsExtracted')}
        color="var(--color-success)"
      />
      <SummaryCard
        icon={<AlertCircle size={20} color="var(--color-error)" />}
        value={report.total_errors}
        label={t('pilotAlon.errors')}
        color="var(--color-error)"
      />
      <SummaryCard
        icon={<AlertTriangle size={20} color="var(--color-warning)" />}
        value={report.total_warnings}
        label={t('pilotAlon.warnings')}
        color="var(--color-warning)"
      />
      <SummaryCard
        icon={<FileWarning size={20} color="var(--color-info)" />}
        value={missingCount}
        label={t('pilotAlon.missingItems')}
        color="var(--color-info)"
      />
    </div>
  );
}

function SummaryCard({
  icon,
  value,
  label,
  color,
}: {
  icon: React.ReactNode;
  value: number;
  label: string;
  color: string;
}) {
  return (
    <div
      className="card"
      style={{
        flex: '1 1 140px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: 16,
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: '50%',
          background: `${color}20`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{label}</div>
      </div>
    </div>
  );
}

function MetricsSection({
  metrics,
  t,
}: {
  metrics: ExtractedMetricSummary[];
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const [expanded, setExpanded] = useState(true);

  const grouped = useMemo(() => {
    const map: Record<string, ExtractedMetricSummary[]> = {};
    for (const m of metrics) {
      (map[m.category] ??= []).push(m);
    }
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
  }, [metrics]);

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
        <Ruler size={18} /> {t('pilotAlon.extractedMetrics')} ({metrics.length})
        <span style={{ marginInlineStart: 'auto' }}>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </span>
      </h3>
      {expanded && (
        <div style={{ display: 'grid', gap: 16 }}>
          {grouped.map(([category, catMetrics]) => {
            const Icon = CATEGORY_ICONS[category] || FileText;
            const catLabel = CATEGORY_LABELS_HE[category] || category;
            return (
              <div key={category}>
                <h4
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: 'var(--color-text-dim)',
                    marginBottom: 8,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <Icon size={14} /> {catLabel}
                </h4>
                <div className="table-responsive">
                  <table>
                    <thead>
                      <tr>
                        <th>{t('pilotAlon.parameter')}</th>
                        <th>{t('pilotAlon.value')}</th>
                        <th>{t('pilotAlon.unit')}</th>
                        <th>{t('pilotAlon.sourceFile')}</th>
                        <th>{t('pilotAlon.confidence')}</th>
                        <th>{t('pilotAlon.status')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {catMetrics.map((m, idx) => (
                        <tr key={idx}>
                          <td style={{ fontSize: 13 }}>{m.label}</td>
                          <td
                            style={{
                              fontFamily: 'var(--font-mono)',
                              fontWeight: 600,
                              color: m.is_missing ? 'var(--color-error)' : undefined,
                            }}
                          >
                            {m.is_missing
                              ? t('pilotAlon.missingEvidence')
                              : typeof m.value === 'number'
                                ? m.value.toLocaleString()
                                : m.value != null
                                  ? String(m.value)
                                  : '\u2014'}
                          </td>
                          <td style={{ color: 'var(--color-text-dim)', fontSize: 12 }}>
                            {m.unit}
                          </td>
                          <td style={{ fontSize: 12 }}>
                            {m.source_file || '\u2014'}
                          </td>
                          <td>
                            {!m.is_missing && <ConfidenceBar value={m.confidence} />}
                          </td>
                          <td>
                            {m.is_missing ? (
                              <span
                                className="badge"
                                style={{
                                  background: 'var(--color-error)',
                                  color: '#fff',
                                  fontSize: 11,
                                }}
                                title={m.missing_reason}
                              >
                                {t('pilotAlon.missing')}
                              </span>
                            ) : (
                              <span
                                className="badge"
                                style={{
                                  background: 'var(--color-success)',
                                  color: '#fff',
                                  fontSize: 11,
                                }}
                              >
                                {t('pilotAlon.extracted')}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 90
      ? 'var(--color-success)'
      : pct >= 70
        ? 'var(--color-warning)'
        : 'var(--color-error)';
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
        <div
          style={{ width: `${pct}%`, height: '100%', borderRadius: 3, background: color }}
        />
      </div>
      <span
        style={{
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          color: 'var(--color-text-dim)',
        }}
      >
        {pct}%
      </span>
    </div>
  );
}

function ComplianceGroupsSection({
  groups,
  t,
}: {
  groups: ComplianceGroup[];
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(0);

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
        <Search size={18} /> {t('pilotAlon.complianceResults')}
      </h3>
      <div style={{ display: 'grid', gap: 8 }}>
        {groups.map((g, idx) => {
          const isOpen = expandedIdx === idx;
          const layerLabel = LAYER_LABELS_HE[g.layer] || g.layer;
          return (
            <div
              key={idx}
              style={{
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 16px',
                  cursor: 'pointer',
                  background: 'var(--color-surface-2)',
                }}
                onClick={() => setExpandedIdx(isOpen ? null : idx)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>
                    {layerLabel} / {g.discipline}
                  </span>
                  {g.fail_count > 0 && (
                    <span className="badge" style={{ background: 'var(--color-error)', color: '#fff', fontSize: 10 }}>
                      {g.fail_count} {t('pilotAlon.errors')}
                    </span>
                  )}
                  {g.warning_count > 0 && (
                    <span className="badge" style={{ background: 'var(--color-warning)', color: '#000', fontSize: 10 }}>
                      {g.warning_count} {t('pilotAlon.warnings')}
                    </span>
                  )}
                </div>
                {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
              {isOpen && (
                <div className="table-responsive" style={{ padding: 0 }}>
                  <table>
                    <thead>
                      <tr>
                        <th>{t('pilotAlon.severity')}</th>
                        <th>{t('pilotAlon.rule')}</th>
                        <th>{t('pilotAlon.message')}</th>
                        <th>{t('pilotAlon.expectedValue')}</th>
                        <th>{t('pilotAlon.observedValue')}</th>
                        <th>{t('pilotAlon.deviation')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {g.findings.map((f: Finding) => (
                        <tr key={f.finding_id}>
                          <td><StatusBadge status={f.severity} /></td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                            {f.rule_ref}
                            {f.regulation_basis && (
                              <div style={{ fontSize: 10, color: 'var(--color-text-dim)' }}>
                                {f.regulation_basis}
                              </div>
                            )}
                          </td>
                          <td style={{ fontSize: 13 }}>
                            {f.message}
                            {f.explanation && (
                              <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 2 }}>
                                {f.explanation}
                              </div>
                            )}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                            {f.expected_value != null ? String(f.expected_value) : '\u2014'}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                            {f.observed_value != null ? String(f.observed_value) : '\u2014'}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                            {f.deviation != null ? (
                              <span style={{ color: f.deviation !== 0 ? 'var(--color-error)' : undefined }}>
                                {f.deviation > 0 ? '+' : ''}{f.deviation.toFixed(2)}
                              </span>
                            ) : '\u2014'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SectionComparisonsTable({
  comparisons,
  t,
}: {
  comparisons: SectionComparison[];
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const [expanded, setExpanded] = useState(true);

  const statusColor = (s: string) => {
    switch (s) {
      case 'pass': return 'var(--color-success)';
      case 'fail': return 'var(--color-error)';
      case 'warn': return 'var(--color-warning)';
      case 'missing': return 'var(--color-error)';
      case 'manual_review': return 'var(--color-info)';
      default: return 'var(--color-text-dim)';
    }
  };

  const statusLabel = (s: string) => {
    switch (s) {
      case 'pass': return t('pilotAlon.pass');
      case 'fail': return t('pilotAlon.fail');
      case 'warn': return t('pilotAlon.warn');
      case 'missing': return t('pilotAlon.missing');
      case 'manual_review': return t('pilotAlon.manualReview');
      default: return s;
    }
  };

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
        <Search size={18} /> {t('pilotAlon.sectionComparisons')} ({comparisons.length})
        <span style={{ marginInlineStart: 'auto' }}>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </span>
      </h3>
      {expanded && (
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>{t('pilotAlon.section')}</th>
                <th>{t('pilotAlon.category')}</th>
                <th>{t('pilotAlon.regulationValue')}</th>
                <th>{t('pilotAlon.submissionValue')}</th>
                <th>{t('pilotAlon.deviation')}</th>
                <th>{t('pilotAlon.status')}</th>
                <th>{t('pilotAlon.explanation')}</th>
              </tr>
            </thead>
            <tbody>
              {comparisons.map((c, idx) => (
                <tr key={idx}>
                  <td style={{ fontSize: 12, fontWeight: 600 }}>
                    <div>{c.section_id}</div>
                    <div style={{ fontWeight: 400, color: 'var(--color-text-dim)', fontSize: 11 }}>
                      {c.section_title}
                    </div>
                  </td>
                  <td style={{ fontSize: 12 }}>
                    {CATEGORY_LABELS_HE[c.category] || c.category}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    {c.regulation_value != null ? String(c.regulation_value) : '\u2014'}
                    {c.unit && <span style={{ color: 'var(--color-text-dim)', marginInlineStart: 4 }}>{c.unit}</span>}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    {c.submission_value != null ? String(c.submission_value) : '\u2014'}
                    {c.unit && <span style={{ color: 'var(--color-text-dim)', marginInlineStart: 4 }}>{c.unit}</span>}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    {c.deviation != null ? (
                      <span style={{ color: Math.abs(c.deviation) > 0 ? statusColor(c.status) : undefined }}>
                        {c.deviation > 0 ? '+' : ''}{c.deviation.toFixed(2)}
                      </span>
                    ) : '\u2014'}
                  </td>
                  <td>
                    <span
                      className="badge"
                      style={{
                        background: `${statusColor(c.status)}20`,
                        color: statusColor(c.status),
                        fontSize: 11,
                        border: `1px solid ${statusColor(c.status)}40`,
                      }}
                    >
                      {statusLabel(c.status)}
                    </span>
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--color-text-dim)', maxWidth: 250 }}>
                    {c.explanation}
                    {c.evidence_links && c.evidence_links.length > 0 && (
                      <div style={{ marginTop: 4, fontSize: 10, color: 'var(--color-primary)' }}>
                        {c.evidence_links.join(' | ')}
                      </div>
                    )}
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

function OfficialityBadge({
  status,
  confidence,
  t,
}: {
  status: string;
  confidence: number;
  t: (key: string) => string;
}) {
  const pct = Math.round(confidence * 100);
  let color: string;
  let label: string;

  switch (status) {
    case 'verified_official':
      color = 'var(--color-success)';
      label = t('pilotAlon.verified');
      break;
    case 'likely_official':
      color = 'var(--color-warning)';
      label = t('pilotAlon.likelyOfficial');
      break;
    case 'unverified':
      color = 'var(--color-error)';
      label = t('pilotAlon.unverified');
      break;
    case 'pending':
      color = 'var(--color-text-dim)';
      label = t('pilotAlon.pendingReview');
      break;
    default:
      color = 'var(--color-text-dim)';
      label = status;
  }

  return (
    <span
      className="badge"
      style={{
        background: `${color}20`,
        color,
        fontSize: 10,
        border: `1px solid ${color}40`,
      }}
      title={`${pct}% confidence`}
    >
      {label} ({pct}%)
    </span>
  );
}

function CoverageSection({
  coverage,
  t,
}: {
  coverage: DocumentCoverage[];
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
        <FileText size={18} /> {t('pilotAlon.documentCoverage')}
      </h3>
      <div className="table-responsive">
        <table>
          <thead>
            <tr>
              <th>{t('pilotAlon.fileName')}</th>
              <th>{t('pilotAlon.role')}</th>
              <th>{t('pilotAlon.type')}</th>
              <th>{t('pilotAlon.officialityStatus')}</th>
              <th>{t('pilotAlon.legalStatus')}</th>
              <th>{t('pilotAlon.factsExtracted')}</th>
            </tr>
          </thead>
          <tbody>
            {coverage.map((doc, idx) => (
              <tr key={idx}>
                <td style={{ fontSize: 13 }}>{doc.file_name}</td>
                <td>
                  <span
                    className={`badge badge-${doc.document_role === 'regulation' ? 'warning' : 'info'}`}
                  >
                    {doc.document_role}
                  </span>
                </td>
                <td style={{ fontSize: 12 }}>{doc.document_type || '\u2014'}</td>
                <td>
                  <OfficialityBadge
                    status={doc.officiality_status}
                    confidence={doc.officiality_confidence}
                    t={t}
                  />
                </td>
                <td style={{ fontSize: 11 }}>
                  {doc.legal_status !== 'unknown' ? doc.legal_status : '\u2014'}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {doc.facts_extracted}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MissingSection({
  evidence,
  documents,
  t,
}: {
  evidence: MissingEvidence[];
  documents: string[];
  t: (key: string, params?: Record<string, string>) => string;
}) {
  return (
    <div className="card" style={{ borderColor: 'var(--color-warning)' }}>
      <h3
        style={{
          fontSize: 15,
          fontWeight: 600,
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'var(--color-warning)',
        }}
      >
        <FileWarning size={18} /> {t('pilotAlon.missingEvidenceTitle')}
      </h3>

      {evidence.length > 0 && (
        <>
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            {t('pilotAlon.missingParameters')}
          </h4>
          <div className="table-responsive" style={{ marginBottom: 16 }}>
            <table>
              <thead>
                <tr>
                  <th>{t('pilotAlon.category')}</th>
                  <th>{t('pilotAlon.expectedSource')}</th>
                  <th>{t('pilotAlon.reason')}</th>
                </tr>
              </thead>
              <tbody>
                {evidence.map((e, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 600 }}>
                      {CATEGORY_LABELS_HE[e.category] || e.category}
                    </td>
                    <td style={{ fontSize: 12 }}>{e.expected_source}</td>
                    <td style={{ fontSize: 13, color: 'var(--color-text-dim)' }}>
                      {e.reason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {documents.length > 0 && (
        <>
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            {t('pilotAlon.missingDocuments')}
          </h4>
          <ul style={{ margin: 0, paddingInlineStart: 20 }}>
            {documents.map((doc) => (
              <li key={doc} style={{ fontSize: 13, marginBottom: 4 }}>
                {doc}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
