import { useState } from 'react';
import { Award, Scale } from 'lucide-react';
import { MetricTile } from '@/components/data-display/MetricTile';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import type { BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, Select } from '@/components/ui/Input';
import { ReasonDialog } from '@/components/ui/ReasonDialog';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { Tabs } from '@/components/ui/Tabs';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDateTime, formatKg, formatNumber, humanize } from '@/utils/format';
import { ENTRY_TYPES, SOURCE_TYPES, type Entry } from '../api/rewards-api';
import { useAdjust, useBalance, useLedger, useLedgerSummary, useMyEntries, useReverse, useUserOptions } from '../hooks/useRewards';

const TONES: Record<string, BadgeTone> = { earned: 'success', redeemed: 'info', adjustment: 'warning', reversal: 'danger' };
const signed = (n: number) => (n > 0 ? `+${formatNumber(n)}` : formatNumber(n));

export function RewardsPage() {
  const { can } = useAuth();
  const mine = can('rewards:read_own');
  const manage = can('rewards:manage');
  const tabs = [
    ...(mine ? [{ id: 'mine', label: 'My points', panel: <MyPoints /> }] : []),
    ...(manage ? [{ id: 'ledger', label: 'Ledger', panel: <Ledger /> }] : []),
  ];
  return (
    <section aria-labelledby="rewards-title" className="stack stack--tight">
      <PageHeader title="Rewards and impact ledger" titleId="rewards-title" subtitle="Points are earned from verified collections and recorded in an append-only ledger. Points cannot be redeemed yet." />
      <Tabs label="Rewards views" items={tabs} />
    </section>
  );
}

function EntryTable({ entries, caption, onReverse }: { entries: Entry[]; caption: string; onReverse?: (e: Entry) => void }) {
  return (
    <Table caption={caption}>
      <thead>
        <tr>
          <th scope="col">When</th>
          <th scope="col">Type</th>
          <th scope="col">Points</th>
          <th scope="col">Weight</th>
          <th scope="col">Source</th>
          <th scope="col">Note</th>
          {onReverse && <th scope="col"><span className="visually-hidden">Actions</span></th>}
        </tr>
      </thead>
      <tbody>
        {entries.map((e) => (
          <tr key={e.id}>
            <td>{formatDateTime(e.created_at)}</td>
            <td><StatusBadge value={e.entry_type} tones={TONES} /></td>
            <td>{signed(e.points)}</td>
            <td>{e.impact_weight_kg === null ? '—' : formatKg(e.impact_weight_kg)}</td>
            <td>{humanize(e.source_type)}</td>
            <td>{e.description ?? '—'}</td>
            {onReverse && (
              <td>{e.entry_type === 'reversal' ? null : <Button variant="secondary" onClick={() => onReverse(e)} aria-label={`Reverse entry of ${signed(e.points)} points`}>Reverse</Button>}</td>
            )}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function MyPoints() {
  const [pageNo, setPage] = useState(1);
  const [type, setType] = useState('');
  const balance = useBalance();
  const entries = useMyEntries(pageNo, type);
  return (
    <div className="stack stack--tight">
      <QueryBoundary query={balance} label="your balance">
        {(b) => (
          <>
            <div className="grid-3">
              <MetricTile icon={<Award size={22} />} label="Points balance" value={formatNumber(b.points)} note={`${formatNumber(b.earned_points)} earned in total`} />
              <MetricTile icon={<Scale size={22} />} label="Verified weight collected" value={formatKg(b.impact_weight_kg)} note={`${b.entries} ledger entr${b.entries === 1 ? 'y' : 'ies'}`} />
            </div>
            <p className="muted">{b.basis ?? `Points are ${b.points_per_kg} per kilogram collected.`}</p>
          </>
        )}
      </QueryBoundary>
      <div className="filter-bar">
        <Field label="Entry type">
          {(c) => <Select {...c} value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}><option value="">All entries</option>{ENTRY_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</Select>}
        </Field>
      </div>
      <QueryBoundary query={entries} label="your entries">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState title="No points yet" description="Points appear after a collection task for one of your reports is completed with a weight." />
          ) : (
            <>
              <EntryTable entries={data.items} caption="My ledger entries" />
              <Pagination page={data.page} pageCount={Math.max(1, Math.ceil(data.total / data.page_size))} onPageChange={setPage} summary={`${data.total} entries`} />
            </>
          )
        }
      </QueryBoundary>
    </div>
  );
}

function Ledger() {
  const [filters, setFilters] = useState({ page: 1, entry_type: '', source_type: '' });
  const [adjusting, setAdjusting] = useState(false);
  const [reversing, setReversing] = useState<Entry | null>(null);
  const summary = useLedgerSummary();
  const query = useLedger(filters);
  const reverse = useReverse();
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  return (
    <div className="stack stack--tight">
      <QueryBoundary query={summary} label="the ledger summary">
        {(s) => (
          <>
            <div className="grid-3">
              <MetricTile icon={<Award size={22} />} label="Net points" value={formatNumber(s.net_points)} note={`${formatNumber(s.points_issued)} issued, ${formatNumber(s.points_removed)} removed`} />
              <MetricTile icon={<Scale size={22} />} label="Verified weight" value={formatKg(s.impact_weight_kg)} note={`${s.users} people, ${s.entries} entries`} />
            </div>
            {s.basis && <p className="muted">{s.basis}</p>}
          </>
        )}
      </QueryBoundary>
      <div className="filter-bar">
        <Field label="Entry type">
          {(c) => <Select {...c} value={filters.entry_type} onChange={(e) => set({ entry_type: e.target.value })}><option value="">All entries</option>{ENTRY_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</Select>}
        </Field>
        <Field label="Source">
          {(c) => <Select {...c} value={filters.source_type} onChange={(e) => set({ source_type: e.target.value })}><option value="">All sources</option>{SOURCE_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</Select>}
        </Field>
        <Button onClick={() => setAdjusting(true)}>Adjust points</Button>
      </div>
      <QueryBoundary query={query} label="the ledger">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState title="The ledger is empty" description="Entries appear when collections are completed or an adjustment is recorded." />
          ) : (
            <>
              <EntryTable entries={data.items} caption="Ledger entries" onReverse={setReversing} />
              <Pagination page={data.page} pageCount={Math.max(1, Math.ceil(data.total / data.page_size))} onPageChange={(page) => setFilters((f) => ({ ...f, page }))} summary={`${data.total} entries`} />
            </>
          )
        }
      </QueryBoundary>
      {adjusting && <AdjustDialog onClose={() => setAdjusting(false)} />}
      {reversing && (
        <ReasonDialog
          title="Reverse ledger entry"
          description="Adds an offsetting entry; the original stays in the ledger. The reason is recorded."
          submitLabel="Reverse entry"
          destructive
          pending={reverse.isPending}
          error={reverse.error}
          onSubmit={(reason) => reverse.mutate({ id: reversing.id, reason }, { onSuccess: () => setReversing(null) })}
          onClose={() => { setReversing(null); reverse.reset(); }}
        />
      )}
    </div>
  );
}

function AdjustDialog({ onClose }: { onClose: () => void }) {
  const users = useUserOptions(true);
  const adjust = useAdjust();
  const { values, bind } = useFields({ user: '', points: '', description: '' });
  const points = Number(values.points);
  const pointsOk = Number.isInteger(points) && points !== 0 && Math.abs(points) <= 100000;
  return (
    <Dialog
      open
      onClose={onClose}
      title="Adjust points"
      description="A manual correction of up to 100,000 points either way. It is recorded with your name."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={adjust.isPending} disabled={!values.user || !pointsOk || values.description.trim().length < 3} onClick={() => adjust.mutate({ user_id: values.user, points, description: values.description.trim() }, { onSuccess: onClose })}>
            Record adjustment
          </Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Person">{(c) => <Select {...c} data-autofocus {...bind('user')}><option value="">Choose a person</option>{(users.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>)}</Select>}</Field>
        <Field label="Points (negative to remove)" error={values.points !== '' && !pointsOk ? 'Enter a whole number other than 0, up to 100,000 either way.' : undefined}>{(c) => <Input {...c} inputMode="numeric" {...bind('points')} />}</Field>
        <Field label="Reason">{(c) => <Input {...c} maxLength={500} {...bind('description')} />}</Field>
        {users.isError && <Alert tone="warning">The people list could not be loaded: {getErrorMessage(users.error)}</Alert>}
        {adjust.isError && <Alert tone="danger">{getErrorMessage(adjust.error)}</Alert>}
      </div>
    </Dialog>
  );
}
