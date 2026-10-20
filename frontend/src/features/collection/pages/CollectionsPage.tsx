import { useState } from 'react';
import { ClipboardList } from 'lucide-react';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Choice';
import { Field } from '@/components/ui/Field';
import { SearchInput, Select } from '@/components/ui/Input';
import { Pagination, Table } from '@/components/ui/Table';
import { useAuth } from '@/services/session';
import { formatDateTime, formatKg, humanize } from '@/utils/format';
import { PRIORITIES, TASK_STATUSES } from '../api/collection-api';
import { CreateTaskDialog } from '../components/CreateTaskDialog';
import { TaskDialog } from '../components/TaskDialog';
import { PriorityBadge, TaskStatusBadge } from '../components/badges';
import { useTasks } from '../hooks/useCollection';

export function CollectionsPage() {
  const { can } = useAuth();
  const manage = can('collection:manage');
  const [filters, setFilters] = useState({ page: 1, q: '', status: '', priority: '', mine: !manage });
  const [open, setOpen] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const query = useTasks(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  return (
    <section aria-labelledby="collections-title" className="stack stack--tight">
      <PageHeader
        title="Collections"
        titleId="collections-title"
        subtitle="Field work: assign, collect, record weight"
        actions={manage ? <Button onClick={() => setCreating(true)}>New task</Button> : undefined}
      />
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Title or address" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Status">
          {(c) => (
            <Select {...c} value={filters.status} onChange={(e) => set({ status: e.target.value })}>
              <option value="">All statuses</option>
              {TASK_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Priority">
          {(c) => (
            <Select {...c} value={filters.priority} onChange={(e) => set({ priority: e.target.value })}>
              <option value="">All priorities</option>
              {PRIORITIES.map((p) => <option key={p} value={p}>{humanize(p)}</option>)}
            </Select>
          )}
        </Field>
        <Switch label="Assigned to me" checked={filters.mine} onChange={(e) => set({ mine: e.target.checked })} />
      </div>
      <QueryBoundary query={query} label="collection tasks">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<ClipboardList size={24} />} title="No collection tasks" description={filters.mine ? 'Nothing is assigned to you. Turn off "Assigned to me" to see every task.' : 'No task matches these filters.'} />
          ) : (
            <>
              <Table caption="Collection tasks">
                <thead>
                  <tr>
                    <th scope="col">Task</th>
                    <th scope="col">Priority</th>
                    <th scope="col">Status</th>
                    <th scope="col">Due</th>
                    <th scope="col">Assigned to</th>
                    <th scope="col">Collected</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((t) => {
                    const a = t.assignment && !t.assignment.unassigned_at ? t.assignment : null;
                    return (
                      <tr key={t.id}>
                        <th scope="row">
                          {t.title}
                          {t.address_text && <p className="muted">{t.address_text}</p>}
                        </th>
                        <td><PriorityBadge value={t.priority} /></td>
                        <td><TaskStatusBadge value={t.status} /></td>
                        <td>{formatDateTime(t.due_at)}</td>
                        <td>{a ? a.assignee_name : '—'}{a?.vehicle_registration ? <p className="muted">{a.vehicle_registration}</p> : null}</td>
                        <td>{t.collected_weight_kg == null ? '—' : formatKg(t.collected_weight_kg)}</td>
                        <td><Button variant="secondary" onClick={() => setOpen(t.id)} aria-label={`Open task: ${t.title}`}>Open</Button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} task${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {open && <TaskDialog taskId={open} onClose={() => setOpen(null)} />}
      {creating && <CreateTaskDialog onClose={() => setCreating(false)} />}
    </section>
  );
}
