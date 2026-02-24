import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Download, FileText, AlertTriangle, Info, AlertCircle, Search } from 'lucide-react';
import { getValidation, getFindings, getReportUrl } from '../../shared/api/validations';
import { useI18n } from '../../shared/i18n';
import Spinner from '../../shared/components/Spinner';
import StatusBadge from '../../shared/components/StatusBadge';
import EmptyState from '../../shared/components/EmptyState';
import Modal from '../../shared/components/Modal';
import type { Finding, Severity } from '../../shared/api/types';

export default function FindingsPage() {
  const { validationId } = useParams<{ validationId: string }>();
  const { t, formatDateTime } = useI18n();
  const [severityFilter, setSeverityFilter] = useState<Severity | 'all'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);

  const { data: validation, isLoading: loadingVal } = useQuery({
    queryKey: ['validation', validationId],
    queryFn: () => getValidation(validationId!),
    enabled: !!validationId,
  });

  const { data: findings, isLoading: loadingFindings } = useQuery({
    queryKey: ['findings', validationId],
    queryFn: () => getFindings(validationId!),
    enabled: !!validationId,
  });

  const filtered = useMemo(() => {
    if (!findings) return [];
    return findings.filter((f) => {
      if (severityFilter !== 'all' && f.severity !== severityFilter) return false;
      if (searchTerm && !f.message.toLowerCase().includes(searchTerm.toLowerCase()) &&
          !f.rule_ref.toLowerCase().includes(searchTerm.toLowerCase())) return false;
      return true;
    });
  }, [findings, severityFilter, searchTerm]);

  const counts = useMemo(() => {
    if (!findings) return { error: 0, warning: 0, info: 0 };
    return {
      error: findings.filter((f) => f.severity === 'error').length,
      warning: findings.filter((f) => f.severity === 'warning').length,
      info: findings.filter((f) => f.severity === 'info').length,
    };
  }, [findings]);

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(findings, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `findings_${validationId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loadingVal || loadingFindings) {
    return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}><Spinner size={32} /></div>;
  }

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link to={validation ? `/projects/${validation.project_id}` : '/'} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--color-text-dim)' }}>
          <ArrowLeft size={14} /> {t('findings.backToProject')}
        </Link>
      </div>

      <div className="page-header">
        <div>
          <h1>{t('findings.title')}</h1>
          {validation && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6, fontSize: 13, color: 'var(--color-text-dim)', flexWrap: 'wrap' }}>
              <StatusBadge status={validation.status} />
              <span>ID: {validation.validation_id}</span>
              <span>{formatDateTime(validation.created_at)}</span>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <a href={getReportUrl(validationId!)} target="_blank" rel="noopener noreferrer" className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', textDecoration: 'none' }}>
            <Download size={14} /> {t('findings.pdfReport')}
          </a>
          <button className="btn-secondary" onClick={downloadJson} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Download size={14} /> {t('findings.json')}
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        {([['error', counts.error, 'var(--color-error)', t('findings.errors')], ['warning', counts.warning, 'var(--color-warning)', t('findings.warnings')], ['info', counts.info, 'var(--color-info)', t('findings.infos')]] as const).map(([sev, count, color, label]) => (
          <div key={sev} className="card" style={{ flex: '1 1 140px', display: 'flex', alignItems: 'center', gap: 12, padding: 16, cursor: 'pointer', borderColor: severityFilter === sev ? color : undefined }}
            onClick={() => setSeverityFilter(severityFilter === sev ? 'all' : sev)}>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: `${color}20`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {sev === 'error' ? <AlertCircle size={20} color={color} /> : sev === 'warning' ? <AlertTriangle size={20} color={color} /> : <Info size={20} color={color} />}
            </div>
            <div>
              <div style={{ fontSize: 24, fontWeight: 700 }}>{count}</div>
              <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Search bar */}
      <div style={{ position: 'relative', marginBottom: 16 }}>
        <Search size={16} style={{ position: 'absolute', insetInlineStart: 12, top: 10, color: 'var(--color-text-dim)' }} />
        <input value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)}
          placeholder={t('findings.searchPlaceholder')}
          style={{ paddingInlineStart: 36 }} />
      </div>

      {/* Findings table */}
      {!filtered.length ? (
        <EmptyState icon={<FileText size={48} />} message={findings?.length ? t('findings.noMatchFilters') : t('findings.noFindings')} />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-responsive">
            <table>
              <thead>
                <tr><th>{t('findings.severity')}</th><th>{t('findings.rule')}</th><th>{t('findings.message')}</th><th>{t('findings.actions')}</th></tr>
              </thead>
              <tbody>
                {filtered.map((f) => (
                  <tr key={f.finding_id}>
                    <td><StatusBadge status={f.severity} /></td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{f.rule_ref}</td>
                    <td style={{ fontSize: 13, maxWidth: 400 }}>{f.message}</td>
                    <td>
                      <button className="btn-secondary btn-sm" onClick={() => setSelectedFinding(f)}>
                        {t('common.details')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal open={!!selectedFinding} onClose={() => setSelectedFinding(null)} title={t('findings.detailsTitle')}>
        {selectedFinding && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('findings.severity')}</label>
              <div><StatusBadge status={selectedFinding.severity} /></div>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('findings.ruleReference')}</label>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>{selectedFinding.rule_ref}</div>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('findings.message')}</label>
              <div style={{ fontSize: 14 }}>{selectedFinding.message}</div>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('findings.computationTrace')}</label>
              <pre style={{
                background: 'var(--color-surface-2)', padding: 12, borderRadius: 'var(--radius)',
                fontSize: 12, fontFamily: 'var(--font-mono)', overflow: 'auto', maxHeight: 200,
              }}>
                {JSON.stringify(selectedFinding.computation_trace, null, 2)}
              </pre>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('findings.inputFacts')}</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {selectedFinding.input_facts.map((f) => (
                  <span key={f} className="badge badge-info" style={{ fontSize: 11 }}>{f}</span>
                ))}
              </div>
            </div>
            {selectedFinding.source_hashes.length > 0 && (
              <div>
                <label style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{t('findings.sourceHashes')}</label>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  {selectedFinding.source_hashes.join(', ')}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}
