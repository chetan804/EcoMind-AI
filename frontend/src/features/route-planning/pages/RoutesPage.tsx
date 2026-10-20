import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Route } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import type { BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Choice';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, Select } from '@/components/ui/Input';
import { ReasonDialog } from '@/components/ui/ReasonDialog';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { fetchTasks, useCollectors } from '@/features/collection';
import { useFacilityOptions } from '@/features/facilities';
import { useVehicleOptions } from '@/features/fleet';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDate, formatNumber, humanize } from '@/utils/format';
import { PLAN_STATUSES } from '../api/routes-api';
import { RoutePlanMap } from '../components/RoutePlanMap';
import { useCreatePlan, usePlan, usePlanAction, usePlans } from '../hooks/useRoutes';

const TONES: Record<string, BadgeTone> = { draft: 'warning', published: 'info', in_progress: 'info', completed: 'success', cancelled: 'neutral' };
const MAX_TASKS = 40;

export function RoutesPage() {
  const { can } = useAuth();
  const [filters, setFilters] = useState({ page: 1, status: '' });
  const [open, setOpen] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const query = usePlans(filters);
  return (
    <section aria-labelledby="routes-title" className="stack stack--tight">
      <PageHeader
        title="Route optimization"
        titleId="routes-title"
        subtitle="Deterministic stop ordering from straight-line distances, with no live traffic or travel-time estimate"
        actions={can('routes:manage') ? <Button onClick={() => setCreating(true)}>Plan a route</Button> : undefined}
      />
      <div className="filter-bar">
        <Field label="Status">
          {(c) => (
            <Select {...c} value={filters.status} onChange={(e) => setFilters({ page: 1, status: e.target.value })}>
              <option value="">All statuses</option>
              {PLAN_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
            </Select>
          )}
        </Field>
      </div>
      <QueryBoundary query={query} label="route plans">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<Route size={24} />} title="No route plans" description="Plan a route to order a set of collection tasks into the shortest stop sequence." />
          ) : (
            <>
              <Table caption="Route plans">
                <thead>
                  <tr>
                    <th scope="col">Plan</th>
                    <th scope="col">Date</th>
                    <th scope="col">Status</th>
                    <th scope="col">Distance</th>
                    <th scope="col">Ordering method</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((p) => (
                    <tr key={p.id}>
                      <th scope="row">{p.name}</th>
                      <td>{formatDate(p.planned_date)}</td>
                      <td><StatusBadge value={p.status} tones={TONES} /></td>
                      <td>{p.total_distance_km === null ? '—' : `${formatNumber(p.total_distance_km)} km`}</td>
                      <td>{p.optimizer ?? '—'}</td>
                      <td><Button variant="secondary" onClick={() => setOpen(p.id)} aria-label={`Open plan: ${p.name}`}>Open</Button></td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} plan${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {open && <PlanDialog planId={open} onClose={() => setOpen(null)} />}
      {creating && <CreatePlanDialog onClose={() => setCreating(false)} onCreated={setOpen} />}
    </section>
  );
}

function CreatePlanDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const { can } = useAuth();
  const create = useCreatePlan();
  const facilities = useFacilityOptions(can('facilities:read'));
  const vehicles = useVehicleOptions(can('fleet:read'));
  const drivers = useCollectors(can('users:read'));
  const tasks = useQuery({
    queryKey: ['collection', 'plannable'],
    queryFn: ({ signal }) => fetchTasks({ page: 1, q: '', status: '', priority: '', mine: false, page_size: 100 }, signal),
    select: (page) => page.items.filter((t) => (t.status === 'pending' || t.status === 'assigned') && t.latitude !== null),
  });
  const [chosen, setChosen] = useState<string[]>([]);
  const { values, bind } = useFields({ name: '', date: '', start: '', end: '', vehicle: '', driver: '' });
  const valid = values.name.trim().length >= 2 && values.date !== '' && values.start !== '' && chosen.length > 0 && chosen.length <= MAX_TASKS;
  const submit = () =>
    create.mutate(
      {
        name: values.name.trim(),
        planned_date: values.date,
        start_facility_id: values.start,
        end_facility_id: optional(values.end),
        task_ids: chosen,
        vehicle_id: optional(values.vehicle),
        driver_id: optional(values.driver),
      },
      { onSuccess: (plan) => { onClose(); onCreated(plan.id); } },
    );
  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Plan a route"
      description="Only tasks with coordinates can be ordered. The plan is a draft until published."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!valid} onClick={submit}>Create plan</Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Plan name">{(c) => <Input {...c} data-autofocus {...bind('name')} />}</Field>
        <Field label="Date">{(c) => <Input {...c} type="date" {...bind('date')} />}</Field>
        <Field label="Start depot">
          {(c) => <Select {...c} {...bind('start')}><option value="">Choose a facility</option>{(facilities.data ?? []).filter((f) => f.latitude !== null).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</Select>}
        </Field>
        <Field label="End at (optional)">
          {(c) => <Select {...c} {...bind('end')}><option value="">Last stop</option>{(facilities.data ?? []).filter((f) => f.latitude !== null).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</Select>}
        </Field>
        <Field label="Vehicle (optional)">
          {(c) => <Select {...c} {...bind('vehicle')}><option value="">None</option>{(vehicles.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.registration_number}</option>)}</Select>}
        </Field>
        <Field label="Driver (optional)">
          {(c) => <Select {...c} {...bind('driver')}><option value="">None</option>{(drivers.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</Select>}
        </Field>
      </div>
      <fieldset className="settings-form">
        <legend>Tasks to include ({chosen.length} of up to {MAX_TASKS})</legend>
        {tasks.isPending && <p role="status">Loading tasks…</p>}
        {tasks.isError && <Alert tone="danger">{getErrorMessage(tasks.error)}</Alert>}
        {tasks.data?.length === 0 && <p className="muted">No pending or assigned task has coordinates yet.</p>}
        {(tasks.data ?? []).map((t) => (
          <Checkbox
            key={t.id}
            label={`${t.title}${t.address_text ? `, ${t.address_text}` : ''}`}
            checked={chosen.includes(t.id)}
            onChange={(e) => setChosen((c) => (e.target.checked ? [...c, t.id] : c.filter((x) => x !== t.id)))}
          />
        ))}
      </fieldset>
      {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
    </Dialog>
  );
}

function PlanDialog({ planId, onClose }: { planId: string; onClose: () => void }) {
  const { can } = useAuth();
  const query = usePlan(planId);
  const action = usePlanAction(planId);
  const [cancelling, setCancelling] = useState(false);
  return (
    <Dialog open wide onClose={onClose} title="Route plan" footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      <QueryBoundary query={query} label="the plan">
        {(plan) => (
          <div className="stack stack--tight">
            <div>
              <h3 className="task__title">{plan.name}</h3>
              <StatusBadge value={plan.status} tones={TONES} />
            </div>
            <dl className="detail-list">
              <dt>Date</dt><dd>{formatDate(plan.planned_date)}</dd>
              <dt>Total distance</dt><dd>{plan.total_distance_km === null ? '—' : `${formatNumber(plan.total_distance_km)} km`}</dd>
              <dt>Ordering method</dt><dd>{plan.optimizer ?? '—'}</dd>
              {plan.start_label && (<><dt>Starts at</dt><dd>{plan.start_label}</dd></>)}
            </dl>
            {(plan.warnings ?? []).map((w) => <Alert key={w} tone="warning">{w}</Alert>)}
            <RoutePlanMap plan={plan} />
            <Table caption="Stops in order">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Stop</th>
                  <th scope="col">Leg distance</th>
                </tr>
              </thead>
              <tbody>
                {plan.stops.map((s) => (
                  <tr key={s.sequence}>
                    <td>{s.sequence}</td>
                    <th scope="row">{s.label} <span className="muted">({s.kind})</span></th>
                    <td>{formatNumber(s.leg_distance_km)} km</td>
                  </tr>
                ))}
              </tbody>
            </Table>
            {plan.return_leg_distance_km != null && <p className="muted">Return leg: {formatNumber(plan.return_leg_distance_km)} km.</p>}
            {plan.basis && <p className="muted">{plan.basis}</p>}
            {action.isError && <Alert tone="danger">{getErrorMessage(action.error)}</Alert>}
            {can('routes:manage') && (
              <div className="row-actions">
                {plan.status === 'draft' && <Button loading={action.isPending} onClick={() => action.mutate({ action: 'publish' })}>Publish plan</Button>}
                {(plan.status === 'draft' || plan.status === 'published') && <Button variant="danger" onClick={() => setCancelling(true)}>Cancel plan</Button>}
              </div>
            )}
            {cancelling && (
              <ReasonDialog
                title="Cancel plan"
                submitLabel="Cancel plan"
                destructive
                pending={action.isPending}
                error={action.error}
                onSubmit={(reason) => action.mutate({ action: 'cancel', reason }, { onSuccess: () => setCancelling(false) })}
                onClose={() => { setCancelling(false); action.reset(); }}
              />
            )}
          </div>
        )}
      </QueryBoundary>
    </Dialog>
  );
}
