import { useState } from 'react';
import { Building2 } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, SearchInput, Select } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Pagination, Table } from '@/components/ui/Table';
import { getErrorMessage } from '@/services/error-handler';
import { useZoneOptions } from '@/features/locations';
import { directionsUrl, facilityMarkers, LocationPicker, MapPanel, toPoint } from '@/features/maps';
import { useAuth } from '@/services/session';
import { formatNumber, humanize } from '@/utils/format';
import { FACILITY_STATUSES, FACILITY_TYPES, type Facility } from '../api/facilities-api';
import { useFacilities, useSaveFacility } from '../hooks/useFacilities';

const STATUS_TONES: Record<string, BadgeTone> = { active: 'success', inactive: 'neutral', maintenance: 'warning' };

export function FacilitiesPage() {
  const { can } = useAuth();
  const [filters, setFilters] = useState({ page: 1, q: '', facility_type: '', status: '' });
  const [editing, setEditing] = useState<Facility | 'new' | null>(null);
  const query = useFacilities(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const manage = can('facilities:manage');

  return (
    <section aria-labelledby="facilities-title" className="stack stack--tight">
      <PageHeader
        title="Processing facilities and depots"
        titleId="facilities-title"
        subtitle="Where material is delivered, processed and recovered"
        actions={manage ? <Button onClick={() => setEditing('new')}>Add facility</Button> : undefined}
      />
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Name or code" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Type">
          {(c) => (
            <Select {...c} value={filters.facility_type} onChange={(e) => set({ facility_type: e.target.value })}>
              <option value="">All types</option>
              {FACILITY_TYPES.map((t) => (
                <option key={t} value={t}>{humanize(t)}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Status">
          {(c) => (
            <Select {...c} value={filters.status} onChange={(e) => set({ status: e.target.value })}>
              <option value="">All statuses</option>
              {FACILITY_STATUSES.map((s) => (
                <option key={s} value={s}>{humanize(s)}</option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <QueryBoundary query={query} label="facilities">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<Building2 size={24} />} title="No facilities found" description={manage ? 'Add a depot or processing centre to start routing collections to it.' : 'No facility matches these filters.'} />
          ) : (
            <>
              <Table caption="Facilities">
                <thead>
                  <tr>
                    <th scope="col">Facility</th>
                    <th scope="col">Type</th>
                    <th scope="col">Location</th>
                    <th scope="col">Daily capacity</th>
                    <th scope="col">Status</th>
                    {manage && <th scope="col"><span className="visually-hidden">Actions</span></th>}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((f) => (
                    <tr key={f.id}>
                      <th scope="row">
                        {f.name}
                        <p className="muted">{f.code}</p>
                      </th>
                      <td>{humanize(f.facility_type)}</td>
                      <td>
                        {[f.address_line, f.city, f.region, f.country_code].filter(Boolean).join(', ') || <Badge tone="neutral">No address</Badge>}
                        {toPoint(f.latitude, f.longitude) && (
                          <p>
                            <a href={directionsUrl(toPoint(f.latitude, f.longitude) as { lat: number; lng: number })} target="_blank" rel="noopener noreferrer">
                              Directions<span className="visually-hidden"> to {f.name} (opens Google Maps in a new tab)</span>
                            </a>
                          </p>
                        )}
                      </td>
                      <td>{f.daily_capacity_kg === null ? 'Not set' : `${formatNumber(f.daily_capacity_kg)} kg`}</td>
                      <td><StatusBadge value={f.status} tones={STATUS_TONES} /></td>
                      {manage && (
                        <td>
                          <Button variant="secondary" onClick={() => setEditing(f)} aria-label={`Edit ${f.name}`}>Edit</Button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </Table>
              {facilityMarkers(data.items).length > 0 && (
                <MapPanel label="Facilities on this page" markers={facilityMarkers(data.items)} height={320} />
              )}
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} facilit${data.total === 1 ? 'y' : 'ies'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {editing && <FacilityDialog key={editing === 'new' ? 'new' : editing.id} facility={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </section>
  );
}

function FacilityDialog({ facility, onClose }: { facility: Facility | null; onClose: () => void }) {
  const save = useSaveFacility();
  const zones = useZoneOptions();
  const [locationInvalid, setLocationInvalid] = useState(false);
  const { values, bind, set } = useFields({
    code: facility?.code ?? '',
    name: facility?.name ?? '',
    facility_type: facility?.facility_type ?? 'depot',
    status: facility?.status ?? 'active',
    address_line: facility?.address_line ?? '',
    city: facility?.city ?? '',
    region: facility?.region ?? '',
    country_code: facility?.country_code ?? '',
    latitude: facility?.latitude?.toString() ?? '',
    longitude: facility?.longitude?.toString() ?? '',
    daily_capacity_kg: facility?.daily_capacity_kg?.toString() ?? '',
    contact_email: facility?.contact_email ?? '',
    zone_id: facility?.zone_id ?? '',
  });
  const valid = values.name.trim().length >= 2 && (facility !== null || values.code.trim().length >= 2) && !locationInvalid;

  const submit = () => {
    const body: Record<string, unknown> = {
      name: values.name.trim(),
      facility_type: values.facility_type,
      status: values.status,
      address_line: optional(values.address_line) ?? null,
      city: optional(values.city) ?? null,
      region: optional(values.region) ?? null,
      country_code: optional(values.country_code) ?? null,
      latitude: optional(values.latitude) ?? null,
      longitude: optional(values.longitude) ?? null,
      daily_capacity_kg: optional(values.daily_capacity_kg) ?? null,
      contact_email: optional(values.contact_email) ?? null,
      zone_id: optional(values.zone_id) ?? null,
    };
    if (!facility) body.code = values.code.trim();
    save.mutate({ id: facility?.id, body }, { onSuccess: onClose });
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={facility ? `Edit ${facility.name}` : 'Add facility'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={save.isPending} disabled={!valid} onClick={submit}>{facility ? 'Save changes' : 'Add facility'}</Button>
        </>
      }
    >
      <div className="form-grid">
        {!facility && <Field label="Code" hint="2-32 letters, digits, - or _">{(c) => <Input {...c} data-autofocus {...bind('code')} />}</Field>}
        <Field label="Name">{(c) => <Input {...c} data-autofocus={facility ? true : undefined} {...bind('name')} />}</Field>
        <Field label="Type">
          {(c) => (
            <Select {...c} {...bind('facility_type')}>
              {FACILITY_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Status">
          {(c) => (
            <Select {...c} {...bind('status')}>
              {FACILITY_STATUSES.map((s) => <option key={s} value={s}>{humanize(s)}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Zone" hint={zones.isError ? 'Zones could not be loaded' : undefined}>
          {(c) => (
            <Select {...c} {...bind('zone_id')}>
              <option value="">No zone</option>
              {(zones.data ?? []).map((z) => <option key={z.id} value={z.id}>{z.name} ({z.code})</option>)}
              {facility?.zone_id && !(zones.data ?? []).some((z) => z.id === facility.zone_id) && <option value={facility.zone_id}>Current zone (retired)</option>}
            </Select>
          )}
        </Field>
        <Field label="Address">{(c) => <Input {...c} {...bind('address_line')} />}</Field>
        <Field label="City">{(c) => <Input {...c} {...bind('city')} />}</Field>
        <Field label="Region">{(c) => <Input {...c} {...bind('region')} />}</Field>
        <Field label="Country code" hint="Two letters, for example IN">{(c) => <Input {...c} maxLength={2} {...bind('country_code')} />}</Field>
        <Field label="Daily capacity (kg)">{(c) => <Input {...c} inputMode="decimal" {...bind('daily_capacity_kg')} />}</Field>
        <Field label="Contact email">{(c) => <Input {...c} type="email" {...bind('contact_email')} />}</Field>
      </div>
      <fieldset className="stack stack--tight">
        <legend>Location (optional)</legend>
        <LocationPicker
          label="Facility location"
          value={values.latitude && values.longitude ? { lat: Number(values.latitude), lng: Number(values.longitude) } : null}
          onChange={(point) => set({ latitude: point ? point.lat.toFixed(6) : '', longitude: point ? point.lng.toFixed(6) : '' })}
          onInvalidChange={setLocationInvalid}
        />
      </fieldset>
      {save.isError && <Alert tone="danger">{getErrorMessage(save.error)}</Alert>}
    </Dialog>
  );
}
