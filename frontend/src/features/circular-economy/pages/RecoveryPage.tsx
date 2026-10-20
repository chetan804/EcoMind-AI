import { useState } from 'react';
import { Recycle } from 'lucide-react';
import { MetricTile } from '@/components/data-display/MetricTile';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import type { BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, Select, Textarea } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { useFacilityOptions } from '@/features/facilities';
import { useCategories } from '@/features/sorting-guide';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatDateTime, formatKg, humanize } from '@/utils/format';
import { METHODS, VERIFICATION, type Recovery } from '../api/recovery-api';
import { useCreateRecord, useRecords, useRecoverySummary, useVerifyRecord } from '../hooks/useRecovery';

const TONES: Record<string, BadgeTone> = { pending: 'warning', verified: 'success', rejected: 'danger' };
const percent = (rate: number | null) => (rate === null ? 'Not available' : `${(rate * 100).toFixed(1)}%`);

export function RecoveryPage() {
  const { can } = useAuth();
  const [filters, setFilters] = useState({ page: 1, status: '', recovery_method: '', facility_id: '' });
  const [creating, setCreating] = useState(false);
  const [verifying, setVerifying] = useState<Recovery | null>(null);
  const facilities = useFacilityOptions(can('facilities:read'));
  const categories = useCategories(true, can('sorting_guide:read'));
  const summary = useRecoverySummary();
  const query = useRecords(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const facilityName = (id: string) => facilities.data?.find((f) => f.id === id)?.name ?? 'Unknown facility';
  const categoryName = (id: string) => categories.data?.find((c) => c.id === id)?.name ?? 'Unknown material';

  return (
    <section aria-labelledby="recovery-title" className="stack stack--tight">
      <PageHeader
        title="Material recovery"
        titleId="recovery-title"
        subtitle="What facilities report recovering from collected material. Only verified records count towards totals."
        actions={can('circular_economy:manage') ? <Button onClick={() => setCreating(true)}>Record recovery</Button> : undefined}
      />
      <QueryBoundary query={summary} label="the recovery summary">
        {(s) => (
          <>
            <div className="grid-3">
              <MetricTile icon={<Recycle size={22} />} label="Recovery rate (verified)" value={percent(s.recovery_rate)} note={`${s.verified_records} verified record${s.verified_records === 1 ? '' : 's'}`} />
              <MetricTile icon={<Recycle size={22} />} tone="blue" label="Recovered weight" value={formatKg(s.recovered_weight_kg)} note={`of ${formatKg(s.input_weight_kg)} processed`} />
              <MetricTile icon={<Recycle size={22} />} tone="amber" label="Awaiting verification" value={String(s.pending_records)} note={`${s.rejected_records} rejected`} />
            </div>
            {s.basis && <p className="muted">{s.basis}</p>}
          </>
        )}
      </QueryBoundary>
      <div className="filter-bar">
        <Field label="Status">
          {(c) => <Select {...c} value={filters.status} onChange={(e) => set({ status: e.target.value })}><option value="">All statuses</option>{VERIFICATION.map((v) => <option key={v} value={v}>{humanize(v)}</option>)}</Select>}
        </Field>
        <Field label="Method">
          {(c) => <Select {...c} value={filters.recovery_method} onChange={(e) => set({ recovery_method: e.target.value })}><option value="">All methods</option>{METHODS.map((m) => <option key={m} value={m}>{humanize(m)}</option>)}</Select>}
        </Field>
        <Field label="Facility">
          {(c) => <Select {...c} value={filters.facility_id} onChange={(e) => set({ facility_id: e.target.value })}><option value="">All facilities</option>{(facilities.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</Select>}
        </Field>
      </div>
      <QueryBoundary query={query} label="recovery records">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<Recycle size={24} />} title="No recovery records" description="Facilities record what was recycled, composted or reused. A different person must verify each record." />
          ) : (
            <>
              <Table caption="Recovery records">
                <thead>
                  <tr>
                    <th scope="col">Processed</th>
                    <th scope="col">Facility</th>
                    <th scope="col">Material</th>
                    <th scope="col">Method</th>
                    <th scope="col">Input</th>
                    <th scope="col">Recovered</th>
                    <th scope="col">Status</th>
                    {can('circular_economy:verify') && <th scope="col"><span className="visually-hidden">Actions</span></th>}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.id}>
                      <td>{formatDateTime(r.processed_at)}</td>
                      <th scope="row">{facilityName(r.facility_id)}</th>
                      <td>{categoryName(r.material_category_id)}</td>
                      <td>{humanize(r.recovery_method)}</td>
                      <td>{formatKg(r.input_weight_kg)}</td>
                      <td>{formatKg(r.recovered_weight_kg)}</td>
                      <td><StatusBadge value={r.verification_status} tones={TONES} /></td>
                      {can('circular_economy:verify') && (
                        <td>{r.verification_status === 'pending' && <Button variant="secondary" onClick={() => setVerifying(r)} aria-label={`Verify record: ${categoryName(r.material_category_id)}, ${formatKg(r.recovered_weight_kg)}`}>Verify</Button>}</td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={data.page} pageCount={Math.max(1, Math.ceil(data.total / data.page_size))} onPageChange={(page) => setFilters((f) => ({ ...f, page }))} summary={`${data.total} record${data.total === 1 ? '' : 's'}`} />
            </>
          )
        }
      </QueryBoundary>
      {creating && <CreateDialog onClose={() => setCreating(false)} />}
      {verifying && <VerifyDialog record={verifying} onClose={() => setVerifying(null)} />}
    </section>
  );
}

function CreateDialog({ onClose }: { onClose: () => void }) {
  const { can } = useAuth();
  const facilities = useFacilityOptions(can('facilities:read'));
  const categories = useCategories(false, can('sorting_guide:read'));
  const create = useCreateRecord();
  const { values, bind } = useFields({ facility: '', category: '', method: 'recycled', input: '', recovered: '', processed: '', notes: '' });
  const input = Number(values.input);
  const recovered = Number(values.recovered);
  const weightsOk = values.input !== '' && values.recovered !== '' && input >= 0 && recovered >= 0 && recovered <= input;
  const valid = values.facility && values.category && weightsOk && values.processed;
  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Record recovery"
      description="Recovered weight cannot exceed the weight processed. The record stays pending until someone else verifies it."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={create.isPending}
            disabled={!valid}
            onClick={() =>
              create.mutate(
                { facility_id: values.facility, material_category_id: values.category, recovery_method: values.method, input_weight_kg: values.input.trim(), recovered_weight_kg: values.recovered.trim(), processed_at: new Date(values.processed).toISOString(), notes: optional(values.notes) },
                { onSuccess: onClose },
              )
            }
          >
            Record recovery
          </Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Facility">{(c) => <Select {...c} data-autofocus {...bind('facility')}><option value="">Choose a facility</option>{(facilities.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</Select>}</Field>
        <Field label="Material">{(c) => <Select {...c} {...bind('category')}><option value="">Choose a material</option>{(categories.data ?? []).map((cat) => <option key={cat.id} value={cat.id}>{cat.name}</option>)}</Select>}</Field>
        <Field label="Method">{(c) => <Select {...c} {...bind('method')}>{METHODS.map((m) => <option key={m} value={m}>{humanize(m)}</option>)}</Select>}</Field>
        <Field label="Processed on">{(c) => <Input {...c} type="datetime-local" {...bind('processed')} />}</Field>
        <Field label="Weight processed (kg)">{(c) => <Input {...c} inputMode="decimal" {...bind('input')} />}</Field>
        <Field label="Weight recovered (kg)" error={values.recovered !== '' && values.input !== '' && !weightsOk ? 'Recovered weight cannot be negative or more than the weight processed.' : undefined}>{(c) => <Input {...c} inputMode="decimal" {...bind('recovered')} />}</Field>
      </div>
      <Field label="Notes (optional)">{(c) => <Textarea {...c} maxLength={2000} {...bind('notes')} />}</Field>
      {create.isError && <Alert tone="danger">{getErrorMessage(create.error)}</Alert>}
    </Dialog>
  );
}

function VerifyDialog({ record, onClose }: { record: Recovery; onClose: () => void }) {
  const verify = useVerifyRecord();
  const { values, bind } = useFields({ decision: 'verified', notes: '' });
  const needsNotes = values.decision === 'rejected';
  return (
    <Dialog
      open
      onClose={onClose}
      title="Verify recovery record"
      description={`${formatKg(record.recovered_weight_kg)} recovered of ${formatKg(record.input_weight_kg)} processed (${humanize(record.recovery_method)}). You cannot verify a record you created.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={verify.isPending} disabled={needsNotes && values.notes.trim().length < 3} onClick={() => verify.mutate({ id: record.id, decision: values.decision as 'verified' | 'rejected', notes: optional(values.notes) }, { onSuccess: onClose })}>
            Save decision
          </Button>
        </>
      }
    >
      <div className="stack stack--tight">
        <Field label="Decision">{(c) => <Select {...c} data-autofocus {...bind('decision')}><option value="verified">Verify</option><option value="rejected">Reject</option></Select>}</Field>
        <Field label={needsNotes ? 'Notes (required)' : 'Notes (optional)'}>{(c) => <Textarea {...c} maxLength={2000} {...bind('notes')} />}</Field>
        {verify.isError && <Alert tone="danger">{getErrorMessage(verify.error)}</Alert>}
      </div>
    </Dialog>
  );
}
