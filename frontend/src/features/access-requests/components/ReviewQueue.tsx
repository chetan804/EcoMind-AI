import { useState } from 'react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Select, Textarea } from '@/components/ui/Input';
import { Pagination, Table } from '@/components/ui/Table';
import { getErrorMessage } from '@/services/error-handler';
import { formatDateTime, humanize } from '@/utils/format';
import type { RoleRequest } from '../api/access-requests-api';
import { useRequestChanges, useRequests } from '../hooks/useAccessRequests';
import { STATUS_TONE } from '../status-tone';

/** Administrators: requests for operational roles, newest first. Approving adds the role; rejecting needs a reason. */
export function ReviewQueue() {
  const [filters, setFilters] = useState({ status_filter: 'pending', page: 1 });
  const [deciding, setDeciding] = useState<{ row: RoleRequest; approve: boolean } | null>(null);
  const query = useRequests(filters);
  return (
    <div className="stack stack--tight">
      <div className="filter-bar">
        <Field label="Status">
          {(c) => (
            <Select {...c} value={filters.status_filter} onChange={(e) => setFilters({ status_filter: e.target.value, page: 1 })}>
              <option value="pending">Waiting for a decision</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="withdrawn">Withdrawn</option>
              <option value="">All</option>
            </Select>
          )}
        </Field>
      </div>
      <QueryBoundary query={query} label="role requests">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState title="No role requests here" description="When someone asks for a collector, facility operator or manager role it appears in this list." />
          ) : (
            <>
              <Table caption="Role requests">
                <thead>
                  <tr>
                    <th scope="col">Person</th>
                    <th scope="col">Role</th>
                    <th scope="col">Reason</th>
                    <th scope="col">Status</th>
                    <th scope="col">Sent</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.id}>
                      <th scope="row">
                        {r.requester_name}
                        <p className="muted">{r.requester_email}{r.organisation ? ` · ${r.organisation}` : ''}</p>
                      </th>
                      <td>{humanize(r.requested_role)}</td>
                      <td className="access-reason">{r.reason}{r.decision_note && <p className="muted">Decision note: {r.decision_note}</p>}</td>
                      <td><Badge tone={STATUS_TONE[r.status]} dot>{humanize(r.status)}</Badge></td>
                      <td>{formatDateTime(r.created_at)}</td>
                      <td>
                        {r.status === 'pending' && (
                          <div className="row-actions">
                            <Button onClick={() => setDeciding({ row: r, approve: true })} aria-label={`Approve ${humanize(r.requested_role)} for ${r.requester_name}`}>Approve</Button>
                            <Button variant="secondary" onClick={() => setDeciding({ row: r, approve: false })} aria-label={`Reject ${humanize(r.requested_role)} for ${r.requester_name}`}>Reject</Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} request${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {deciding && <DecisionDialog key={deciding.row.id + String(deciding.approve)} {...deciding} onClose={() => setDeciding(null)} />}
    </div>
  );
}

function DecisionDialog({ row, approve, onClose }: { row: RoleRequest; approve: boolean; onClose: () => void }) {
  const [note, setNote] = useState('');
  const { decide } = useRequestChanges();
  const valid = approve || note.trim().length >= 3;
  const role = humanize(row.requested_role);
  return (
    <Dialog
      open
      onClose={onClose}
      title={approve ? `Approve ${role} role` : `Reject ${role} role`}
      description={`${row.requester_name} (${row.requester_email}). The decision is audited and the person is notified.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            variant={approve ? 'primary' : 'danger'}
            loading={decide.isPending}
            unavailableReason={valid ? undefined : 'Give a short reason for rejecting.'}
            onClick={() => decide.mutate({ id: row.id, approve, note }, { onSuccess: onClose })}
          >
            {approve ? 'Approve and grant role' : 'Reject request'}
          </Button>
        </>
      }
    >
      <p className="access-reason">{row.reason}</p>
      <Field label={approve ? 'Note to the person (optional)' : 'Reason (required)'}>
        {(c) => <Textarea {...c} data-autofocus value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />}
      </Field>
      {decide.isError && <Alert tone="danger">{getErrorMessage(decide.error)}</Alert>}
    </Dialog>
  );
}
