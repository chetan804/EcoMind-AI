import { useState } from 'react';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Pagination, Table } from '@/components/ui/Table';
import { formatDateTime } from '@/utils/format';
import { SettingsNav } from '@/features/settings';
import { useAudit } from '../hooks/useAudit';

/** Read-only, append-only record of security- and data-relevant actions. */
export function AuditPage() {
  const [filters, setFilters] = useState({ page: 1, action: '', entity_type: '' });
  const query = useAudit(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  return (
    <section aria-labelledby="audit-title" className="stack stack--tight">
      <PageHeader title="Audit log" titleId="audit-title" subtitle="Who did what, newest first. Entries cannot be edited or deleted." />
      <SettingsNav />
      <div className="filter-bar">
        <Field label="Action" hint="For example auth.login_failed">{(c) => <Input {...c} value={filters.action} onChange={(e) => set({ action: e.target.value })} />}</Field>
        <Field label="Entity type">{(c) => <Input {...c} value={filters.entity_type} onChange={(e) => set({ entity_type: e.target.value })} />}</Field>
      </div>
      <QueryBoundary query={query} label="the audit log">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState title="No audit entries match" description="Adjust the filters." />
          ) : (
            <>
              <Table caption="Audit log entries">
                <thead>
                  <tr>
                    <th scope="col">When</th>
                    <th scope="col">Action</th>
                    <th scope="col">Entity</th>
                    <th scope="col">Actor</th>
                    <th scope="col">Request</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((e) => (
                    <tr key={e.id}>
                      <td>{formatDateTime(e.occurred_at)}</td>
                      <th scope="row">{e.action}</th>
                      <td>{e.entity_type}</td>
                      <td>{e.actor_email ?? 'system or anonymous'}</td>
                      <td className="muted">{e.request_id ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} entr${data.total === 1 ? 'y' : 'ies'}`}
              />
            </>
          )
        }
      </QueryBoundary>
    </section>
  );
}
