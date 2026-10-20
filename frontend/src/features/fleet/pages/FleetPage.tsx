import { useState } from 'react';
import { Truck } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import type { BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, SearchInput, Select } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { useFacilityOptions } from '@/features/facilities';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { formatKg, humanize } from '@/utils/format';
import { VEHICLE_STATUSES, VEHICLE_TYPES, type Vehicle } from '../api/fleet-api';
import { useSaveVehicle, useVehicles } from '../hooks/useFleet';

const STATUS_TONES: Record<string, BadgeTone> = { available: 'success', in_service: 'info', maintenance: 'warning', retired: 'neutral' };

export function FleetPage() {
  const { can } = useAuth();
  const [filters, setFilters] = useState({ page: 1, q: '', vehicle_type: '', status: '' });
  const [editing, setEditing] = useState<Vehicle | 'new' | null>(null);
  const query = useVehicles(filters);
  const facilities = useFacilityOptions(can('facilities:read'));
  const manage = can('fleet:manage');
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const facilityName = (id: string | null) => (id ? (facilities.data?.find((f) => f.id === id)?.name ?? 'Unknown facility') : '—');

  return (
    <section aria-labelledby="fleet-title" className="stack stack--tight">
      <PageHeader
        title="Collection fleet vehicles"
        titleId="fleet-title"
        subtitle="Vehicles available for collection work"
        actions={manage ? <Button onClick={() => setEditing('new')}>Add vehicle</Button> : undefined}
      />
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Registration number" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Type">
          {(c) => (
            <Select {...c} value={filters.vehicle_type} onChange={(e) => set({ vehicle_type: e.target.value })}>
              <option value="">All types</option>
              {VEHICLE_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Status">
          {(c) => (
            <Select {...c} value={filters.status} onChange={(e) => set({ status: e.target.value })}>
              <option value="">All statuses</option>
              {VEHICLE_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
            </Select>
          )}
        </Field>
      </div>
      <QueryBoundary query={query} label="vehicles">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<Truck size={24} />} title="No vehicles found" description={manage ? 'Add a vehicle so tasks can be assigned to it.' : 'No vehicle matches these filters.'} />
          ) : (
            <>
              <Table caption="Fleet vehicles">
                <thead>
                  <tr>
                    <th scope="col">Registration</th>
                    <th scope="col">Type</th>
                    <th scope="col">Capacity</th>
                    <th scope="col">Home depot</th>
                    <th scope="col">Active tasks</th>
                    <th scope="col">Status</th>
                    {manage && <th scope="col"><span className="visually-hidden">Actions</span></th>}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((v) => (
                    <tr key={v.id}>
                      <th scope="row">{v.registration_number}</th>
                      <td>{humanize(v.vehicle_type)}</td>
                      <td>{formatKg(v.capacity_kg)}</td>
                      <td>{facilityName(v.home_facility_id)}</td>
                      <td>{v.active_task_count ?? 0}</td>
                      <td><StatusBadge value={v.status} tones={STATUS_TONES} /></td>
                      {manage && <td><Button variant="secondary" onClick={() => setEditing(v)} aria-label={`Edit ${v.registration_number}`}>Edit</Button></td>}
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} vehicle${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {editing && <VehicleDialog key={editing === 'new' ? 'new' : editing.id} vehicle={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </section>
  );
}

function VehicleDialog({ vehicle, onClose }: { vehicle: Vehicle | null; onClose: () => void }) {
  const { can } = useAuth();
  const save = useSaveVehicle();
  const facilities = useFacilityOptions(can('facilities:read'));
  const { values, bind } = useFields({
    registration_number: vehicle?.registration_number ?? '',
    vehicle_type: vehicle?.vehicle_type ?? 'compactor_truck',
    status: vehicle?.status ?? 'available',
    capacity_kg: vehicle?.capacity_kg.toString() ?? '',
    home_facility_id: vehicle?.home_facility_id ?? '',
  });
  const capacity = Number(values.capacity_kg);
  const valid = (vehicle !== null || values.registration_number.trim().length >= 2) && capacity > 0;
  const submit = () => {
    const body: Record<string, unknown> = {
      vehicle_type: values.vehicle_type,
      status: values.status,
      capacity_kg: values.capacity_kg.trim(),
      home_facility_id: values.home_facility_id || null,
    };
    if (!vehicle) body.registration_number = values.registration_number.trim();
    save.mutate({ id: vehicle?.id, body }, { onSuccess: onClose });
  };
  return (
    <Dialog
      open
      onClose={onClose}
      title={vehicle ? `Edit ${vehicle.registration_number}` : 'Add vehicle'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={save.isPending} disabled={!valid} onClick={submit}>{vehicle ? 'Save changes' : 'Add vehicle'}</Button>
        </>
      }
    >
      <div className="stack stack--tight">
        {!vehicle && <Field label="Registration number">{(c) => <Input {...c} data-autofocus {...bind('registration_number')} />}</Field>}
        <Field label="Type">
          {(c) => <Select {...c} {...bind('vehicle_type')}>{VEHICLE_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}</Select>}
        </Field>
        <Field label="Status">
          {(c) => <Select {...c} {...bind('status')}>{VEHICLE_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}</Select>}
        </Field>
        <Field label="Capacity (kg)">{(c) => <Input {...c} inputMode="decimal" data-autofocus={vehicle ? true : undefined} {...bind('capacity_kg')} />}</Field>
        <Field label="Home depot">
          {(c) => (
            <Select {...c} {...bind('home_facility_id')}>
              <option value="">None</option>
              {(facilities.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </Select>
          )}
        </Field>
        {save.isError && <Alert tone="danger">{getErrorMessage(save.error)}</Alert>}
      </div>
    </Dialog>
  );
}
