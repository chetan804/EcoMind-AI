import { useState } from 'react';
import { Gift } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { useFields } from '@/components/forms/useFields';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, SearchInput, Select, Textarea } from '@/components/ui/Input';
import { ReasonDialog } from '@/components/ui/ReasonDialog';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { getErrorMessage } from '@/services/error-handler';
import { formatDateTime, formatNumber, humanize } from '@/utils/format';
import { REDEMPTION_STATUSES, type ItemInput, type Redemption, type RewardItem } from '../api/rewards-api';
import { useCancelRedemption, useCreateItem, useFulfil, useItems, useRedemptionQueue, useUpdateItem } from '../hooks/useRewards';
import { REDEMPTION_TONES } from './tones';
import '../rewards.css';

const pageCount = (d: { total: number; page_size: number }) => Math.max(1, Math.ceil(d.total / d.page_size));
const MAX_COST = 1_000_000;

/** `datetime-local` has no zone; the API insists on one, so the browser's zone is made explicit. */
const toLocalInput = (iso: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const wholeOrNull = (text: string) => (text.trim() === '' ? null : Number(text));
const validWhole = (text: string, min: number, max: number) => text.trim() === '' || (/^\d+$/.test(text.trim()) && Number(text) >= min && Number(text) <= max);

export function ItemsTab() {
  const [pageNo, setPage] = useState(1);
  const [editing, setEditing] = useState<RewardItem | 'new' | null>(null);
  const query = useItems(pageNo);
  const update = useUpdateItem();
  return (
    <div className="stack stack--tight">
      <p className="muted">The platform ships no rewards. Add what your organisation actually offers; citizens can redeem only active, unexpired items. Items are never deleted: switch one off instead.</p>
      <div className="filter-bar"><Button onClick={() => setEditing('new')}>New reward</Button></div>
      {update.isError && <Alert tone="danger">{getErrorMessage(update.error)}</Alert>}
      <QueryBoundary query={query} label="the reward items">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<Gift size={28} />} title="No rewards yet" description="Add the first reward to let citizens spend their points." />
          ) : (
            <>
              <Table caption="Reward items">
                <thead>
                  <tr>
                    <th scope="col">Reward</th>
                    <th scope="col">Cost</th>
                    <th scope="col">Stock</th>
                    <th scope="col">Per person</th>
                    <th scope="col">Valid until</th>
                    <th scope="col">Redeemed</th>
                    <th scope="col">Status</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((i) => (
                    <tr key={i.id}>
                      <td>{i.name}</td>
                      <td>{formatNumber(i.points_cost)}</td>
                      <td>{i.stock === null ? 'Unlimited' : formatNumber(i.stock)}</td>
                      <td>{i.max_per_user ?? 'No limit'}</td>
                      <td>{i.valid_until ? formatDateTime(i.valid_until) : '—'}</td>
                      <td>{i.redeemed_count} ({i.pending_count} waiting)</td>
                      <td><Badge tone={i.active ? 'success' : 'neutral'}>{i.active ? 'Active' : 'Off'}</Badge></td>
                      <td>
                        <div className="listing__actions">
                          <Button variant="secondary" onClick={() => setEditing(i)} aria-label={`Edit ${i.name}`}>Edit</Button>
                          <Button variant="secondary" loading={update.isPending && update.variables?.id === i.id} onClick={() => update.mutate({ id: i.id, body: { active: !i.active } })} aria-label={`${i.active ? 'Switch off' : 'Switch on'} ${i.name}`}>
                            {i.active ? 'Switch off' : 'Switch on'}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={data.page} pageCount={pageCount(data)} onPageChange={setPage} summary={`${data.total} rewards`} />
            </>
          )
        }
      </QueryBoundary>
      {editing && <ItemDialog item={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function ItemDialog({ item, onClose }: { item: RewardItem | null; onClose: () => void }) {
  const create = useCreateItem();
  const update = useUpdateItem();
  const mutation = item ? update : create;
  const { values, bind } = useFields({
    name: item?.name ?? '',
    description: item?.description ?? '',
    points_cost: item ? String(item.points_cost) : '',
    stock: item?.stock == null ? '' : String(item.stock),
    max_per_user: item?.max_per_user == null ? '' : String(item.max_per_user),
    valid_until: toLocalInput(item?.valid_until ?? null),
  });
  const costOk = /^\d+$/.test(values.points_cost.trim()) && Number(values.points_cost) >= 1 && Number(values.points_cost) <= MAX_COST;
  const stockOk = validWhole(values.stock, 0, 1_000_000);
  const limitOk = validWhole(values.max_per_user, 1, 1000);
  const nameOk = values.name.trim().length >= 3;
  const dateOk = values.valid_until === '' || !Number.isNaN(new Date(values.valid_until).getTime());
  const valid = nameOk && costOk && stockOk && limitOk && dateOk;
  const body: ItemInput = {
    name: values.name.trim(),
    description: values.description.trim() || null,
    points_cost: Number(values.points_cost),
    stock: wholeOrNull(values.stock),
    max_per_user: wholeOrNull(values.max_per_user),
    valid_until: values.valid_until ? new Date(values.valid_until).toISOString() : null,
  };
  const submit = () => (item ? update.mutate({ id: item.id, body }, { onSuccess: onClose }) : create.mutate({ ...body, active: true }, { onSuccess: onClose }));
  return (
    <Dialog
      open
      onClose={onClose}
      title={item ? `Edit ${item.name}` : 'New reward'}
      description="Changing the cost does not affect redemptions that already happened."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={mutation.isPending} disabled={!valid} onClick={submit}>{item ? 'Save changes' : 'Add reward'}</Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Name" error={values.name !== '' && !nameOk ? 'At least 3 characters.' : undefined}>{(c) => <Input {...c} data-autofocus maxLength={120} {...bind('name')} />}</Field>
        <Field label="Description (optional)">{(c) => <Textarea {...c} maxLength={1000} {...bind('description')} />}</Field>
        <Field label="Cost in points" error={values.points_cost !== '' && !costOk ? `A whole number from 1 to ${formatNumber(MAX_COST)}.` : undefined}>{(c) => <Input {...c} inputMode="numeric" {...bind('points_cost')} />}</Field>
        <Field label="Units in stock (leave empty for unlimited)" error={!stockOk ? 'A whole number, or empty.' : undefined}>{(c) => <Input {...c} inputMode="numeric" {...bind('stock')} />}</Field>
        <Field label="Limit per person (leave empty for none)" error={!limitOk ? 'A whole number from 1 to 1,000, or empty.' : undefined}>{(c) => <Input {...c} inputMode="numeric" {...bind('max_per_user')} />}</Field>
        <Field label="Available until (optional)" hint="In your local time zone.">{(c) => <Input {...c} type="datetime-local" {...bind('valid_until')} />}</Field>
        {mutation.isError && <Alert tone="danger">{getErrorMessage(mutation.error)}</Alert>}
      </div>
    </Dialog>
  );
}

export function QueueTab() {
  const [filters, setFilters] = useState({ page: 1, status: 'pending', code: '' });
  const [fulfilling, setFulfilling] = useState<Redemption | null>(null);
  const [cancelling, setCancelling] = useState<Redemption | null>(null);
  const query = useRedemptionQueue(filters);
  const fulfil = useFulfil();
  const cancel = useCancelRedemption();
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  return (
    <div className="stack stack--tight">
      <div className="filter-bar">
        <Field label="Status">
          {(c) => (
            <Select {...c} value={filters.status} onChange={(e) => set({ status: e.target.value })}>
              <option value="">All</option>
              {REDEMPTION_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Claim code">{(c) => <SearchInput {...c} placeholder="K7M2P-9XQ4T" value={filters.code} onChange={(e) => set({ code: e.target.value })} />}</Field>
      </div>
      <QueryBoundary query={query} label="the redemptions">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState title="Nothing to hand over" description={filters.status === 'pending' && !filters.code ? 'Redemptions waiting for a hand-over appear here.' : 'No redemption matches these filters.'} />
          ) : (
            <>
              <Table caption="Redemptions">
                <thead>
                  <tr>
                    <th scope="col">Claim code</th>
                    <th scope="col">Reward</th>
                    <th scope="col">Citizen</th>
                    <th scope="col">Points</th>
                    <th scope="col">Status</th>
                    <th scope="col">Requested</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.id}>
                      <td><code>{r.code}</code></td>
                      <td>{r.item_name}</td>
                      <td>{r.user_name ?? '—'}<div className="muted">{r.user_email}</div></td>
                      <td>{formatNumber(r.points_spent)}</td>
                      <td>
                        <StatusBadge value={r.status} tones={REDEMPTION_TONES} />
                        {r.note && <div className="muted">{r.note}</div>}
                        {r.cancel_reason && <div className="muted">{r.cancel_reason}</div>}
                      </td>
                      <td>{formatDateTime(r.created_at)}</td>
                      <td>
                        {r.status === 'pending' && (
                          <div className="listing__actions">
                            <Button onClick={() => setFulfilling(r)} aria-label={`Mark ${r.code} handed over`}>Hand over</Button>
                            <Button variant="secondary" onClick={() => setCancelling(r)} aria-label={`Cancel ${r.code}`}>Cancel</Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={data.page} pageCount={pageCount(data)} onPageChange={(page) => setFilters((f) => ({ ...f, page }))} summary={`${data.total} redemptions`} />
            </>
          )
        }
      </QueryBoundary>
      {fulfilling && (
        <ReasonDialog
          title={`Hand over ${fulfilling.item_name}`}
          description={`Check the claim code ${fulfilling.code} with ${fulfilling.user_name ?? 'the citizen'}. This cannot be undone.`}
          label="Note"
          required={false}
          submitLabel="Mark as handed over"
          pending={fulfil.isPending}
          error={fulfil.error}
          onSubmit={(note) => fulfil.mutate({ id: fulfilling.id, note: note || undefined }, { onSuccess: () => setFulfilling(null) })}
          onClose={() => { setFulfilling(null); fulfil.reset(); }}
        />
      )}
      {cancelling && (
        <ReasonDialog
          title={`Cancel ${cancelling.item_name}`}
          description={`${formatNumber(cancelling.points_spent)} points go back to ${cancelling.user_name ?? 'the citizen'} and the unit returns to stock. They are told why.`}
          submitLabel="Cancel redemption"
          destructive
          pending={cancel.isPending}
          error={cancel.error}
          onSubmit={(reason) => cancel.mutate({ id: cancelling.id, reason }, { onSuccess: () => setCancelling(null) })}
          onClose={() => { setCancelling(null); cancel.reset(); }}
        />
      )}
    </div>
  );
}
