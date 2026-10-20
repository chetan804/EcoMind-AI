import { useState } from 'react';
import { FileText } from 'lucide-react';
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
import { REPORT_STATUSES } from '../api/reports-api';
import { CreateReportDialog, ReportDialog } from '../components/ReportDialogs';
import { ReportStatusBadge } from '../components/ReportStatusBadge';
import { useReports } from '../hooks/useReports';

export function ReportsPage() {
  const { can } = useAuth();
  const seesAll = can('waste_reports:read_all');
  const [filters, setFilters] = useState({ page: 1, q: '', status: '', mine: !seesAll });
  const [open, setOpen] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const query = useReports(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  return (
    <section aria-labelledby="reports-title" className="stack stack--tight">
      <PageHeader
        title="Waste intake records"
        titleId="reports-title"
        subtitle="Reports of waste that needs collecting"
        actions={can('waste_reports:create') ? <Button onClick={() => setCreating(true)}>Report waste</Button> : undefined}
      />
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Title or address" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Status">
          {(c) => (
            <Select {...c} value={filters.status} onChange={(e) => set({ status: e.target.value })}>
              <option value="">All statuses</option>
              {REPORT_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
            </Select>
          )}
        </Field>
        {seesAll && <Switch label="Only my reports" checked={filters.mine} onChange={(e) => set({ mine: e.target.checked })} />}
      </div>
      <QueryBoundary query={query} label="waste reports">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<FileText size={24} />} title="No reports yet" description={can('waste_reports:create') ? 'Use "Report waste" to submit the first one.' : 'No report matches these filters.'} />
          ) : (
            <>
              <Table caption="Waste reports">
                <thead>
                  <tr>
                    <th scope="col">Report</th>
                    <th scope="col">Status</th>
                    <th scope="col">Estimated weight</th>
                    <th scope="col">Photos</th>
                    <th scope="col">Reported</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.id}>
                      <th scope="row">
                        {r.title}
                        {r.address_text && <p className="muted">{r.address_text}</p>}
                      </th>
                      <td><ReportStatusBadge value={r.status} /></td>
                      <td>{r.estimated_weight_kg === null ? '—' : formatKg(r.estimated_weight_kg)}</td>
                      <td>{r.media.length}</td>
                      <td>{formatDateTime(r.reported_at)}</td>
                      <td><Button variant="secondary" onClick={() => setOpen(r.id)} aria-label={`Open report: ${r.title}`}>Open</Button></td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} report${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {open && <ReportDialog reportId={open} onClose={() => setOpen(null)} />}
      {creating && <CreateReportDialog onClose={() => setCreating(false)} />}
    </section>
  );
}
