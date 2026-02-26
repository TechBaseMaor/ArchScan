import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Upload, FileText, Clock, Eye } from 'lucide-react';
import { getProject, listRevisions, getProjectHistory } from '../../shared/api/projects';
import { useI18n } from '../../shared/i18n';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { t, formatDateTime } = useI18n();

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
    return <EmptyState icon={<FileText size={48} />} message={t('projectDetail.notFound')} />;
  }

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link to="/advanced" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--color-text-dim)' }}>
          <ArrowLeft size={14} /> {t('projectDetail.backToProjects')}
        </Link>
      </div>

      <div className="page-header">
        <div>
          <h1>{project.name}</h1>
          {project.description && <p style={{ color: 'var(--color-text-dim)', fontSize: 14, marginTop: 4 }}>{project.description}</p>}
        </div>
        <button className="btn-primary" onClick={() => navigate(`/advanced/projects/${projectId}/validate`)}>
          <Upload size={16} style={{ marginInlineEnd: 6, verticalAlign: -3 }} />
          {t('projectDetail.uploadValidate')}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 24 }}>
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileText size={16} /> {t('projectDetail.revisions')} ({revisions?.length ?? 0})
          </h3>
          {!revisions?.length ? (
            <p style={{ color: 'var(--color-text-dim)', fontSize: 13 }}>{t('projectDetail.noRevisions')}</p>
          ) : (
            <div className="table-responsive">
              <table>
                <thead>
                  <tr><th>{t('projectDetail.revision')}</th><th>{t('projectDetail.files')}</th><th>{t('common.date')}</th><th></th></tr>
                </thead>
                <tbody>
                  {revisions.map((r) => (
                    <tr key={r.revision_id}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{r.revision_id}</td>
                      <td>
                        {r.sources.map((s) => (
                          <span key={s.source_hash} className="badge badge-info" style={{ marginInlineEnd: 4 }}>
                            {s.file_name}
                          </span>
                        ))}
                      </td>
                      <td style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{formatDateTime(r.created_at)}</td>
                      <td>
                        <Link
                          to={`/advanced/projects/${projectId}/revisions/${r.revision_id}/insights`}
                          className="btn-primary"
                          style={{ fontSize: 12, padding: '4px 10px', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                        >
                          <Eye size={13} /> {t('insights.viewInsights')}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Clock size={16} /> {t('projectDetail.validationHistory')}
          </h3>
          {!history?.length ? (
            <p style={{ color: 'var(--color-text-dim)', fontSize: 13 }}>{t('projectDetail.noValidations')}</p>
          ) : (
            <div className="table-responsive">
              <table>
                <thead>
                  <tr><th>{t('projectDetail.revision')}</th><th>{t('projectDetail.sources')}</th><th>{t('projectDetail.validations')}</th><th>{t('common.date')}</th></tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.revision_id}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{h.revision_id.slice(0, 8)}</td>
                      <td>{h.source_count}</td>
                      <td>{h.validation_count}</td>
                      <td style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{formatDateTime(h.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
