import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Upload, FileText, Clock } from 'lucide-react';
import { getProject, listRevisions, getProjectHistory } from '../../shared/api/projects';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const { data: project, isLoading: loadingProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId!),
    enabled: !!projectId,
  });

  const { data: revisions } = useQuery({
    queryKey: ['revisions', projectId],
    queryFn: () => listRevisions(projectId!),
    enabled: !!projectId,
  });

  const { data: history } = useQuery({
    queryKey: ['history', projectId],
    queryFn: () => getProjectHistory(projectId!),
    enabled: !!projectId,
  });

  if (loadingProject) {
    return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}><Spinner size={32} /></div>;
  }

  if (!project) {
    return <EmptyState icon={<FileText size={48} />} message="Project not found." />;
  }

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link to="/" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--color-text-dim)' }}>
          <ArrowLeft size={14} /> Back to Projects
        </Link>
      </div>

      <div className="page-header">
        <div>
          <h1>{project.name}</h1>
          {project.description && <p style={{ color: 'var(--color-text-dim)', fontSize: 14, marginTop: 4 }}>{project.description}</p>}
        </div>
        <button className="btn-primary" onClick={() => navigate(`/projects/${projectId}/validate`)}>
          <Upload size={16} style={{ marginRight: 6, verticalAlign: -3 }} />
          Upload &amp; Validate
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Revisions */}
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileText size={16} /> Revisions ({revisions?.length ?? 0})
          </h3>
          {!revisions?.length ? (
            <p style={{ color: 'var(--color-text-dim)', fontSize: 13 }}>No revisions yet. Upload files to create one.</p>
          ) : (
            <table>
              <thead>
                <tr><th>Revision</th><th>Files</th><th>Date</th></tr>
              </thead>
              <tbody>
                {revisions.map((r) => (
                  <tr key={r.revision_id}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{r.revision_id}</td>
                    <td>
                      {r.sources.map((s) => (
                        <span key={s.source_hash} className="badge badge-info" style={{ marginRight: 4 }}>
                          {s.file_name}
                        </span>
                      ))}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{new Date(r.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* History */}
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Clock size={16} /> Validation History
          </h3>
          {!history?.length ? (
            <p style={{ color: 'var(--color-text-dim)', fontSize: 13 }}>No validation runs yet.</p>
          ) : (
            <table>
              <thead>
                <tr><th>Revision</th><th>Sources</th><th>Validations</th><th>Date</th></tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.revision_id}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{h.revision_id.slice(0, 8)}</td>
                    <td>{h.source_count}</td>
                    <td>{h.validation_count}</td>
                    <td style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{new Date(h.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
