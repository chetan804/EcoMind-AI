import { useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import { MetricTile } from '@/components/data-display/MetricTile';
import { AuthImage } from '@/components/data-display/AuthImage';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import type { BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Choice';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, SearchInput, Select, Textarea } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { CountList } from '@/components/ui/StatList';
import { Pagination, Table } from '@/components/ui/Table';
import { useCollectors } from '@/features/collection';
import { LocationPicker, MapPanel, toPoint } from '@/features/maps';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDateTime, humanize } from '@/utils/format';
import { INCIDENT_STATUSES, INCIDENT_TYPES, type Incident } from '../api/incidents-api';
import { incidentMarkers } from '../markers';
import { useAssignIncident, useCreateIncident, useIncidents, useIncidentStatus, useIncidentSummary } from '../hooks/useIncidents';

const TONES: Record<string, BadgeTone> = { open: 'warning', acknowledged: 'info', in_progress: 'info', resolved: 'success', dismissed: 'neutral' };

/** Which statuses the server lets an incident move to (docs/api/community-incidents-api.md). */
const NEXT: Record<string, string[]> = {
  open: ['acknowledged', 'dismissed'],
  acknowledged: ['in_progress', 'resolved', 'dismissed'],
  in_progress: ['resolved', 'dismissed'],
  resolved: [],
  dismissed: [],
};

export function IncidentsPage() {
  const { can } = useAuth();
  const triage = can('incidents:triage');
  const [filters, setFilters] = useState({ page: 1, q: '', status: '', incident_type: '', unassigned: false });
  const [open, setOpen] = useState<Incident | null>(null);
  const [creating, setCreating] = useState(false);
  const query = useIncidents(filters);
  const summary = useIncidentSummary(triage);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  return (
    <section aria-labelledby="incidents-title" className="stack stack--tight">
      <PageHeader
        title="Community incident triage"
        titleId="incidents-title"
        subtitle={triage ? 'Review, assign and close reports from residents and field staff' : 'Problems you have reported or been assigned, and what happened to them'}
        actions={can('incidents:create') ? <Button onClick={() => setCreating(true)}>Report an incident</Button> : undefined}
      />
      {triage && summary.data && (
        <div className="grid-3">
          <MetricTile icon={<ShieldAlert size={22} />} tone="amber" label="Open incidents" value={String(summary.data.open_incidents)} note={`${summary.data.unassigned_open} unassigned`} />
          <div>
            <p className="muted">By status</p>
            <CountList items={summary.data.by_status} label="Incidents by status" />
          </div>
          <div>
            <p className="muted">By type</p>
            <CountList items={summary.data.by_type} label="Incidents by type" />
          </div>
        </div>
      )}
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Title or description" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Status">
          {(c) => <Select {...c} value={filters.status} onChange={(e) => set({ status: e.target.value })}><option value="">All statuses</option>{INCIDENT_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}</Select>}
        </Field>
        <Field label="Type">
          {(c) => <Select {...c} value={filters.incident_type} onChange={(e) => set({ incident_type: e.target.value })}><option value="">All types</option>{INCIDENT_TYPES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}</Select>}
        </Field>
        {triage && <Switch label="Unassigned only" checked={filters.unassigned} onChange={(e) => set({ unassigned: e.target.checked })} />}
      </div>
      <QueryBoundary query={query} label="incidents">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<ShieldAlert size={24} />} title="No incidents" description={can('incidents:create') ? 'Use "Report an incident" to flag a problem in your area.' : 'No incident matches these filters.'} />
          ) : (
            <>
              <Table caption="Incidents">
                <thead>
                  <tr>
                    <th scope="col">Incident</th>
                    <th scope="col">Type</th>
                    <th scope="col">Status</th>
                    <th scope="col">Reported</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((i) => (
                    <tr key={i.id}>
                      <th scope="row">{i.title}{i.address_text && <p className="muted">{i.address_text}</p>}</th>
                      <td>{humanize(i.incident_type)}</td>
                      <td><StatusBadge value={i.status} tones={TONES} /></td>
                      <td>{formatDateTime(i.created_at)}</td>
                      <td><Button variant="secondary" onClick={() => setOpen(i)} aria-label={`Open incident: ${i.title}`}>Open</Button></td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              {incidentMarkers(data.items).length > 0 && (
                <MapPanel label="Incidents on this page" markers={incidentMarkers(data.items)} height={300} />
              )}
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} incident${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {open && <IncidentDialog incident={open} triage={triage} onClose={() => setOpen(null)} />}
      {creating && <ReportDialog onClose={() => setCreating(false)} />}
    </section>
  );
}

function ReportDialog({ onClose }: { onClose: () => void }) {
  const { can } = useAuth();
  const create = useCreateIncident();
  const [photo, setPhoto] = useState<File | null>(null);
  const { values, bind, set } = useFields({ incident_type: 'illegal_dumping', title: '', description: '', address_text: '', latitude: '', longitude: '' });
  const [locationInvalid, setLocationInvalid] = useState(false);
  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Report an incident"
      description="Hazardous waste or fire: contact the emergency services first. This form is not monitored in real time."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={create.isPending}
            disabled={values.title.trim().length < 3 || locationInvalid}
            onClick={() =>
              create.mutate(
                {
                  photo,
                  body: {
                    incident_type: values.incident_type,
                    title: values.title.trim(),
                    description: optional(values.description),
                    address_text: optional(values.address_text),
                    latitude: optional(values.latitude),
                    longitude: optional(values.longitude),
                  },
                },
                { onSuccess: onClose },
              )
            }
          >
            Submit incident
          </Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Type">{(c) => <Select {...c} data-autofocus {...bind('incident_type')}>{INCIDENT_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</Select>}</Field>
        <Field label="Title">{(c) => <Input {...c} {...bind('title')} />}</Field>
        <Field label="Address or landmark">{(c) => <Input {...c} {...bind('address_text')} />}</Field>
        {can('waste_reports:create') && (
          <Field label="Photo (optional)" hint="JPEG, PNG or WebP. Location metadata is removed.">
            {(c) => <Input {...c} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />}
          </Field>
        )}
      </div>
      <Field label="Description (optional)">{(c) => <Textarea {...c} maxLength={5000} {...bind('description')} />}</Field>
      <fieldset className="stack stack--tight">
        <legend>Where is it? (optional)</legend>
        <LocationPicker
          label="Incident location"
          value={values.latitude && values.longitude ? { lat: Number(values.latitude), lng: Number(values.longitude) } : null}
          onChange={(point) => set({ latitude: point ? point.lat.toFixed(6) : '', longitude: point ? point.lng.toFixed(6) : '' })}
          onInvalidChange={setLocationInvalid}
        />
      </fieldset>
      {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
    </Dialog>
  );
}

function IncidentDialog({ incident, triage, onClose }: { incident: Incident; triage: boolean; onClose: () => void }) {
  const { can } = useAuth();
  const collectors = useCollectors(can('users:read'));
  const assign = useAssignIncident();
  const setStatus = useIncidentStatus();
  const [current, setCurrent] = useState(incident);
  const { values, bind, set } = useFields({ assignee: incident.assigned_to_id ?? '', status: '', notes: '' });
  const options = NEXT[current.status] ?? [];
  const needsNotes = values.status === 'resolved' || values.status === 'dismissed';
  const error = assign.error ?? setStatus.error;
  return (
    <Dialog open wide onClose={onClose} title="Incident" footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      <div className="stack stack--tight">
        <div>
          <h3 className="task__title">{current.title}</h3>
          <StatusBadge value={current.status} tones={TONES} /> {humanize(current.incident_type)}
        </div>
        <dl className="detail-list">
          <dt>Reported</dt><dd>{formatDateTime(current.created_at)}</dd>
          <dt>Place</dt><dd>{current.address_text ?? (current.latitude !== null ? `${current.latitude}, ${current.longitude}` : '—')}</dd>
          {current.description && (<><dt>Description</dt><dd>{current.description}</dd></>)}
          {current.resolution_notes && (<><dt>Resolution</dt><dd>{current.resolution_notes}</dd></>)}
        </dl>
        {toPoint(current.latitude, current.longitude) && <MapPanel label="Incident location" height={220} markers={incidentMarkers([current])} />}
        {current.photo_content_path && <AuthImage contentPath={current.photo_content_path} alt={`Photo for ${current.title}`} />}

        {triage && (
          <>
            <div className="stack stack--tight" role="group" aria-label="Assignment">
              <Field label="Assigned to">
                {(c) => (
                  <Select {...c} {...bind('assignee')}>
                    <option value="">Choose a person</option>
                    {(collectors.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                  </Select>
                )}
              </Field>
              <div>
                <Button variant="secondary" loading={assign.isPending} disabled={!values.assignee || values.assignee === current.assigned_to_id} onClick={() => assign.mutate({ id: current.id, assignee_id: values.assignee }, { onSuccess: setCurrent })}>
                  Assign
                </Button>
              </div>
            </div>
            {options.length > 0 && (
              <div className="stack stack--tight" role="group" aria-label="Change status">
                <Field label="Move to">
                  {(c) => <Select {...c} {...bind('status')}><option value="">Choose a status</option>{options.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}</Select>}
                </Field>
                <Field label={needsNotes ? 'Notes (required)' : 'Notes (optional)'}>{(c) => <Textarea {...c} maxLength={5000} {...bind('notes')} />}</Field>
                <div>
                  <Button loading={setStatus.isPending} disabled={!values.status || (needsNotes && values.notes.trim().length < 3)} onClick={() => setStatus.mutate({ id: current.id, status: values.status, notes: optional(values.notes) }, { onSuccess: (i) => { setCurrent(i); set({ status: '', notes: '' }); } })}>
                    Update status
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
        {error ? <Alert tone="danger">{getErrorMessage(error)}</Alert> : null}
      </div>
    </Dialog>
  );
}
