import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Upload,
  FileUp,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ArrowRight,
  ArrowLeft,
  Table2,
  Scale,
  BarChart3,
  Pencil,
  Check,
  X,
} from 'lucide-react';
import { createProject, createRevision, getRevisionFacts, updateFact } from '../../shared/api/projects';
import { listRulesets } from '../../shared/api/rulesets';
import { startValidation, getValidation, getComplianceReport } from '../../shared/api/validations';
import { useToast } from '../../shared/components/Toast';
import { useI18n } from '../../shared/i18n';
import Spinner from '../../shared/components/Spinner';
import AiProposalsPanel from '../ai/AiProposalsPanel';
import type { ExtractedFact, ValidationRun, ComplianceReport, Finding } from '../../shared/api/types';

type Step = 'upload' | 'extraction' | 'rules' | 'compare';

const STEPS: Step[] = ['upload', 'extraction', 'rules', 'compare'];
const ACCEPTED_EXTENSIONS = /\.(ifc|pdf|dwg|dwfx)$/i;

export default function SimpleWorkflowPage() {
  const { t } = useI18n();
  const { showError } = useToast();
  const queryClient = useQueryClient();

  const [step, setStep] = useState<Step>('upload');
  const [files, setFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [revisionId, setRevisionId] = useState<string | null>(null);
  const [selectedRulesetId, setSelectedRulesetId] = useState<string | null>(null);
  const [validationRun, setValidationRun] = useState<ValidationRun | null>(null);
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval>>(undefined);

  const factsQuery = useQuery({
    queryKey: ['workflowFacts', projectId, revisionId],
    queryFn: () => getRevisionFacts(projectId!, revisionId!),
    enabled: !!projectId && !!revisionId && step !== 'upload',
  });

  const rulesetsQuery = useQuery({
    queryKey: ['rulesets'],
    queryFn: listRulesets,
    enabled: step === 'rules',
  });

  const uploadMut = useMutation({
    mutationFn: async () => {
      const proj = await createProject(`Analysis ${new Date().toLocaleDateString()}`);
      const rev = await createRevision(proj.project_id, files);
      return { proj, rev };
    },
    onSuccess: ({ proj, rev }) => {
      setProjectId(proj.project_id);
      setRevisionId(rev.revision_id);
      setStep('extraction');
    },
    onError: () => showError(t('validation.uploadError')),
  });

  const validateMut = useMutation({
    mutationFn: () => startValidation(projectId!, revisionId!, selectedRulesetId!),
    onSuccess: (run) => {
      setValidationRun(run);
      setStep('compare');
    },
    onError: () => showError(t('validation.startError')),
  });

  useEffect(() => {
    if (step !== 'compare' || !validationRun) return;
    if (validationRun.status === 'done' || validationRun.status === 'failed') {
      if (validationRun.status === 'done') {
        getComplianceReport(validationRun.validation_id).then(setReport).catch(() => {});
      }
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const updated = await getValidation(validationRun.validation_id);
        setValidationRun(updated);
        if (updated.status === 'done' || updated.status === 'failed') {
          clearInterval(pollRef.current);
          if (updated.status === 'done') {
            getComplianceReport(updated.validation_id).then(setReport).catch(() => {});
          }
        }
      } catch { /* retry */ }
    }, 1500);
    return () => clearInterval(pollRef.current);
  }, [step, validationRun]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const dropped = Array.from(e.dataTransfer.files).filter(f => ACCEPTED_EXTENSIONS.test(f.name));
    if (dropped.length) setFiles(prev => [...prev, ...dropped]);
    else showError(t('workflow.supportedFormats'));
  }, [showError, t]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles(prev => [...prev, ...Array.from(e.target.files!)]);
  };

  const removeFile = (idx: number) => setFiles(prev => prev.filter((_, i) => i !== idx));

  const startOver = () => {
    setStep('upload');
    setFiles([]);
    setProjectId(null);
    setRevisionId(null);
    setSelectedRulesetId(null);
    setValidationRun(null);
    setReport(null);
  };

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>{t('workflow.title')}</h1>

      {/* Steps indicator */}
      <StepBar currentStep={step} t={t} />

      <div style={{ marginTop: 32 }}>
        {step === 'upload' && (
          <UploadStep
            files={files}
            isDragOver={isDragOver}
            setIsDragOver={setIsDragOver}
            onDrop={handleDrop}
            onFileInput={handleFileInput}
            onRemove={removeFile}
            onContinue={() => uploadMut.mutate()}
            isPending={uploadMut.isPending}
            t={t}
          />
        )}

        {step === 'extraction' && projectId && revisionId && (
          <ExtractionStep
            projectId={projectId}
            revisionId={revisionId}
            facts={factsQuery.data ?? []}
            isLoading={factsQuery.isLoading}
            fileCount={files.length}
            onBack={() => startOver()}
            onNext={() => setStep('rules')}
            t={t}
            queryClient={queryClient}
          />
        )}

        {step === 'rules' && (
          <RulesStep
            rulesets={rulesetsQuery.data ?? []}
            isLoading={rulesetsQuery.isLoading}
            selectedId={selectedRulesetId}
            onSelect={setSelectedRulesetId}
            onBack={() => setStep('extraction')}
            onCompare={() => validateMut.mutate()}
            isPending={validateMut.isPending}
            t={t}
          />
        )}

        {step === 'compare' && (
          <CompareStep
            validationRun={validationRun}
            report={report}
            onStartOver={startOver}
            onBack={() => setStep('rules')}
            projectId={projectId!}
            revisionId={revisionId!}
            t={t}
          />
        )}
      </div>
    </div>
  );
}

/* ── Step Bar ─────────────────────────────────────────────────────────────── */

function StepBar({ currentStep, t }: { currentStep: Step; t: (k: string) => string }) {
  const stepLabels: Record<Step, { labelKey: string; Icon: typeof Upload }> = {
    upload: { labelKey: 'workflow.step.upload', Icon: Upload },
    extraction: { labelKey: 'workflow.step.extraction', Icon: Table2 },
    rules: { labelKey: 'workflow.step.rules', Icon: Scale },
    compare: { labelKey: 'workflow.step.compare', Icon: BarChart3 },
  };

  const idx = STEPS.indexOf(currentStep);

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
      {STEPS.map((s, i) => {
        const { labelKey, Icon } = stepLabels[s];
        const isActive = i === idx;
        const isDone = i < idx;
        return (
          <div key={s} style={{ flex: 1, textAlign: 'center' }}>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: 36, height: 36, borderRadius: '50%', margin: '0 auto',
              background: isDone ? 'var(--color-success)' : isActive ? 'var(--color-primary)' : 'var(--color-surface-2)',
              color: isDone || isActive ? '#fff' : 'var(--color-text-dim)',
              transition: 'all 0.3s',
            }}>
              {isDone ? <CheckCircle2 size={18} /> : <Icon size={18} />}
            </div>
            <div style={{
              fontSize: 12, marginTop: 6, fontWeight: isActive ? 600 : 400,
              color: isActive ? 'var(--color-text)' : 'var(--color-text-dim)',
            }}>
              {t(labelKey)}
            </div>
            {i < STEPS.length - 1 && (
              <div style={{
                position: 'relative', top: -28,
                height: 2, marginInline: 'calc(50% + 22px)', marginInlineEnd: 'calc(-50% + 22px)',
                background: i < idx ? 'var(--color-success)' : 'var(--color-border)',
                transition: 'background 0.3s',
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Step 1: Upload ───────────────────────────────────────────────────────── */

function UploadStep({
  files, isDragOver, setIsDragOver, onDrop, onFileInput, onRemove, onContinue, isPending, t,
}: {
  files: File[];
  isDragOver: boolean;
  setIsDragOver: (v: boolean) => void;
  onDrop: (e: React.DragEvent) => void;
  onFileInput: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRemove: (i: number) => void;
  onContinue: () => void;
  isPending: boolean;
  t: (k: string, p?: Record<string, string>) => string;
}) {
  return (
    <div className="card" style={{ maxWidth: 600, margin: '0 auto' }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Upload size={20} />
        {t('workflow.step.upload')}
      </h2>
      <div
        onDrop={onDrop}
        onDragOver={e => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onClick={() => document.getElementById('wf-file-input')?.click()}
        style={{
          border: `2px dashed ${isDragOver ? 'var(--color-primary)' : 'var(--color-border)'}`,
          borderRadius: 'var(--radius-lg)', padding: 48, textAlign: 'center',
          background: isDragOver ? 'rgba(108,138,255,.06)' : 'transparent',
          cursor: 'pointer', transition: 'all 0.15s',
        }}
      >
        <FileUp size={44} color="var(--color-text-dim)" />
        <p style={{ marginTop: 12, color: 'var(--color-text-dim)', fontSize: 14 }}>
          {t('workflow.uploadHint')}
        </p>
        <p style={{ marginTop: 4, color: 'var(--color-text-dim)', fontSize: 12 }}>
          {t('workflow.supportedFormats')}
        </p>
        <input
          id="wf-file-input" type="file" multiple
          accept=".ifc,.pdf,.dwg,.dwfx"
          style={{ display: 'none' }}
          onChange={onFileInput}
        />
      </div>

      {files.length > 0 && (
        <div style={{ marginTop: 16 }}>
          {files.map((f, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '8px 12px', borderRadius: 'var(--radius)',
              background: 'var(--color-surface-2)', marginBottom: 6,
            }}>
              <span style={{ fontSize: 13 }}>
                {f.name}{' '}
                <span style={{ color: 'var(--color-text-dim)' }}>
                  ({(f.size / 1024).toFixed(0)} KB)
                </span>
              </span>
              <button className="btn-secondary btn-sm" onClick={(e) => { e.stopPropagation(); onRemove(i); }}>
                {t('common.remove')}
              </button>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          className="btn-primary"
          disabled={!files.length || isPending}
          onClick={(e) => { e.stopPropagation(); onContinue(); }}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          {isPending ? (
            <><Spinner size={14} /> {t('workflow.processing')}</>
          ) : (
            <>{t('workflow.next')} <ArrowRight size={14} /></>
          )}
        </button>
      </div>
    </div>
  );
}

/* ── Step 2: Extraction Table ─────────────────────────────────────────────── */

function ExtractionStep({
  projectId, revisionId, facts, isLoading, fileCount, onBack, onNext, t, queryClient,
}: {
  projectId: string;
  revisionId: string;
  facts: ExtractedFact[];
  isLoading: boolean;
  fileCount: number;
  onBack: () => void;
  onNext: () => void;
  t: (k: string, p?: Record<string, string>) => string;
  queryClient: ReturnType<typeof useQueryClient>;
}) {
  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spinner size={28} />
      </div>
    );
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Table2 size={20} />
              {t('workflow.step.extraction')}
            </h2>
            <p style={{ color: 'var(--color-text-dim)', fontSize: 13, marginTop: 4 }}>
              {t('workflow.factsExtracted', { count: String(facts.length), files: String(fileCount) })}
            </p>
          </div>
          <p style={{ color: 'var(--color-text-dim)', fontSize: 12, fontStyle: 'italic' }}>
            {t('workflow.editHint')}
          </p>
        </div>
      </div>

      {facts.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-dim)' }}>
          <AlertTriangle size={40} color="var(--color-warning)" />
          <p style={{ marginTop: 12 }}>{t('workflow.noFacts')}</p>
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>{t('workflow.category')}</th>
                  <th>{t('workflow.label')}</th>
                  <th>{t('workflow.value')}</th>
                  <th>{t('workflow.unit')}</th>
                  <th>{t('workflow.source')}</th>
                  <th>{t('workflow.confidence')}</th>
                </tr>
              </thead>
              <tbody>
                {facts.map(fact => (
                  <EditableFactRow
                    key={fact.fact_id}
                    fact={fact}
                    projectId={projectId}
                    revisionId={revisionId}
                    queryClient={queryClient}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* AI Panel */}
      <AiProposalsPanel projectId={projectId} revisionId={revisionId} />

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
        <button className="btn-secondary" onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <ArrowLeft size={14} /> {t('workflow.back')}
        </button>
        <button className="btn-primary" onClick={onNext} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {t('workflow.next')} <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}

/* ── Editable Fact Row ────────────────────────────────────────────────────── */

function EditableFactRow({
  fact, projectId, revisionId, queryClient,
}: {
  fact: ExtractedFact;
  projectId: string;
  revisionId: string;
  queryClient: ReturnType<typeof useQueryClient>;
}) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const updateMut = useMutation({
    mutationFn: (updates: Partial<Pick<ExtractedFact, 'label' | 'value' | 'unit' | 'category'>>) =>
      updateFact(projectId, revisionId, fact.fact_id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflowFacts', projectId, revisionId] });
      setEditingField(null);
    },
  });

  const startEdit = (field: string, currentValue: unknown) => {
    setEditingField(field);
    setEditValue(currentValue != null ? String(currentValue) : '');
  };

  const commitEdit = () => {
    if (editingField) {
      const val = editingField === 'value' ? (isNaN(Number(editValue)) ? editValue : Number(editValue)) : editValue;
      updateMut.mutate({ [editingField]: val });
    }
  };

  const cancelEdit = () => {
    setEditingField(null);
    setEditValue('');
  };

  const isLowConf = fact.confidence < 0.5;
  const isUnknown = !fact.value || fact.category === 'unknown';
  const rowStyle: React.CSSProperties = isUnknown
    ? { background: 'rgba(245,158,11,.06)' }
    : isLowConf
      ? { background: 'rgba(245,158,11,.03)' }
      : {};

  const renderCell = (field: string, value: unknown, mono = false) => {
    if (editingField === field) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <input
            autoFocus
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }}
            style={{ padding: '4px 8px', fontSize: 13, width: 120 }}
          />
          <button className="btn-primary btn-sm" onClick={commitEdit} style={{ padding: '3px 6px' }}>
            <Check size={12} />
          </button>
          <button className="btn-secondary btn-sm" onClick={cancelEdit} style={{ padding: '3px 6px' }}>
            <X size={12} />
          </button>
        </div>
      );
    }
    return (
      <span
        onClick={() => startEdit(field, value)}
        style={{
          cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '2px 6px', borderRadius: 4, fontSize: 13,
          fontFamily: mono ? 'var(--font-mono)' : 'inherit',
          border: '1px solid transparent',
        }}
        onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--color-border)')}
        onMouseLeave={e => (e.currentTarget.style.borderColor = 'transparent')}
      >
        {value != null ? String(value) : '\u2014'}
        <Pencil size={10} color="var(--color-text-dim)" style={{ opacity: 0.4 }} />
      </span>
    );
  };

  return (
    <tr style={rowStyle}>
      <td>
        <span className="badge badge-info" style={{ fontSize: 11 }}>{fact.category}</span>
      </td>
      <td>{renderCell('label', fact.label)}</td>
      <td>{renderCell('value', fact.value, true)}</td>
      <td>{renderCell('unit', fact.unit)}</td>
      <td style={{ fontSize: 12, color: 'var(--color-text-dim)', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {fact.metadata?.source_file as string || '\u2014'}
      </td>
      <td><ConfidencePill value={fact.confidence} /></td>
    </tr>
  );
}

/* ── Step 3: Rules ────────────────────────────────────────────────────────── */

function RulesStep({
  rulesets, isLoading, selectedId, onSelect, onBack, onCompare, isPending, t,
}: {
  rulesets: { ruleset_id: string; name: string; version: string; jurisdiction: string; rules: unknown[] }[];
  isLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onBack: () => void;
  onCompare: () => void;
  isPending: boolean;
  t: (k: string) => string;
}) {
  return (
    <div className="card" style={{ maxWidth: 600, margin: '0 auto' }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Scale size={20} />
        {t('workflow.step.rules')}
      </h2>
      <p style={{ color: 'var(--color-text-dim)', fontSize: 13, marginBottom: 16 }}>
        {t('workflow.addRuleset')}
      </p>

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner size={24} /></div>
      ) : !rulesets?.length ? (
        <div style={{ textAlign: 'center', padding: 24, color: 'var(--color-text-dim)' }}>
          <p>{t('validation.noRulesets')}</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {rulesets.map(rs => (
            <div
              key={rs.ruleset_id}
              onClick={() => onSelect(rs.ruleset_id)}
              style={{
                padding: 14, borderRadius: 'var(--radius)',
                border: `2px solid ${selectedId === rs.ruleset_id ? 'var(--color-primary)' : 'var(--color-border)'}`,
                background: selectedId === rs.ruleset_id ? 'rgba(108,138,255,.06)' : 'transparent',
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 14 }}>{rs.name}</div>
              <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 4 }}>
                v{rs.version} &middot; {rs.jurisdiction} &middot; {(rs.rules as unknown[]).length} {t('rulesets.rules').toLowerCase()}
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
        <button className="btn-secondary" onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <ArrowLeft size={14} /> {t('workflow.back')}
        </button>
        <button
          className="btn-primary"
          disabled={!selectedId || isPending}
          onClick={onCompare}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          {isPending ? (
            <><Spinner size={14} /> {t('workflow.comparing')}</>
          ) : (
            <>{t('workflow.compare')} <ArrowRight size={14} /></>
          )}
        </button>
      </div>
    </div>
  );
}

/* ── Step 4: Compare ──────────────────────────────────────────────────────── */

function CompareStep({
  validationRun, report, onStartOver, onBack, projectId, revisionId, t,
}: {
  validationRun: ValidationRun | null;
  report: ComplianceReport | null;
  onStartOver: () => void;
  onBack: () => void;
  projectId: string;
  revisionId: string;
  t: (k: string, p?: Record<string, string>) => string;
}) {
  if (!validationRun || (validationRun.status !== 'done' && validationRun.status !== 'failed')) {
    return (
      <div className="card" style={{ maxWidth: 500, margin: '0 auto', textAlign: 'center', padding: 48 }}>
        <Loader2 size={48} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
        <h2 style={{ fontSize: 18, fontWeight: 600, marginTop: 20 }}>{t('workflow.comparing')}</h2>
        <p style={{ color: 'var(--color-text-dim)', marginTop: 8, fontSize: 14 }}>{t('validation.processing')}</p>
      </div>
    );
  }

  if (validationRun.status === 'failed') {
    return (
      <div className="card" style={{ maxWidth: 500, margin: '0 auto', textAlign: 'center', padding: 48 }}>
        <AlertTriangle size={48} color="var(--color-error)" />
        <h2 style={{ fontSize: 18, fontWeight: 600, marginTop: 16 }}>{t('validation.failed')}</h2>
        <p style={{ color: 'var(--color-error)', marginTop: 8, fontSize: 14 }}>
          {validationRun.error_message || t('validation.unexpectedError')}
        </p>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 24 }}>
          <button className="btn-secondary" onClick={onBack}>{t('workflow.back')}</button>
          <button className="btn-primary" onClick={onStartOver}>{t('workflow.startOver')}</button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <BarChart3 size={20} />
          {t('workflow.results')}
        </h2>
        {report && (
          <div style={{ display: 'flex', gap: 16, marginTop: 12, flexWrap: 'wrap' }}>
            <StatCard
              label={t('workflow.passCount', { count: '' })}
              value={report.total_findings - report.total_errors - report.total_warnings}
              color="var(--color-success)"
            />
            <StatCard label={t('workflow.failCount', { count: '' })} value={report.total_errors} color="var(--color-error)" />
            <StatCard label={t('workflow.warnCount', { count: '' })} value={report.total_warnings} color="var(--color-warning)" />
          </div>
        )}
      </div>

      {report && report.section_comparisons.length > 0 && (
        <div className="card" style={{ padding: 0, marginBottom: 16 }}>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>{t('pilotAlon.section')}</th>
                  <th>{t('pilotAlon.regulationValue')}</th>
                  <th>{t('pilotAlon.submissionValue')}</th>
                  <th>{t('pilotAlon.status')}</th>
                  <th>{t('pilotAlon.deviation')}</th>
                  <th>{t('pilotAlon.explanation')}</th>
                </tr>
              </thead>
              <tbody>
                {report.section_comparisons.map((sc, i) => (
                  <tr key={i}>
                    <td style={{ fontSize: 13, fontWeight: 500 }}>{sc.section_title || sc.category}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                      {sc.regulation_value != null ? `${sc.regulation_value} ${sc.unit}` : '\u2014'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                      {sc.submission_value != null ? `${sc.submission_value} ${sc.unit}` : '\u2014'}
                    </td>
                    <td><ComparisonStatusBadge status={sc.status} t={t} /></td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                      {sc.deviation != null ? `${(sc.deviation * 100).toFixed(1)}%` : '\u2014'}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--color-text-dim)', maxWidth: 200 }}>
                      {sc.explanation || '\u2014'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {report && report.groups.length > 0 && (
        <div className="card" style={{ padding: 0, marginBottom: 16 }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--color-border)' }}>
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>{t('pilotAlon.complianceResults')}</h3>
          </div>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>{t('pilotAlon.severity')}</th>
                  <th>{t('pilotAlon.rule')}</th>
                  <th>{t('pilotAlon.message')}</th>
                </tr>
              </thead>
              <tbody>
                {report.groups.flatMap(g => g.findings).map((f: Finding) => (
                  <tr key={f.finding_id}>
                    <td><SeverityBadge severity={f.severity} /></td>
                    <td style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>{f.rule_ref}</td>
                    <td style={{ fontSize: 13 }}>{f.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <AiProposalsPanel projectId={projectId} revisionId={revisionId} />

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'center' }}>
        <button className="btn-primary" onClick={onStartOver} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {t('workflow.startOver')}
        </button>
      </div>
    </div>
  );
}

/* ── Shared small components ──────────────────────────────────────────────── */

function ConfidencePill({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 75 ? 'var(--color-success)' : pct >= 40 ? 'var(--color-warning)' : 'var(--color-error)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontFamily: 'var(--font-mono)', color }}>
      {pct}%
    </span>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      padding: '12px 20px', borderRadius: 'var(--radius)', background: 'var(--color-surface-2)',
      display: 'flex', alignItems: 'center', gap: 10, minWidth: 120,
    }}>
      <span style={{ fontSize: 28, fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>{value}</span>
      <span style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{label}</span>
    </div>
  );
}

function ComparisonStatusBadge({ status, t }: { status: string; t: (k: string) => string }) {
  const map: Record<string, { label: string; color: string }> = {
    pass: { label: t('pilotAlon.pass'), color: 'var(--color-success)' },
    fail: { label: t('pilotAlon.fail'), color: 'var(--color-error)' },
    warn: { label: t('pilotAlon.warn'), color: 'var(--color-warning)' },
    missing: { label: t('pilotAlon.missing'), color: 'var(--color-text-dim)' },
    manual_review: { label: t('pilotAlon.manualReview'), color: 'var(--color-info)' },
  };
  const entry = map[status] || { label: status, color: 'var(--color-text-dim)' };
  return (
    <span style={{ fontSize: 12, fontWeight: 600, color: entry.color }}>{entry.label}</span>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    error: 'var(--color-error)',
    warning: 'var(--color-warning)',
    info: 'var(--color-info)',
  };
  return (
    <span className="badge" style={{
      background: `${colors[severity] || 'var(--color-text-dim)'}20`,
      color: colors[severity] || 'var(--color-text-dim)',
      fontSize: 11, fontWeight: 600,
    }}>
      {severity}
    </span>
  );
}
