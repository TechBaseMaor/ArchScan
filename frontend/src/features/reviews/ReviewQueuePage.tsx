import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Clock,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { listReviewItems, decideReview } from '../../shared/api/validations';
import { useI18n } from '../../shared/i18n';
import Spinner from '../../shared/components/Spinner';
import EmptyState from '../../shared/components/EmptyState';
import type { ReviewItem } from '../../shared/api/types';

type Filter = 'all' | 'pending' | 'resolved';

export default function ReviewQueuePage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>('all');

  const { data: items, isLoading } = useQuery({
    queryKey: ['reviewItems'],
    queryFn: () => listReviewItems(),
    refetchInterval: 10_000,
  });

  const decideMutation = useMutation({
    mutationFn: ({ reviewId, decision }: { reviewId: string; decision: 'approved' | 'rejected' }) =>
      decideReview(reviewId, decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reviewItems'] }),
  });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <Spinner size={32} />
      </div>
    );
  }

  const allItems = items ?? [];
  const filtered =
    filter === 'pending'
      ? allItems.filter((i) => i.status === 'pending_review')
      : filter === 'resolved'
        ? allItems.filter((i) => i.status === 'approved' || i.status === 'rejected' || i.status === 'auto_approved')
        : allItems;

  const pendingCount = allItems.filter((i) => i.status === 'pending_review').length;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>{t('reviews.title')}</h1>
          <p style={{ color: 'var(--color-text-dim)', fontSize: 14, marginTop: 4 }}>
            {t('reviews.subtitle')}
          </p>
        </div>
        {pendingCount > 0 && (
          <span
            className="badge"
            style={{
              background: 'var(--color-warning)',
              color: '#000',
              fontSize: 12,
              padding: '4px 10px',
            }}
          >
            {t('reviews.pendingCount', { count: String(pendingCount) })}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['all', 'pending', 'resolved'] as Filter[]).map((f) => (
          <button
            key={f}
            className={filter === f ? 'btn-primary btn-sm' : 'btn-secondary btn-sm'}
            onClick={() => setFilter(f)}
          >
            {t(`reviews.filter${f.charAt(0).toUpperCase() + f.slice(1)}`)}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon={<ShieldCheck size={48} />} message={t('reviews.empty')} />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>{t('reviews.fileName')}</th>
                  <th>{t('reviews.reviewType')}</th>
                  <th>{t('reviews.reason')}</th>
                  <th>{t('reviews.confidence')}</th>
                  <th>{t('reviews.status')}</th>
                  <th>{t('reviews.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <ReviewRow
                    key={item.review_id}
                    item={item}
                    t={t}
                    onDecide={(decision) =>
                      decideMutation.mutate({ reviewId: item.review_id, decision })
                    }
                    isDeciding={decideMutation.isPending}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function ReviewRow({
  item,
  t,
  onDecide,
  isDeciding,
}: {
  item: ReviewItem;
  t: (key: string, params?: Record<string, string>) => string;
  onDecide: (decision: 'approved' | 'rejected') => void;
  isDeciding: boolean;
}) {
  const isPending = item.status === 'pending_review';

  return (
    <tr>
      <td style={{ fontSize: 13, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {item.file_name || '\u2014'}
      </td>
      <td>
        <span className="badge badge-info" style={{ fontSize: 11 }}>
          {item.review_type}
        </span>
      </td>
      <td style={{ fontSize: 12, color: 'var(--color-text-dim)', maxWidth: 300 }}>
        {item.reason}
      </td>
      <td>
        <ConfidencePill value={item.confidence} />
      </td>
      <td>
        <StatusIcon status={item.status} t={t} />
      </td>
      <td>
        {isPending ? (
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              className="btn-primary btn-sm"
              onClick={() => onDecide('approved')}
              disabled={isDeciding}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}
            >
              <CheckCircle2 size={12} /> {t('reviews.approve')}
            </button>
            <button
              className="btn-secondary btn-sm"
              onClick={() => onDecide('rejected')}
              disabled={isDeciding}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}
            >
              <XCircle size={12} /> {t('reviews.reject')}
            </button>
          </div>
        ) : (
          <span style={{ fontSize: 12, color: 'var(--color-text-dim)' }}>
            {item.reviewer && `${t('reviews.decidedBy')}: ${item.reviewer}`}
          </span>
        )}
      </td>
    </tr>
  );
}

function StatusIcon({
  status,
  t,
}: {
  status: string;
  t: (key: string) => string;
}) {
  switch (status) {
    case 'approved':
    case 'auto_approved':
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--color-success)', fontSize: 12 }}>
          <ShieldCheck size={14} /> {t('reviews.approved')}
        </span>
      );
    case 'rejected':
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--color-error)', fontSize: 12 }}>
          <ShieldX size={14} /> {t('reviews.rejected')}
        </span>
      );
    case 'pending_review':
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--color-warning)', fontSize: 12 }}>
          <Clock size={14} /> {t('reviews.pending')}
        </span>
      );
    default:
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
          <ShieldAlert size={14} /> {status}
        </span>
      );
  }
}

function ConfidencePill({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 75 ? 'var(--color-success)' : pct >= 40 ? 'var(--color-warning)' : 'var(--color-error)';
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
