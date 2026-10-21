import { useState } from 'react';
import { Gift } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { ReasonDialog } from '@/components/ui/ReasonDialog';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { getErrorMessage } from '@/services/error-handler';
import { formatDate, formatDateTime, formatNumber } from '@/utils/format';
import type { CatalogItem, Redemption } from '../api/rewards-api';
import { useBalance, useCancelMine, useCatalog, useMyRedemptions, useRedeem } from '../hooks/useRewards';
import { REDEMPTION_TONES } from './tones';
import '../rewards.css';

const REASONS = { out_of_stock: 'Out of stock', limit_reached: 'You have reached the limit for this reward' } as const;
const pageCount = (d: { total: number; page_size: number }) => Math.max(1, Math.ceil(d.total / d.page_size));

/** What a citizen can spend points on. The catalogue is whatever staff entered; there is no built-in one. */
export function CatalogueTab() {
  const [pageNo, setPage] = useState(1);
  const [choice, setChoice] = useState<CatalogItem | null>(null);
  const catalog = useCatalog(pageNo);
  const balance = useBalance();
  const points = balance.data?.points;
  return (
    <div className="stack stack--tight">
      {points !== undefined && <p className="muted">You have <strong>{formatNumber(points)}</strong> points to spend.</p>}
      <QueryBoundary query={catalog} label="the rewards">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<Gift size={28} />} title="No rewards are on offer yet" description="Rewards are set up by the organisation running this platform. Check back later; your points are kept." />
          ) : (
            <>
              <ul className="reward-grid" aria-label="Rewards">
                {data.items.map((item) => (
                  <RewardCard key={item.id} item={item} points={points} onChoose={() => setChoice(item)} />
                ))}
              </ul>
              <Pagination page={data.page} pageCount={pageCount(data)} onPageChange={setPage} summary={`${data.total} rewards`} />
            </>
          )
        }
      </QueryBoundary>
      {choice && <RedeemDialog item={choice} points={points} onClose={() => setChoice(null)} />}
    </div>
  );
}

function RewardCard({ item, points, onChoose }: { item: CatalogItem; points: number | undefined; onChoose: () => void }) {
  const short = points !== undefined && points < item.points_cost ? item.points_cost - points : 0;
  const blocked = item.unavailable_reason ? REASONS[item.unavailable_reason] : short > 0 ? `${formatNumber(short)} more points needed` : null;
  return (
    <li className="reward">
      <h3 className="reward__title">{item.name}</h3>
      <span className="reward__cost">{formatNumber(item.points_cost)} points</span>
      {item.description && <p className="muted">{item.description}</p>}
      <div className="listing__meta">
        {item.stock_remaining !== null && item.stock_remaining > 0 && <Badge tone="info">{formatNumber(item.stock_remaining)} left</Badge>}
        {item.valid_until && <Badge tone="neutral">Until {formatDate(item.valid_until)}</Badge>}
        {item.remaining_for_you !== null && item.remaining_for_you > 0 && <Badge tone="neutral">{item.remaining_for_you} more for you</Badge>}
      </div>
      <div className="reward__actions">
        <Button onClick={onChoose} disabled={blocked !== null} aria-label={`Redeem ${item.name}`}>Redeem</Button>
        {blocked && <span className="muted">{blocked}</span>}
      </div>
    </li>
  );
}

function RedeemDialog({ item, points, onClose }: { item: CatalogItem; points: number | undefined; onClose: () => void }) {
  // One id per opening of the dialog: pressing again after a timeout repeats the same request.
  const [requestId] = useState(() => crypto.randomUUID());
  const redeem = useRedeem();
  const done = redeem.data;
  return (
    <Dialog
      open
      onClose={onClose}
      title={done ? 'Reward redeemed' : `Redeem ${item.name}`}
      description={done ? undefined : `This spends ${formatNumber(item.points_cost)} points.`}
      footer={
        done ? (
          <Button onClick={onClose}>Done</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button loading={redeem.isPending} onClick={() => redeem.mutate({ itemId: item.id, clientRequestId: requestId })}>
              {`Redeem for ${formatNumber(item.points_cost)} points`}
            </Button>
          </>
        )
      }
    >
      <div className="stack stack--tight">
        {done ? (
          <>
            <p>Show this claim code to collect <strong>{done.item_name}</strong>. It is also kept under My redemptions.</p>
            <code className="claim-code" aria-label="Claim code">{done.code}</code>
          </>
        ) : (
          <>
            {points !== undefined && <p className="muted">Balance after: {formatNumber(points - item.points_cost)} points.</p>}
            <p className="muted">You can cancel while the reward has not been handed over, and the points come back.</p>
          </>
        )}
        {redeem.isError && <Alert tone="danger">{getErrorMessage(redeem.error)}</Alert>}
      </div>
    </Dialog>
  );
}

/** A citizen's own redemptions, with the claim code and a way back while still pending. */
export function MyRedemptionsTab() {
  const [pageNo, setPage] = useState(1);
  const [cancelling, setCancelling] = useState<Redemption | null>(null);
  const query = useMyRedemptions(pageNo);
  const cancel = useCancelMine();
  return (
    <div className="stack stack--tight">
      <QueryBoundary query={query} label="your redemptions">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState title="Nothing redeemed yet" description="Rewards you redeem appear here with their claim code." />
          ) : (
            <>
              <Table caption="My redemptions">
                <thead>
                  <tr>
                    <th scope="col">Reward</th>
                    <th scope="col">Points</th>
                    <th scope="col">Claim code</th>
                    <th scope="col">Status</th>
                    <th scope="col">Requested</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.id}>
                      <td>{r.item_name}</td>
                      <td>{formatNumber(r.points_spent)}</td>
                      <td>{r.status === 'cancelled' ? '—' : <code>{r.code}</code>}</td>
                      <td>
                        <StatusBadge value={r.status} tones={REDEMPTION_TONES} />
                        {r.cancel_reason && <div className="muted">{r.cancel_reason}</div>}
                      </td>
                      <td>{formatDateTime(r.created_at)}</td>
                      <td>{r.status === 'pending' && <Button variant="secondary" onClick={() => setCancelling(r)} aria-label={`Cancel redemption of ${r.item_name}`}>Cancel</Button>}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={data.page} pageCount={pageCount(data)} onPageChange={setPage} summary={`${data.total} redemptions`} />
            </>
          )
        }
      </QueryBoundary>
      {cancelling && (
        <ReasonDialog
          title={`Cancel ${cancelling.item_name}`}
          description={`Your ${formatNumber(cancelling.points_spent)} points are returned.`}
          required={false}
          submitLabel="Cancel redemption"
          destructive
          pending={cancel.isPending}
          error={cancel.error}
          onSubmit={(reason) => cancel.mutate({ id: cancelling.id, reason: reason.trim() || undefined }, { onSuccess: () => setCancelling(null) })}
          onClose={() => { setCancelling(null); cancel.reset(); }}
        />
      )}
    </div>
  );
}
