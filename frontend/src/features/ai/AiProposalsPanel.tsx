import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Sparkles,
  CheckCircle2,
  XCircle,
  Pencil,
  Clock,
  BrainCircuit,
  AlertTriangle,
} from 'lucide-react';
import { getAiStatus, runEnrichment, listProposals, decideProposal } from '../../shared/api/ai';
import { useI18n } from '../../shared/i18n';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';
import type { AiProposal, AiEnrichmentRequest } from '../../shared/api/types';

type Scope = 'all' | 'missing_only' | 'low_confidence';

interface Props {
  projectId: string;
  revisionId: string;
}

export default function AiProposalsPanel({ projectId, revisionId }: Props) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<Scope>('all');

  const statusQuery = useQuery({
    queryKey: ['aiStatus'],
    queryFn: getAiStatus,
    staleTime: 60_000,
  });

  const proposalsQuery = useQuery({
    queryKey: ['aiProposals', projectId, revisionId],
    queryFn: () => listProposals(projectId, revisionId),
    enabled: !!projectId && !!revisionId,
    refetchInterval: 15_000,
  });

  const enrichMutation = useMutation({
    mutationFn: (req: AiEnrichmentRequest) => runEnrichment(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['aiProposals', projectId, revisionId] });
    },
  });

  const decideMutation = useMutation({
    mutationFn: ({
      proposalId,
      decision,
    }: {
      proposalId: string;
      decision: 'accepted' | 'rejected';
    }) =>
      decideProposal(projectId, revisionId, proposalId, {
        decision,
        user: 'user',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['aiProposals', projectId, revisionId] });
    },
  });

  const aiAvailable = statusQuery.data?.available ?? false;
  const proposals = proposalsQuery.data ?? [];
  const pendingCount = proposals.filter((p) => p.status === 'pending').length;

  return (
    <div style={{ marginTop: 32 }}>
      <div
        className="page-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <BrainCircuit size={22} color="var(--color-primary)" />
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>{t('ai.proposals')}</h2>
            <p style={{ color: 'var(--color-text-dim)', fontSize: 13, margin: 0 }}>
              {t('ai.proposalsSubtitle')}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as Scope)}
            style={{
              padding: '6px 10px',
              fontSize: 13,
              borderRadius: 6,
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
            }}
          >
            <option value="all">{t('ai.scopeAll')}</option>
            <option value="missing_only">{t('ai.scopeMissing')}</option>
            <option value="low_confidence">{t('ai.scopeLowConf')}</option>
          </select>

          <button
            className="btn-primary"
            disabled={!aiAvailable || enrichMutation.isPending}
            onClick={() =>
              enrichMutation.mutate({
                project_id: projectId,
                revision_id: revisionId,
                scope,
              })
            }
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 13,
            }}
          >
            {enrichMutation.isPending ? (
              <>
                <Spinner size={14} /> {t('ai.enriching')}
              </>
            ) : (
              <>
                <Sparkles size={14} /> {t('ai.enrichButton')}
              </>
            )}
          </button>
        </div>
      </div>

      {!aiAvailable && !statusQuery.isLoading && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 16px',
            background: 'rgba(245,158,11,.1)',
            borderRadius: 8,
            fontSize: 13,
            color: 'var(--color-warning)',
            marginBottom: 16,
          }}
        >
          <AlertTriangle size={16} />
          {t('ai.notConfigured')}
        </div>
      )}

      {enrichMutation.isError && (
        <div
          style={{
            padding: '10px 16px',
            background: 'rgba(239,68,68,.1)',
            borderRadius: 8,
            fontSize: 13,
            color: 'var(--color-error)',
            marginBottom: 16,
          }}
        >
          {t('ai.enrichError')}
        </div>
      )}

      {enrichMutation.isSuccess && enrichMutation.data.length === 0 && (
        <div
          style={{
            padding: '10px 16px',
            background: 'rgba(59,130,246,.08)',
            borderRadius: 8,
            fontSize: 13,
            color: 'var(--color-primary)',
            marginBottom: 16,
          }}
        >
          {t('ai.enrichEmpty')}
        </div>
      )}

      {proposalsQuery.isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
          <Spinner size={24} />
        </div>
      ) : proposals.length === 0 ? (
        <EmptyState icon={<Sparkles size={48} />} message={t('ai.noProposals')} />
      ) : (
        <>
          {pendingCount > 0 && (
            <div style={{ marginBottom: 12 }}>
              <span
                className="badge"
                style={{
                  background: 'var(--color-primary)',
                  color: '#fff',
                  fontSize: 12,
                  padding: '4px 10px',
                }}
              >
                {t('ai.enrichComplete', { count: String(pendingCount) })}
              </span>
            </div>
          )}

          <div className="card" style={{ padding: 0 }}>
            <div className="table-responsive">
              <table>
                <thead>
                  <tr>
                    <th>{t('ai.category')}</th>
                    <th>{t('ai.label')}</th>
                    <th>{t('ai.value')}</th>
                    <th>{t('ai.unit')}</th>
                    <th>{t('ai.confidence')}</th>
                    <th>{t('ai.sourceDocument')}</th>
                    <th>{t('ai.status')}</th>
                    <th>{t('ai.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {proposals.map((p) => (
                    <ProposalRow
                      key={p.proposal_id}
                      proposal={p}
                      t={t}
                      onDecide={(decision) =>
                        decideMutation.mutate({ proposalId: p.proposal_id, decision })
                      }
                      isDeciding={decideMutation.isPending}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ProposalRow({
  proposal,
  t,
  onDecide,
  isDeciding,
}: {
  proposal: AiProposal;
  t: (key: string, params?: Record<string, string>) => string;
  onDecide: (decision: 'accepted' | 'rejected') => void;
  isDeciding: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const isPending = proposal.status === 'pending';

  return (
    <>
      <tr
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded(!expanded)}
      >
        <td>
          <span className="badge badge-info" style={{ fontSize: 11 }}>
            {proposal.category}
          </span>
        </td>
        <td style={{ fontSize: 13, maxWidth: 200 }}>{proposal.label}</td>
        <td style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          {proposal.edited_value != null
            ? String(proposal.edited_value)
            : proposal.value != null
              ? String(proposal.value)
              : '\u2014'}
        </td>
        <td style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>{proposal.unit}</td>
        <td>
          <ConfidencePill value={proposal.confidence} />
        </td>
        <td
          style={{
            fontSize: 12,
            maxWidth: 150,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            color: 'var(--color-text-dim)',
          }}
        >
          {proposal.source_document || '\u2014'}
        </td>
        <td>
          <ProposalStatusBadge status={proposal.status} t={t} />
        </td>
        <td>
          {isPending ? (
            <div style={{ display: 'flex', gap: 6 }} onClick={(e) => e.stopPropagation()}>
              <button
                className="btn-primary btn-sm"
                onClick={() => onDecide('accepted')}
                disabled={isDeciding}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  fontSize: 12,
                }}
              >
                <CheckCircle2 size={12} /> {t('ai.accept')}
              </button>
              <button
                className="btn-secondary btn-sm"
                onClick={() => onDecide('rejected')}
                disabled={isDeciding}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  fontSize: 12,
                }}
              >
                <XCircle size={12} /> {t('ai.reject')}
              </button>
            </div>
          ) : (
            <span style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>
              {proposal.decided_by && `${t('ai.decidedBy')}: ${proposal.decided_by}`}
            </span>
          )}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={8} style={{ background: 'var(--color-surface)', padding: 16 }}>
            <div style={{ display: 'grid', gap: 8, fontSize: 13 }}>
              <div>
                <strong>{t('ai.reasoning')}:</strong>
                <p style={{ margin: '4px 0 0', color: 'var(--color-text-dim)' }}>
                  {proposal.reasoning || proposal.source_snippet || '\u2014'}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                <span>
                  <strong>{t('ai.modelVersion')}:</strong>{' '}
                  <code style={{ fontSize: 12 }}>{proposal.model_version}</code>
                </span>
                {proposal.decided_at && (
                  <span>
                    <strong>{t('ai.decidedBy')}:</strong> {proposal.decided_by} (
                    {new Date(proposal.decided_at).toLocaleString()})
                  </span>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function ProposalStatusBadge({
  status,
  t,
}: {
  status: string;
  t: (key: string) => string;
}) {
  switch (status) {
    case 'accepted':
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            color: 'var(--color-success)',
            fontSize: 12,
          }}
        >
          <CheckCircle2 size={14} /> {t('ai.accepted')}
        </span>
      );
    case 'rejected':
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            color: 'var(--color-error)',
            fontSize: 12,
          }}
        >
          <XCircle size={14} /> {t('ai.rejected')}
        </span>
      );
    case 'edited':
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            color: 'var(--color-primary)',
            fontSize: 12,
          }}
        >
          <Pencil size={14} /> {t('ai.edited')}
        </span>
      );
    default:
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            color: 'var(--color-warning)',
            fontSize: 12,
          }}
        >
          <Clock size={14} /> {t('ai.pending')}
        </span>
      );
  }
}

function ConfidencePill({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 75
      ? 'var(--color-success)'
      : pct >= 40
        ? 'var(--color-warning)'
        : 'var(--color-error)';
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontSize: 12,
        fontFamily: 'var(--font-mono)',
        color,
      }}
    >
      {pct}%
    </span>
  );
}
