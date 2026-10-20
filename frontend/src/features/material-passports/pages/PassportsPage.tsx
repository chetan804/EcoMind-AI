import { useState } from 'react';
import { QrCode } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import type { BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, SearchInput, Select, Textarea } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { useRecordOptions } from '@/features/circular-economy';
import { useFacilityOptions } from '@/features/facilities';
import { useCategories } from '@/features/sorting-guide';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDateTime, formatKg, humanize } from '@/utils/format';
import { EVENT_TYPES, PASSPORT_STATUSES, type PassportDetail } from '../api/passports-api';
import { useAddEvent, useCreatePassport, useIntegrity, useLinkRecovery, usePassport, usePassports } from '../hooks/usePassports';

const TONES: Record<string, BadgeTone> = { active: 'info', in_processing: 'warning', recovered: 'success', retired: 'neutral' };

/** The event types that can legally follow the last recorded one (docs/api/material-passports-api.md). */
const NEXT: Record<string, string[]> = {
  none: ['created'],
  created: ['collected', 'transferred', 'received'],
  collected: ['transferred', 'received'],
  transferred: ['transferred', 'received'],
  received: ['transferred', 'processed'],
  processed: ['verified'],
  verified: [],
};

export function PassportsPage() {
  const { can } = useAuth();
  const [filters, setFilters] = useState({ page: 1, q: '', status: '' });
  const [open, setOpen] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const categories = useCategories(true, can('sorting_guide:read'));
  const query = usePassports(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const categoryName = (id: string) => categories.data?.find((c) => c.id === id)?.name ?? 'Unknown material';

  return (
    <section aria-labelledby="passports-title" className="stack stack--tight">
      <PageHeader
        title="Chain-of-custody passports"
        titleId="passports-title"
        subtitle="Each batch carries an append-only record of who held it and where it went. The integrity check tests consistency of that record; it is not a cryptographic proof."
        actions={can('passports:manage') ? <Button onClick={() => setCreating(true)}>Create passport</Button> : undefined}
      />
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Passport code or description" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Status">
          {(c) => <Select {...c} value={filters.status} onChange={(e) => set({ status: e.target.value })}><option value="">All statuses</option>{PASSPORT_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}</Select>}
        </Field>
      </div>
      <QueryBoundary query={query} label="passports">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<QrCode size={24} />} title="No passports yet" description={can('passports:manage') ? 'Create a passport when a batch of material enters the chain.' : 'No passport matches these filters.'} />
          ) : (
            <>
              <Table caption="Material passports">
                <thead>
                  <tr>
                    <th scope="col">Passport</th>
                    <th scope="col">Material</th>
                    <th scope="col">Weight</th>
                    <th scope="col">Status</th>
                    <th scope="col">Created</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((p) => (
                    <tr key={p.id}>
                      <th scope="row">{p.passport_code}{p.description && <p className="muted">{p.description}</p>}</th>
                      <td>{categoryName(p.material_category_id)}</td>
                      <td>{formatKg(p.weight_kg)}</td>
                      <td><StatusBadge value={p.status} tones={TONES} /></td>
                      <td>{formatDateTime(p.created_at)}</td>
                      <td><Button variant="secondary" onClick={() => setOpen(p.id)} aria-label={`Open passport ${p.passport_code}`}>Open</Button></td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={data.page} pageCount={Math.max(1, Math.ceil(data.total / data.page_size))} onPageChange={(page) => setFilters((f) => ({ ...f, page }))} summary={`${data.total} passport${data.total === 1 ? '' : 's'}`} />
            </>
          )
        }
      </QueryBoundary>
      {open && <PassportDialog passportId={open} onClose={() => setOpen(null)} />}
      {creating && <CreateDialog onClose={() => setCreating(false)} />}
    </section>
  );
}

function CreateDialog({ onClose }: { onClose: () => void }) {
  const { can } = useAuth();
  const categories = useCategories(false, can('sorting_guide:read'));
  const facilities = useFacilityOptions(can('facilities:read'));
  const create = useCreatePassport();
  const { values, bind } = useFields({ category: '', weight: '', description: '', facility: '' });
  return (
    <Dialog
      open
      onClose={onClose}
      title="Create passport"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!values.category || !(Number(values.weight) > 0)} onClick={() => create.mutate({ material_category_id: values.category, weight_kg: values.weight.trim(), description: optional(values.description), current_facility_id: optional(values.facility) }, { onSuccess: onClose })}>
            Create passport
          </Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Material">{(c) => <Select {...c} data-autofocus {...bind('category')}><option value="">Choose a material</option>{(categories.data ?? []).map((cat) => <option key={cat.id} value={cat.id}>{cat.name}</option>)}</Select>}</Field>
        <Field label="Weight (kg)">{(c) => <Input {...c} inputMode="decimal" {...bind('weight')} />}</Field>
        <Field label="Held at (optional)">{(c) => <Select {...c} {...bind('facility')}><option value="">Not at a facility</option>{(facilities.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</Select>}</Field>
        <Field label="Description (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('description')} />}</Field>
        {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
      </div>
    </Dialog>
  );
}

function PassportDialog({ passportId, onClose }: { passportId: string; onClose: () => void }) {
  const query = usePassport(passportId);
  return (
    <Dialog open wide onClose={onClose} title="Passport" footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      <QueryBoundary query={query} label="the passport">{(p) => <PassportBody passport={p} />}</QueryBoundary>
    </Dialog>
  );
}

function PassportBody({ passport: p }: { passport: PassportDetail }) {
  const { can } = useAuth();
  const facilities = useFacilityOptions(can('facilities:read'));
  const categories = useCategories(true, can('sorting_guide:read'));
  const integrity = useIntegrity(p.id);
  const [mode, setMode] = useState<null | 'event' | 'link'>(null);
  const facilityName = (id: string | null) => (id ? (facilities.data?.find((f) => f.id === id)?.name ?? 'Unknown facility') : '—');
  const last = p.events.at(-1)?.event_type ?? 'none';
  const next = p.status === 'recovered' || p.status === 'retired' ? [] : (NEXT[last] ?? []);
  return (
    <div className="stack stack--tight">
      <div>
        <h3 className="task__title">{p.passport_code}</h3>
        <StatusBadge value={p.status} tones={TONES} />
      </div>
      <dl className="detail-list">
        <dt>Material</dt><dd>{categories.data?.find((c) => c.id === p.material_category_id)?.name ?? '—'}</dd>
        <dt>Weight</dt><dd>{formatKg(p.weight_kg)}</dd>
        <dt>Currently at</dt><dd>{p.current_facility_id ? facilityName(p.current_facility_id) : p.status === 'active' && last === 'transferred' ? 'In transit' : '—'}</dd>
        <dt>Recovery record</dt><dd>{p.recovery_record_id ? 'Linked' : 'Not linked'}</dd>
        {p.description && (<><dt>Description</dt><dd>{p.description}</dd></>)}
      </dl>
      <section aria-label="Custody events">
        <h4>Custody events</h4>
        {p.events.length === 0 ? <p className="muted">No events recorded.</p> : (
          <ol className="timeline">
            {p.events.map((e) => (
              <li key={e.id}>
                <strong>{e.sequence}. {humanize(e.event_type)}</strong> · {formatDateTime(e.occurred_at)}
                {e.from_facility_id && ` · from ${facilityName(e.from_facility_id)}`}
                {e.to_facility_id && ` · to ${facilityName(e.to_facility_id)}`}
                {e.notes && <span className="muted"> · {e.notes}</span>}
              </li>
            ))}
          </ol>
        )}
      </section>
      <div className="row-actions">
        <Button variant="secondary" loading={integrity.isFetching} onClick={() => void integrity.refetch()}>Check integrity</Button>
        {can('passports:manage') && next.length > 0 && <Button onClick={() => setMode('event')}>Record custody event</Button>}
        {can('passports:manage') && !p.recovery_record_id && p.status !== 'retired' && <Button variant="secondary" onClick={() => setMode('link')}>Link recovery record</Button>}
      </div>
      {integrity.isError && <Alert tone="danger">{getErrorMessage(integrity.error)}</Alert>}
      {integrity.data && (
        <Alert tone={integrity.data.valid ? 'success' : 'danger'} title={integrity.data.valid ? `Chain consistent (${integrity.data.events} events)` : 'Chain has problems'}>
          {integrity.data.valid ? null : <ul>{integrity.data.problems.map((x) => <li key={x}>{x}</li>)}</ul>}
          {integrity.data.basis}
        </Alert>
      )}
      {mode === 'event' && <EventDialog passport={p} options={next} onClose={() => setMode(null)} />}
      {mode === 'link' && <LinkDialog passport={p} onClose={() => setMode(null)} />}
    </div>
  );
}

function EventDialog({ passport, options, onClose }: { passport: PassportDetail; options: string[]; onClose: () => void }) {
  const { can } = useAuth();
  const facilities = useFacilityOptions(can('facilities:read'));
  const add = useAddEvent(passport.id);
  const { values, bind } = useFields({ type: options[0] ?? '', from: '', to: '', notes: '' });
  const needsTo = values.type === 'transferred' || values.type === 'received';
  return (
    <Dialog
      open
      onClose={onClose}
      title="Record custody event"
      description="Events are append-only: they cannot be edited or deleted afterwards."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={add.isPending} disabled={needsTo && !values.to} onClick={() => add.mutate({ event_type: values.type, to_facility_id: needsTo ? values.to : undefined, from_facility_id: values.type === 'transferred' ? optional(values.from) : undefined, notes: optional(values.notes) }, { onSuccess: onClose })}>
            Record event
          </Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Event">{(c) => <Select {...c} data-autofocus {...bind('type')}>{options.filter((o) => (EVENT_TYPES as readonly string[]).includes(o)).map((o) => <option key={o} value={o}>{humanize(o)}</option>)}</Select>}</Field>
        {needsTo && <Field label="To facility">{(c) => <Select {...c} {...bind('to')}><option value="">Choose a facility</option>{(facilities.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</Select>}</Field>}
        <Field label="Notes (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('notes')} />}</Field>
        {add.isError && <Alert tone="danger">{getErrorMessage(add.error)}</Alert>}
      </div>
    </Dialog>
  );
}

function LinkDialog({ passport, onClose }: { passport: PassportDetail; onClose: () => void }) {
  const { can } = useAuth();
  const records = useRecordOptions(can('circular_economy:read'));
  const link = useLinkRecovery(passport.id);
  const { values, bind } = useFields({ record: '' });
  const options = (records.data ?? []).filter((r) => r.material_category_id === passport.material_category_id);
  return (
    <Dialog
      open
      onClose={onClose}
      title="Link recovery record"
      description="Only a record for the same material that is not rejected and not linked elsewhere can be linked. Verification of the batch needs a verified record."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={link.isPending} disabled={!values.record} onClick={() => link.mutate(values.record, { onSuccess: onClose })}>Link record</Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Recovery record">
          {(c) => (
            <Select {...c} data-autofocus {...bind('record')}>
              <option value="">Choose a record</option>
              {options.map((r) => <option key={r.id} value={r.id}>{formatDateTime(r.processed_at)}: {formatKg(r.recovered_weight_kg)} {humanize(r.recovery_method)} ({humanize(r.verification_status)})</option>)}
            </Select>
          )}
        </Field>
        {options.length === 0 && <p className="muted">No suitable record exists for this material yet.</p>}
        {link.isError && <Alert tone="danger">{getErrorMessage(link.error)}</Alert>}
      </div>
    </Dialog>
  );
}
