import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, BookOpen, Scale } from 'lucide-react';
import { getRuleset } from '../../shared/api/rulesets';
import Spinner from '../../shared/components/Spinner';
import StatusBadge from '../../shared/components/StatusBadge';
import EmptyState from '../../shared/components/EmptyState';

export default function RulesetDetailPage() {
  const { rulesetId } = useParams<{ rulesetId: string }>();

  const { data: ruleset, isLoading } = useQuery({
    queryKey: ['ruleset', rulesetId],
    queryFn: () => getRuleset(rulesetId!),
    enabled: !!rulesetId,
  });

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}><Spinner size={32} /></div>;
  }

  if (!ruleset) {
    return <EmptyState icon={<BookOpen size={48} />} message="Ruleset not found." />;
  }

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Link to="/rulesets" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--color-text-dim)' }}>
          <ArrowLeft size={14} /> Back to Rulesets
        </Link>
      </div>

      <div className="page-header">
        <div>
          <h1>{ruleset.name}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6, fontSize: 13, color: 'var(--color-text-dim)' }}>
            <span className="badge badge-info">v{ruleset.version}</span>
            <span>{ruleset.jurisdiction}</span>
            <span>Effective: {ruleset.effective_date}</span>
            <span>{ruleset.rules.length} rules</span>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr><th>Rule ID</th><th>Version</th><th>Severity</th><th>Description</th><th>Formula</th></tr>
          </thead>
          <tbody>
            {ruleset.rules.map((r) => (
              <tr key={`${r.rule_id}:${r.version}`}>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{r.rule_id}</td>
                <td>{r.version}</td>
                <td><StatusBadge status={r.severity} /></td>
                <td style={{ fontSize: 13, maxWidth: 300 }}>{r.description || '-'}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{r.computation.formula}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Scale size={16} /> Raw JSON
        </h3>
        <pre style={{
          background: 'var(--color-surface-2)', padding: 16, borderRadius: 'var(--radius)',
          fontSize: 12, fontFamily: 'var(--font-mono)', overflow: 'auto', maxHeight: 400,
        }}>
          {JSON.stringify(ruleset, null, 2)}
        </pre>
      </div>
    </>
  );
}
