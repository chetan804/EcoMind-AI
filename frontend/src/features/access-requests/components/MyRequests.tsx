import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatDateTime, humanize } from '@/utils/format';
import { STATUS_TONE } from '../status-tone';
import { useMyRequests, useRequestChanges } from '../hooks/useAccessRequests';

/** The person's own requests with their state; a pending one can be withdrawn. */
export function MyRequests() {
  const query = useMyRequests();
  const { withdraw } = useRequestChanges();
  return (
    <QueryBoundary query={query} label="your role requests">
      {(rows) =>
        rows.length === 0 ? (
          <EmptyState title="No role requests yet" description="Requests you send appear here with the administrator's decision." />
        ) : (
          <ul className="access-list">
            {rows.map((r) => (
              <li key={r.id} className="access-list__item">
                <div>
                  <strong>{humanize(r.requested_role)}</strong> <Badge tone={STATUS_TONE[r.status]} dot>{humanize(r.status)}</Badge>
                  <p className="muted">Sent {formatDateTime(r.created_at)}{r.decided_at ? ` · decided ${formatDateTime(r.decided_at)}` : ''}</p>
                  {r.decision_note && <p>Administrator note: {r.decision_note}</p>}
                </div>
                {r.status === 'pending' && (
                  <Button variant="secondary" loading={withdraw.isPending} onClick={() => withdraw.mutate(r.id)} aria-label={`Withdraw request for ${humanize(r.requested_role)}`}>
                    Withdraw
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )
      }
    </QueryBoundary>
  );
}
