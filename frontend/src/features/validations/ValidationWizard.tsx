import { useState, useCallback, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { ArrowLeft, Upload, CheckCircle2, AlertTriangle, Loader2, FileUp } from 'lucide-react';
import { createRevision } from '../../shared/api/projects';
import { listRulesets } from '../../shared/api/rulesets';
import { startValidation, getValidation } from '../../shared/api/validations';
import { useToast } from '../../shared/components/Toast';
import { useI18n } from '../../shared/i18n';
import Spinner from '../../shared/components/Spinner';
import StatusBadge from '../../shared/components/StatusBadge';
import type { ValidationRun } from '../../shared/api/types';

type Step = 'upload' | 'ruleset' | 'running' | 'done';

export default function ValidationWizard() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { showError } = useToast();
  const { t } = useI18n();

  const [step, setStep] = useState<Step>('upload');
  const [files, setFiles] = useState<File[]>([]);
  const [revisionId, setRevisionId] = useState<string | null>(null);
  const [selectedRulesetId, setSelectedRulesetId] = useState<string | null>(null);
  const [validationRun, setValidationRun] = useState<ValidationRun | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval>>(undefined);

  const { data: rulesets, isLoading: loadingRulesets } = useQuery({
    queryKey: ['rulesets'],
    queryFn: listRulesets,
    enabled: step === 'ruleset',
  });

  const uploadMut = useMutation({
    mutationFn: () => createRevision(projectId!, files),
    onSuccess: (rev) => {
      setRevisionId(rev.revision_id);
      setStep('ruleset');
    },
    onError: () => showError(t('validation.uploadError')),
  });

  const validateMut = useMutation({
    mutationFn: () => startValidation(projectId!, revisionId!, selectedRulesetId!),
    onSuccess: (run) => {
      setValidationRun(run);
      setStep('running');
    },
    onError: () => showError(t('validation.startError')),
  });

  useEffect(() => {
    if (step !== 'running' || !validationRun) return;
    pollRef.current = setInterval(async () => {
      try {
        const updated = await getValidation(validationRun.validation_id);
        setValidationRun(updated);
        if (updated.status === 'done' || updated.status === 'failed') {
          setStep('done');
          clearInterval(pollRef.current);
        }
      } catch { /* retry next interval */ }
    }, 1500);
    return () => clearInterval(pollRef.current);
  }, [step, validationRun]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const dropped = Array.from(e.dataTransfer.files).filter(
      (f) => /\.(ifc|pdf|dwg)$/i.test(f.name)
    );
    if (dropped.length) setFiles((prev) => [...prev, ...dropped]);
    else showError(t('validation.onlySupported'));
  }, [showError, t]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
  };

  const removeFile = (idx: number) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link to={`/advanced/projects/${projectId}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--color-text-dim)' }}>
          <ArrowLeft size={14} /> {t('validation.backToProject')}
        </Link>
      </div>

      {/* Steps indicator */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 32 }}>
        {(['upload', 'ruleset', 'running', 'done'] as Step[]).map((s, i) => (
          <div key={s} style={{
            flex: 1, height: 4, borderRadius: 2,
            background: i <= ['upload', 'ruleset', 'running', 'done'].indexOf(step) ? 'var(--color-primary)' : 'var(--color-border)',
            transition: 'background 0.3s',
          }} />
        ))}
      </div>

      {step === 'upload' && (
        <div className="card" style={{ maxWidth: 600, margin: '0 auto' }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>
            <Upload size={20} style={{ marginInlineEnd: 8, verticalAlign: -4 }} />
            {t('validation.uploadFiles')}
          </h2>
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            style={{
              border: `2px dashed ${isDragOver ? 'var(--color-primary)' : 'var(--color-border)'}`,
              borderRadius: 'var(--radius-lg)',
              padding: 40, textAlign: 'center',
              background: isDragOver ? 'rgba(108,138,255,.06)' : 'transparent',
              transition: 'all 0.15s', cursor: 'pointer',
            }}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <FileUp size={40} color="var(--color-text-dim)" />
            <p style={{ marginTop: 12, color: 'var(--color-text-dim)', fontSize: 14 }}>
              {t('validation.dragDrop')}
            </p>
            <input id="file-input" type="file" multiple accept=".ifc,.pdf,.dwg" style={{ display: 'none' }} onChange={handleFileInput} />
          </div>

          {files.length > 0 && (
            <div style={{ marginTop: 16 }}>
              {files.map((f, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '8px 12px', borderRadius: 'var(--radius)', background: 'var(--color-surface-2)', marginBottom: 6,
                }}>
                  <span style={{ fontSize: 13 }}>{f.name} <span style={{ color: 'var(--color-text-dim)' }}>({(f.size / 1024).toFixed(0)} KB)</span></span>
                  <button className="btn-secondary btn-sm" onClick={() => removeFile(i)}>{t('common.remove')}</button>
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
            <button className="btn-primary" disabled={!files.length || uploadMut.isPending}
              onClick={() => uploadMut.mutate()}>
              {uploadMut.isPending ? <><Spinner size={14} /> {t('validation.uploading')}</> : t('validation.uploadContinue')}
            </button>
          </div>
        </div>
      )}

      {step === 'ruleset' && (
        <div className="card" style={{ maxWidth: 600, margin: '0 auto' }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>{t('validation.selectRuleset')}</h2>
          {loadingRulesets ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner size={24} /></div>
          ) : !rulesets?.length ? (
            <div style={{ textAlign: 'center', padding: 24, color: 'var(--color-text-dim)' }}>
              <p>{t('validation.noRulesets')}</p>
              <Link to="/rulesets" className="btn-primary" style={{ display: 'inline-block', marginTop: 12 }}>{t('validation.goToRulesets')}</Link>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {rulesets.map((rs) => (
                  <div key={rs.ruleset_id}
                    onClick={() => setSelectedRulesetId(rs.ruleset_id)}
                    style={{
                      padding: 14, borderRadius: 'var(--radius)',
                      border: `2px solid ${selectedRulesetId === rs.ruleset_id ? 'var(--color-primary)' : 'var(--color-border)'}`,
                      background: selectedRulesetId === rs.ruleset_id ? 'rgba(108,138,255,.06)' : 'transparent',
                      cursor: 'pointer', transition: 'all 0.15s',
                    }}>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{rs.name}</div>
                    <div style={{ fontSize: 12, color: 'var(--color-text-dim)', marginTop: 4 }}>
                      v{rs.version} &middot; {rs.jurisdiction} &middot; {rs.rules.length} {t('rulesets.rules').toLowerCase()}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
                <button className="btn-primary" disabled={!selectedRulesetId || validateMut.isPending}
                  onClick={() => validateMut.mutate()}>
                  {validateMut.isPending ? <><Spinner size={14} /> {t('validation.starting')}</> : t('validation.runValidation')}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {step === 'running' && validationRun && (
        <div className="card" style={{ maxWidth: 500, margin: '0 auto', textAlign: 'center', padding: 48 }}>
          <Loader2 size={48} color="var(--color-primary)" style={{ animation: 'spin 1s linear infinite' }} />
          <h2 style={{ fontSize: 18, fontWeight: 600, marginTop: 20 }}>{t('validation.running')}</h2>
          <p style={{ color: 'var(--color-text-dim)', marginTop: 8, fontSize: 14 }}>
            {t('validation.processing')}
          </p>
          <div style={{ marginTop: 16 }}><StatusBadge status={validationRun.status} /></div>
        </div>
      )}

      {step === 'done' && validationRun && (
        <div className="card" style={{ maxWidth: 500, margin: '0 auto', textAlign: 'center', padding: 48 }}>
          {validationRun.status === 'done' ? (
            <>
              <CheckCircle2 size={48} color="var(--color-success)" />
              <h2 style={{ fontSize: 18, fontWeight: 600, marginTop: 16 }}>{t('validation.complete')}</h2>
              <p style={{ color: 'var(--color-text-dim)', marginTop: 8, fontSize: 14 }}>
                {t('validation.findingsDetected', { count: validationRun.findings_count ?? 0 })}
              </p>
            </>
          ) : (
            <>
              <AlertTriangle size={48} color="var(--color-error)" />
              <h2 style={{ fontSize: 18, fontWeight: 600, marginTop: 16 }}>{t('validation.failed')}</h2>
              <p style={{ color: 'var(--color-error)', marginTop: 8, fontSize: 14 }}>
                {validationRun.error_message || t('validation.unexpectedError')}
              </p>
            </>
          )}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 24 }}>
            <button className="btn-secondary" onClick={() => navigate(`/advanced/projects/${projectId}`)}>
              {t('validation.backToProject')}
            </button>
            {validationRun.status === 'done' && (
              <button className="btn-primary" onClick={() => navigate(`/advanced/validations/${validationRun.validation_id}/findings`)}>
                {t('validation.viewFindings')}
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}
