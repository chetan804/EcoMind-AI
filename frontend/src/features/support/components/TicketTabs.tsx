import { useState } from 'react';
import { LifeBuoy } from 'lucide-react';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Choice';
import { Field } from '@/components/ui/Field';
import { SearchInput, Select } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { formatDateTime, humanize } from '@/utils/format';
import { TICKET_STATUSES, type Ticket } from '../api/support-api';
import { useMyTickets, useQueue } from '../hooks/useSupport';
import { NewRequestDialog } from './NewRequestDialog';
import { TicketDialog } from './TicketDialog';
import { STATUS_TONE } from './tones';

const pageCount = (d: { total: number; page_size: number }) => Math.max(1, Math.ceil(d.total / d.page_size));

function StatusFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Field label="Status">
      {(c) => (
        <Select {...c} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">All statuses</option>
          {TICKET_STATUSES.map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}

function TicketTable({ tickets, caption, staff, onOpen }: { tickets: Ticket[]; caption: string; staff: boolean; onOpen: (t: Ticket) => void }) {
  return (
    <Table caption={caption}>
      <thead>
        <tr>
          <th scope="col">Subject</th>
          {staff && <th scope="col">From</th>}
          <th scope="col">Status</th>
          <th scope="col">Handled by</th>
          <th scope="col">Replies</th>
          <th scope="col">Updated</th>
          <th scope="col">
            <span className="visually-hidden">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {tickets.map((t) => (
          <tr key={t.id}>
            <td>{t.subject}</td>
            {staff && <td>{t.requester_name ?? '—'}</td>}
            <td>
              <StatusBadge value={t.status} tones={STATUS_TONE} />
            </td>
            <td>{t.assignee_name ?? '—'}</td>
            <td>{t.reply_count}</td>
            <td>{formatDateTime(t.updated_at)}</td>
            <td>
              <Button variant="secondary" onClick={() => onOpen(t)} aria-label={`Open request: ${t.subject}`}>
                Open
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** The person's own requests, and a way to start a new one. */
export function MyRequestsTab() {
  const [filters, setFilters] = useState({ page: 1, status: '' });
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const query = useMyTickets(filters);
  return (
    <div className="stack stack--tight">
      <div className="filter-bar">
        <StatusFilter value={filters.status} onChange={(status) => setFilters({ page: 1, status })} />
        <Button onClick={() => setCreating(true)}>New request</Button>
      </div>
      <QueryBoundary query={query} label="your requests">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState
              icon={<LifeBuoy size={28} />}
              title={filters.status ? 'No requests with that status' : 'You have no support requests'}
              description="Try the help assistant first; if it cannot help, send a request and the support team will reply here."
            />
          ) : (
            <>
              <TicketTable tickets={data.items} caption="My support requests" staff={false} onOpen={(t) => setOpenId(t.id)} />
              <Pagination page={data.page} pageCount={pageCount(data)} onPageChange={(page) => setFilters((f) => ({ ...f, page }))} summary={`${data.total} requests`} />
            </>
          )
        }
      </QueryBoundary>
      {creating && <NewRequestDialog onClose={() => setCreating(false)} onCreated={setOpenId} />}
      {openId && <TicketDialog id={openId} staff={false} onClose={() => setOpenId(null)} />}
    </div>
  );
}

/** Everyone's requests, for people who run the support desk. */
export function QueueTab() {
  const [filters, setFilters] = useState({ page: 1, status: '', assigned_to_me: false, unassigned: false, q: '' });
  const [openId, setOpenId] = useState<string | null>(null);
  const query = useQueue(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  return (
    <div className="stack stack--tight">
      <div className="filter-bar">
        <Field label="Search subjects">{(c) => <SearchInput {...c} value={filters.q} onChange={(e) => set({ q: e.target.value })} maxLength={100} />}</Field>
        <StatusFilter value={filters.status} onChange={(status) => set({ status })} />
        <Checkbox label="Assigned to me" checked={filters.assigned_to_me} onChange={(e) => set({ assigned_to_me: e.target.checked, unassigned: false })} />
        <Checkbox label="Unassigned" checked={filters.unassigned} onChange={(e) => set({ unassigned: e.target.checked, assigned_to_me: false })} />
      </div>
      <QueryBoundary query={query} label="the support queue">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<LifeBuoy size={28} />} title="No requests match" description="Nothing is waiting for the filters you chose." />
          ) : (
            <>
              <TicketTable tickets={data.items} caption="Support queue" staff onOpen={(t) => setOpenId(t.id)} />
              <Pagination page={data.page} pageCount={pageCount(data)} onPageChange={(page) => setFilters((f) => ({ ...f, page }))} summary={`${data.total} requests`} />
            </>
          )
        }
      </QueryBoundary>
      {openId && <TicketDialog id={openId} staff onClose={() => setOpenId(null)} />}
    </div>
  );
}
