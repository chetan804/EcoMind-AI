import { useState } from 'react';
import { MapPinned } from 'lucide-react';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { optional, useFields } from '@/components/forms/useFields';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Field } from '@/components/ui/Field';
import { Input, SearchInput, Select, Textarea } from '@/components/ui/Input';
import { Pagination, Table } from '@/components/ui/Table';
import { getErrorMessage } from '@/services/error-handler';
import { useAuth } from '@/services/session';
import { humanize } from '@/utils/format';
import { ZONE_TYPES, type Zone } from '../api/zones-api';
import { facilityMarkers, MapPanel } from '@/features/maps';
import { useSaveZone, useZoneFacilities, useZones } from '../hooks/useZones';

export function LocationsPage() {
  const { can } = useAuth();
  const [filters, setFilters] = useState({ page: 1, q: '', zone_type: '', active: '' });
  const [editing, setEditing] = useState<Zone | 'new' | null>(null);
  const [selected, setSelected] = useState<Zone | null>(null);
  const query = useZones(filters);
  const set = (patch: Partial<typeof filters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const manage = can('facilities:manage');

  return (
    <section aria-labelledby="locations-title" className="stack stack--tight">
      <PageHeader
        title="Locations and zones"
        titleId="locations-title"
        subtitle="Named service areas and the facilities in each"
        actions={manage ? <Button onClick={() => setEditing('new')}>Add zone</Button> : undefined}
      />
      <Alert tone="info">
        Zones are named areas. They have no map boundaries because the platform holds no verified map data, so no coverage is shown.
      </Alert>
      <div className="filter-bar">
        <Field label="Search">{(c) => <SearchInput {...c} placeholder="Name or code" value={filters.q} onChange={(e) => set({ q: e.target.value })} />}</Field>
        <Field label="Type">
          {(c) => (
            <Select {...c} value={filters.zone_type} onChange={(e) => set({ zone_type: e.target.value })}>
              <option value="">All types</option>
              {ZONE_TYPES.map((t) => (
                <option key={t} value={t}>{humanize(t)}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Status">
          {(c) => (
            <Select {...c} value={filters.active} onChange={(e) => set({ active: e.target.value })}>
              <option value="">All zones</option>
              <option value="true">Active</option>
              <option value="false">Retired</option>
            </Select>
          )}
        </Field>
      </div>
      <QueryBoundary query={query} label="zones">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<MapPinned size={24} />} title="No zones found" description={manage ? 'Add a zone, then assign facilities to it from the facility form.' : 'No zone matches these filters.'} />
          ) : (
            <>
              <Table caption="Zones">
                <thead>
                  <tr>
                    <th scope="col">Zone</th>
                    <th scope="col">Type</th>
                    <th scope="col">Facilities</th>
                    <th scope="col">Status</th>
                    <th scope="col"><span className="visually-hidden">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((z) => (
                    <tr key={z.id}>
                      <th scope="row">
                        {z.name}
                        <p className="muted">{z.code}{z.description ? ` · ${z.description}` : ''}</p>
                      </th>
                      <td>{humanize(z.zone_type)}</td>
                      <td>{z.facility_count}</td>
                      <td><Badge tone={z.is_active ? 'success' : 'neutral'}>{z.is_active ? 'Active' : 'Retired'}</Badge></td>
                      <td>
                        <div className="row-actions">
                          <Button variant="secondary" onClick={() => setSelected(z)} aria-label={`Show facilities in ${z.name}`}>Facilities</Button>
                          {manage && <Button variant="secondary" onClick={() => setEditing(z)} aria-label={`Edit ${z.name}`}>Edit</Button>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination
                page={data.page}
                pageCount={Math.max(1, Math.ceil(data.total / data.page_size))}
                onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
                summary={`${data.total} zone${data.total === 1 ? '' : 's'}`}
              />
            </>
          )
        }
      </QueryBoundary>
      {selected && <ZoneFacilities zone={selected} />}
      {editing && <ZoneDialog key={editing === 'new' ? 'new' : editing.id} zone={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </section>
  );
}

function ZoneFacilities({ zone }: { zone: Zone }) {
  const query = useZoneFacilities(zone.id);
  return (
    <div className="stack stack--tight" aria-live="polite">
      <h2>Facilities in {zone.name}</h2>
      <QueryBoundary query={query} label="facilities in this zone">
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState icon={<MapPinned size={24} />} title="No facilities in this zone" description="Assign a facility to this zone from the facility form." />
          ) : (
            <>
            <MapPanel label={`Facilities in ${zone.name}`} markers={facilityMarkers(data.items)} height={300} emptyMessage="None of these facilities has coordinates yet." />
            <p className="muted">Zones have no recorded boundary data, so only the located facilities of this zone are drawn. No boundary or area is implied.</p>
            <Table caption={`Facilities in ${zone.name}`}>
              <thead>
                <tr>
                  <th scope="col">Facility</th>
                  <th scope="col">Type</th>
                  <th scope="col">City</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((f) => (
                  <tr key={f.id}>
                    <th scope="row">{f.name}<p className="muted">{f.code}</p></th>
                    <td>{humanize(f.facility_type)}</td>
                    <td>{f.city ?? 'Not set'}</td>
                    <td>{humanize(f.status)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
            </>
          )
        }
      </QueryBoundary>
    </div>
  );
}

function ZoneDialog({ zone, onClose }: { zone: Zone | null; onClose: () => void }) {
  const save = useSaveZone();
  const { values, bind } = useFields({
    code: zone?.code ?? '',
    name: zone?.name ?? '',
    zone_type: zone?.zone_type ?? 'mixed_use',
    description: zone?.description ?? '',
    is_active: zone?.is_active === false ? 'false' : 'true',
  });
  const valid = values.name.trim().length >= 2 && (zone !== null || values.code.trim().length >= 2);

  const submit = () => {
    const body: Record<string, unknown> = {
      name: values.name.trim(),
      zone_type: values.zone_type,
      description: optional(values.description) ?? null,
    };
    if (zone) body.is_active = values.is_active === 'true';
    else body.code = values.code.trim();
    save.mutate({ id: zone?.id, body }, { onSuccess: onClose });
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={zone ? `Edit ${zone.name}` : 'Add zone'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={save.isPending} disabled={!valid} onClick={submit}>{zone ? 'Save changes' : 'Add zone'}</Button>
        </>
      }
    >
      <div className="form-grid">
        {!zone && <Field label="Code" hint="2-32 letters, digits, - or _">{(c) => <Input {...c} data-autofocus {...bind('code')} />}</Field>}
        <Field label="Name">{(c) => <Input {...c} data-autofocus={zone ? true : undefined} {...bind('name')} />}</Field>
        <Field label="Type">
          {(c) => (
            <Select {...c} {...bind('zone_type')}>
              {ZONE_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
            </Select>
          )}
        </Field>
        {zone && (
          <Field label="Status">
            {(c) => (
              <Select {...c} {...bind('is_active')}>
                <option value="true">Active</option>
                <option value="false">Retired</option>
              </Select>
            )}
          </Field>
        )}
        <Field label="Description (optional)">{(c) => <Textarea {...c} {...bind('description')} />}</Field>
      </div>
      {save.isError && <Alert tone="danger">{getErrorMessage(save.error)}</Alert>}
    </Dialog>
  );
}
