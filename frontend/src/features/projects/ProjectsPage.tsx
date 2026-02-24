import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FolderKanban, Plus, Sparkles, Download, RefreshCw, AlertTriangle } from 'lucide-react';
import { listProjects, createProject, bootstrapDemo, listSampleFiles } from '../../shared/api/projects';
import { resolveBaseURL } from '../../shared/api/client';
import { useToast } from '../../shared/components/Toast';
import { useI18n } from '../../shared/i18n';
import Modal from '../../shared/components/Modal';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';
import type { SampleFileInfo } from '../../shared/api/types';

const WAKE_UP_HINT_DELAY_MS = 4000;

export default function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showError, showSuccess } = useToast();
  const { t, formatDate } = useI18n();
  const [showCreate, setShowCreate] = useState(false);
  const [showSamples, setShowSamples] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [showWakeHint, setShowWakeHint] = useState(false);
  const hintTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data: projects, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
  });

  useEffect(() => {
    if (isLoading || isFetching) {
      hintTimerRef.current = setTimeout(() => setShowWakeHint(true), WAKE_UP_HINT_DELAY_MS);
    } else {
      setShowWakeHint(false);
    }
    return () => { if (hintTimerRef.current) clearTimeout(hintTimerRef.current); };
  }, [isLoading, isFetching]);

  const createMut = useMutation({
    mutationFn: () => createProject(name, description),
    onSuccess: (proj) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      showSuccess(t('projects.success', { name: proj.name }));
      setShowCreate(false);
      setName('');
      setDescription('');
      navigate(`/projects/${proj.project_id}`);
    },
    onError: () => showError(t('projects.error')),
  });

  const demoMut = useMutation({
    mutationFn: bootstrapDemo,
    onSuccess: (proj) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      showSuccess(t('demo.success', { name: proj.name }));
      navigate(`/projects/${proj.project_id}`);
    },
    onError: () => showError(t('demo.error')),
  });

  const { data: sampleFiles } = useQuery({
    queryKey: ['sampleFiles'],
    queryFn: listSampleFiles,
    enabled: showSamples,
  });

  if (isError) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80, gap: 12, textAlign: 'center' }}>
        <AlertTriangle size={40} color="var(--color-warning)" />
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>{t('loading.errorTitle')}</h2>
        <p style={{ fontSize: 14, color: 'var(--color-text-dim)', maxWidth: 400 }}>{t('loading.errorMessage')}</p>
        <button className="btn-primary" onClick={() => refetch()} disabled={isFetching} style={{ marginTop: 8 }}>
          {isFetching
            ? <Spinner size={14} />
            : <RefreshCw size={15} style={{ marginInlineEnd: 6, verticalAlign: -2 }} />}
          {t('loading.retry')}
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80, gap: 12 }}>
        <Spinner size={32} />
        {showWakeHint && (
          <p style={{ fontSize: 13, color: 'var(--color-text-dim)', textAlign: 'center', maxWidth: 360, animation: 'fadeIn .4s ease' }}>
            {t('loading.wakeUpHint')}
          </p>
        )}
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <h1>{t('projects.title')}</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-secondary" onClick={() => setShowSamples(true)}>
            <Download size={16} style={{ marginInlineEnd: 6, verticalAlign: -3 }} />
            {t('demo.downloadSamples')}
          </button>
          <button className="btn-secondary" onClick={() => demoMut.mutate()} disabled={demoMut.isPending}>
            {demoMut.isPending ? <Spinner size={14} /> : <Sparkles size={16} style={{ marginInlineEnd: 6, verticalAlign: -3 }} />}
            {t('demo.createDemo')}
          </button>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            <Plus size={16} style={{ marginInlineEnd: 6, verticalAlign: -3 }} />
            {t('projects.new')}
          </button>
        </div>
      </div>

      {!projects?.length ? (
        <EmptyState
          icon={<FolderKanban size={48} />}
          message={t('projects.empty')}
          action={
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
              <button className="btn-primary" onClick={() => demoMut.mutate()} disabled={demoMut.isPending}>
                {demoMut.isPending ? <Spinner size={14} /> : <Sparkles size={16} style={{ marginInlineEnd: 6, verticalAlign: -3 }} />}
                {t('demo.createDemo')}
              </button>
              <button className="btn-secondary" onClick={() => setShowSamples(true)}>
                <Download size={16} style={{ marginInlineEnd: 6, verticalAlign: -3 }} />
                {t('demo.downloadSamples')}
              </button>
              <button className="btn-secondary" onClick={() => setShowCreate(true)}>{t('projects.createProject')}</button>
            </div>
          }
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {projects.map((p) => (
            <div key={p.project_id} className="card" style={{ cursor: 'pointer', transition: 'border-color 0.15s' }}
              onClick={() => navigate(`/projects/${p.project_id}`)}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-border)')}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <FolderKanban size={20} color="var(--color-primary)" />
                <span style={{ fontSize: 16, fontWeight: 600 }}>{p.name}</span>
              </div>
              {p.description && (
                <p style={{ fontSize: 13, color: 'var(--color-text-dim)', marginBottom: 8 }}>{p.description}</p>
              )}
              <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>
                {t('common.created')} {formatDate(p.created_at)}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title={t('projects.createModal.title')}>
        <form onSubmit={(e) => { e.preventDefault(); createMut.mutate(); }}>
          <div className="form-group">
            <label>{t('projects.createModal.name')}</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('projects.createModal.namePlaceholder')} required autoFocus />
          </div>
          <div className="form-group">
            <label>{t('projects.createModal.description')}</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
              placeholder={t('projects.createModal.descriptionPlaceholder')} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
            <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>{t('common.cancel')}</button>
            <button type="submit" className="btn-primary" disabled={!name.trim() || createMut.isPending}>
              {createMut.isPending ? <Spinner size={14} /> : t('common.create')}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={showSamples} onClose={() => setShowSamples(false)} title={t('demo.samplesTitle')}>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 13, marginBottom: 16 }}>{t('demo.samplesSubtitle')}</p>
        {!sampleFiles?.length ? (
          <Spinner size={20} />
        ) : (
          <div style={{ display: 'grid', gap: 10 }}>
            {sampleFiles.map((sf: SampleFileInfo) => (
              <div key={sf.name} className="card" style={{ padding: '12px 16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{sf.name}</div>
                    <div style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{sf.description}</div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 2 }}>
                      {sf.format.toUpperCase()} &middot; {sf.size_hint}
                    </div>
                  </div>
                  <a
                    href={`${resolveBaseURL()}${sf.download_url}`}
                    download={sf.name}
                    className="btn-primary"
                    style={{ fontSize: 12, padding: '4px 12px', whiteSpace: 'nowrap' }}
                  >
                    <Download size={13} style={{ marginInlineEnd: 4, verticalAlign: -2 }} />
                    {t('demo.download')}
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </>
  );
}
