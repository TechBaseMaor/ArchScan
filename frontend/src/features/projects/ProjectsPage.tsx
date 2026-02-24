import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FolderKanban, Plus } from 'lucide-react';
import { listProjects, createProject } from '../../shared/api/projects';
import { useToast } from '../../shared/components/Toast';
import { useI18n } from '../../shared/i18n';
import Modal from '../../shared/components/Modal';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showError, showSuccess } = useToast();
  const { t, formatDate } = useI18n();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
  });

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

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}><Spinner size={32} /></div>;
  }

  return (
    <>
      <div className="page-header">
        <h1>{t('projects.title')}</h1>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} style={{ marginInlineEnd: 6, verticalAlign: -3 }} />
          {t('projects.new')}
        </button>
      </div>

      {!projects?.length ? (
        <EmptyState
          icon={<FolderKanban size={48} />}
          message={t('projects.empty')}
          action={<button className="btn-primary" onClick={() => setShowCreate(true)}>{t('projects.createProject')}</button>}
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
    </>
  );
}
