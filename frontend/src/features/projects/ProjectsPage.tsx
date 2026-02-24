import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FolderKanban, Plus } from 'lucide-react';
import { listProjects, createProject } from '../../shared/api/projects';
import { useToast } from '../../shared/components/Toast';
import Modal from '../../shared/components/Modal';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showError, showSuccess } = useToast();
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
      showSuccess(`Project "${proj.name}" created`);
      setShowCreate(false);
      setName('');
      setDescription('');
      navigate(`/projects/${proj.project_id}`);
    },
    onError: () => showError('Failed to create project'),
  });

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}><Spinner size={32} /></div>;
  }

  return (
    <>
      <div className="page-header">
        <h1>Projects</h1>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} style={{ marginRight: 6, verticalAlign: -3 }} />
          New Project
        </button>
      </div>

      {!projects?.length ? (
        <EmptyState
          icon={<FolderKanban size={48} />}
          message="No projects yet. Create your first project to get started."
          action={<button className="btn-primary" onClick={() => setShowCreate(true)}>Create Project</button>}
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
                Created {new Date(p.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create Project">
        <form onSubmit={(e) => { e.preventDefault(); createMut.mutate(); }}>
          <div className="form-group">
            <label>Project Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Tel Aviv Tower" required autoFocus />
          </div>
          <div className="form-group">
            <label>Description (optional)</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
              placeholder="Brief description of the project..." />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
            <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={!name.trim() || createMut.isPending}>
              {createMut.isPending ? <Spinner size={14} /> : 'Create'}
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
