/* Routes: list, generation wizard, execution detail. */

import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { CheckCircle2, CircleDot, Compass, Gauge, MapPin, Play, Plus, Route as RouteIcon, Timer, Trash2 } from 'lucide-react'
import { get, patch, post } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, EmptyState, ErrorNote, Field, Modal, Panel, PanelHeader, Spinner, StatusBadge, Toast } from '../ui'
import { fmtDate, fmtDuration, humanize } from '../lib/format'
import { MapView, type MapPoint, type MapZone } from '../map'

interface RouteListItem {
  id: string
  code: string
  name: string
  service_date: string
  status: string
  total_distance_km: number | null
  total_duration_min: number | null
  stops_count: number
  optimization: Record<string, unknown>
  vehicle_id: string | null
}

interface VehicleItem { id: string; code: string; name: string | null; capacity_kg: number | null; fuel_type: string }
interface DriverItem { user_id: string; full_name: string | null }
interface ZoneItem { id: string; name: string; color_hex: string; boundary: { coordinates: [number, number][][] } }

export function RoutesPage() {
  const { orgId, hasPerm } = useAuth()
  const queryClient = useQueryClient()
  const [wizardOpen, setWizardOpen] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const routesQ = useQuery({ queryKey: ['routes'], queryFn: () => get<RouteListItem[]>('/routes'), enabled: !!orgId })

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight md:text-2xl">Routes</h1>
          <p className="mt-1 text-sm text-[var(--color-mute)]">
            Optimized with OR-Tools (capacitated VRP) · road geometry via OSRM or clearly-labelled estimates
          </p>
        </div>
        {hasPerm('route:generate') && (
          <button className="btn btn-primary" onClick={() => setWizardOpen(true)}><Plus size={15} /> Generate route</button>
        )}
      </div>

      <Panel>
        {routesQ.data?.length ? (
          <div className="divide-y divide-[var(--color-line)]">
            {routesQ.data.map((r) => (
              <a key={r.id} href={`#/ops/routes/${r.id}`} className="table-row flex flex-wrap items-center gap-4 px-5 py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400"><RouteIcon size={17} /></div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold">{r.name}</p>
                  <p className="mt-0.5 text-[11px] text-[var(--color-faint)]">
                    {r.code} · {fmtDate(r.service_date)} · {r.stops_count} stops
                    {r.total_distance_km ? ` · ${r.total_distance_km.toFixed(1)} km` : ''}
                    {r.total_duration_min ? ` · ${fmtDuration(r.total_duration_min)}` : ''}
                  </p>
                </div>
                {Boolean(r.optimization?.geometry_estimated) && <Badge tone="warn">est. geometry</Badge>}
                <StatusBadge status={r.status} />
              </a>
            ))}
          </div>
        ) : (
          <EmptyState icon={<RouteIcon size={30} />} title="No routes yet" hint="Generate your first optimized route from your collection points and fleet." />
        )}
      </Panel>

      {wizardOpen && <GenerateWizard onClose={() => setWizardOpen(false)} onDone={() => { setWizardOpen(false); queryClient.invalidateQueries({ queryKey: ['routes'] }); setToast('Route generated'); setTimeout(() => setToast(null), 2500) }} />}
      {toast && <Toast message={toast} />}
    </div>
  )
}

function GenerateWizard({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { orgId } = useAuth()
  const [name, setName] = useState('')
  const [zoneId, setZoneId] = useState('')
  const [serviceDate, setServiceDate] = useState(new Date().toISOString().slice(0, 10))
  const [vehicleIds, setVehicleIds] = useState<string[]>([])
  const [driverId, setDriverId] = useState('')
  const [depotLat, setDepotLat] = useState('12.9568')
  const [depotLng, setDepotLng] = useState('77.6010')
  const [error, setError] = useState<string | null>(null)

  const zonesQ = useQuery({ queryKey: ['zones'], queryFn: () => get<ZoneItem[]>('/organizations/current/zones'), enabled: !!orgId })
  const vehiclesQ = useQuery({ queryKey: ['vehicles'], queryFn: () => get<VehicleItem[]>('/fleet/vehicles'), enabled: !!orgId })
  const driversQ = useQuery({ queryKey: ['drivers'], queryFn: () => get<DriverItem[]>('/fleet/drivers'), enabled: !!orgId })

  const generate = useMutation({
    mutationFn: () =>
      post('/routes/generate', {
        name: name || 'Collection round',
        service_date: serviceDate,
        depot_lat: parseFloat(depotLat),
        depot_lng: parseFloat(depotLng),
        zone_id: zoneId || null,
        vehicle_ids: vehicleIds.length ? vehicleIds : null,
        driver_user_id: driverId || null,
      }),
    onSuccess: onDone,
    onError: (e: Error) => setError(e.message),
  })

  return (
    <Modal open onClose={onClose} title="Generate optimized route" wide>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Route name">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Morning round — Riverline" />
        </Field>
        <Field label="Service date">
          <input className="input" type="date" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} />
        </Field>
        <Field label="Zone (optional)">
          <select className="input" value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
            <option value="">All zones</option>
            {zonesQ.data?.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
          </select>
        </Field>
        <Field label="Assign driver (optional)">
          <select className="input" value={driverId} onChange={(e) => setDriverId(e.target.value)}>
            <option value="">Unassigned</option>
            {driversQ.data?.map((d) => <option key={d.user_id} value={d.user_id}>{d.full_name}</option>)}
          </select>
        </Field>
        <Field label="Depot latitude" hint="Route start/end point">
          <input className="input" type="number" step="0.0001" value={depotLat} onChange={(e) => setDepotLat(e.target.value)} />
        </Field>
        <Field label="Depot longitude">
          <input className="input" type="number" step="0.0001" value={depotLng} onChange={(e) => setDepotLng(e.target.value)} />
        </Field>
        <div className="sm:col-span-2">
          <p className="label">Vehicles (leave empty for all active)</p>
          <div className="flex flex-wrap gap-2">
            {vehiclesQ.data?.map((v) => (
              <button key={v.id} type="button"
                onClick={() => setVehicleIds((s) => (s.includes(v.id) ? s.filter((x) => x !== v.id) : [...s, v.id]))}
                className={clsx('chip border', vehicleIds.includes(v.id) ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300' : 'border-[var(--color-line)] text-[var(--color-mute)]')}>
                {v.code} {v.capacity_kg ? `· ${v.capacity_kg} kg` : ''} · {humanize(v.fuel_type)}
              </button>
            ))}
          </div>
        </div>
        <div className="sm:col-span-2">
          <ErrorNote message={error} />
          <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-base)] p-3 text-[11px] leading-relaxed text-[var(--color-faint)]">
            The optimizer solves a capacitated vehicle-routing problem over your collection points
            (fill-level weighted demand from smart bins when available), respects vehicle capacity,
            and returns stop sequencing with solver provenance. Road geometry comes from OSRM when
            configured; otherwise a straight-line estimate (×1.3 road factor) is stored and labelled.
          </div>
        </div>
        <button className="btn btn-primary btn-lg sm:col-span-2" disabled={generate.isPending} onClick={() => generate.mutate()}>
          {generate.isPending ? <Spinner /> : <Compass size={16} />} Optimize & create route
        </button>
      </div>
    </Modal>
  )
}

/* ------------------------------------------------------------------ detail */

interface StopDetail {
  id: string
  sequence_no: number
  point_name: string | null
  point_code: string | null
  latitude: number | null
  longitude: number | null
  address: string | null
  status: string
  priority: number
  planned_arrival_offset_min: number | null
  weight_kg: number | null
  skip_reason: string | null
  contamination_flag: boolean
  notes: string | null
}

interface RouteFull extends RouteListItem {
  depot_lat: number
  depot_lng: number
  geometry: { type: string; coordinates: [number, number][] } | null
  geometry_is_estimated: boolean
  planned_weight_kg: number | null
  stops: StopDetail[]
  completed_stops: number
  driver_user_id: string | null
}

export function RouteDetailPage() {
  const { orgId, hasPerm } = useAuth()
  const { id: routeId } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [toast, setToast] = useState<string | null>(null)

  const q = useQuery({ queryKey: ['route', routeId], queryFn: () => get<RouteFull>(`/routes/${routeId}`), enabled: !!orgId && !!routeId })

  const statusMutation = useMutation({
    mutationFn: (status: string) => patch(`/routes/${routeId}/status`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['route', routeId] })
      queryClient.invalidateQueries({ queryKey: ['routes'] })
      setToast('Route status updated')
      setTimeout(() => setToast(null), 2000)
    },
  })

  const r = q.data

  const mapPoints = useMemo<MapPoint[]>(() => {
    if (!r) return []
    const pts: MapPoint[] = [{ id: 'depot', lat: r.depot_lat, lng: r.depot_lng, title: 'Depot', kind: 'facility' }]
    for (const s of r.stops) {
      if (s.latitude == null || s.longitude == null) continue
      pts.push({
        id: s.id, lat: s.latitude, lng: s.longitude, kind: s.status === 'completed' ? 'facility' : 'bin',
        title: `${s.sequence_no}. ${s.point_name ?? ''}`, status: humanize(s.status),
      })
    }
    return pts
  }, [r])

  if (q.isLoading || !r) {
    return <div className="flex min-h-[50vh] items-center justify-center"><Spinner className="text-emerald-400" /></div>
  }

  const opt = r.optimization as {
    solver?: string; solver_status?: string; solve_ms?: number; geometry_estimated?: boolean
    geometry_provider?: string; road_distance_factor?: number; unassigned_stops?: string[]; vehicles_used?: number
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight md:text-2xl">{r.name}</h1>
            <StatusBadge status={r.status} />
          </div>
          <p className="mt-1 text-sm text-[var(--color-mute)]">
            {r.code} · {fmtDate(r.service_date)} · {r.stops_count} stops · {r.completed_stops} done
          </p>
        </div>
        {hasPerm('route:assign') && r.status === 'draft' && (
          <button className="btn btn-primary" onClick={() => statusMutation.mutate('approved')}><CheckCircle2 size={15} /> Approve</button>
        )}
        {hasPerm('route:execute') && r.status === 'approved' && (
          <button className="btn btn-primary" onClick={() => statusMutation.mutate('in_progress')}><Play size={15} /> Start</button>
        )}
        {hasPerm('route:assign') && r.status === 'in_progress' && (
          <button className="btn btn-ghost" onClick={() => statusMutation.mutate('completed')}><CheckCircle2 size={15} /> Complete</button>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel className="overflow-hidden lg:col-span-2">
          <MapView
            className="h-[420px] rounded-none border-0"
            points={mapPoints}
            routes={r.geometry ? [{ id: r.id, coordinates: r.geometry.coordinates.map(([lng, lat]) => [lat, lng]), estimated: r.geometry_is_estimated }] : []}
            fit
          />
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel className="p-5">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Gauge size={15} className="text-emerald-400" /> Plan</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><p className="text-[11px] text-[var(--color-faint)]">Distance</p><p className="font-semibold">{r.total_distance_km?.toFixed(1) ?? '—'} km</p></div>
              <div><p className="text-[11px] text-[var(--color-faint)]">Duration</p><p className="font-semibold">{fmtDuration(r.total_duration_min)}</p></div>
              <div><p className="text-[11px] text-[var(--color-faint)]">Planned load</p><p className="font-semibold">{r.planned_weight_kg?.toFixed(0) ?? '—'} kg</p></div>
              <div><p className="text-[11px] text-[var(--color-faint)]">Progress</p><p className="font-semibold">{r.completed_stops}/{r.stops_count}</p></div>
            </div>
          </Panel>

          <Panel className="p-5">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Compass size={15} className="text-emerald-400" /> Solver provenance</h3>
            <div className="flex flex-col gap-2 text-xs text-[var(--color-mute)]">
              <div className="flex justify-between"><span>Solver</span><span className="font-mono">{opt.solver ?? '—'}</span></div>
              <div className="flex justify-between"><span>Status</span><span className="font-mono">{opt.solver_status ?? '—'}</span></div>
              <div className="flex justify-between"><span>Solve time</span><span className="font-mono">{opt.solve_ms ?? '—'} ms</span></div>
              <div className="flex justify-between"><span>Vehicles used</span><span className="font-mono">{opt.vehicles_used ?? '—'}</span></div>
              <div className="flex items-center justify-between"><span>Geometry</span>{r.geometry_is_estimated ? <Badge tone="warn">estimated ×{opt.road_distance_factor ?? 1.3}</Badge> : <Badge tone="brand">{opt.geometry_provider ?? 'OSRM'} roads</Badge>}</div>
              {!!opt.unassigned_stops?.length && (
                <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-amber-300">
                  {opt.unassigned_stops.length} stop(s) could not be serviced within capacity and were left unassigned.
                </p>
              )}
            </div>
          </Panel>
        </div>
      </div>

      <Panel className="mt-4">
        <PanelHeader title="Stops" subtitle="Execution order and field status" icon={<MapPin size={15} />} />
        <div className="divide-y divide-[var(--color-line)]">
          {r.stops.map((s) => (
            <div key={s.id} className="table-row flex items-center gap-4 px-5 py-3">
              <span className={clsx('flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold',
                s.status === 'completed' ? 'bg-emerald-500/20 text-emerald-300'
                  : s.status === 'skipped' ? 'bg-amber-500/20 text-amber-300'
                  : 'bg-[var(--color-line)] text-[var(--color-mute)]')}>
                {s.sequence_no}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{s.point_name ?? 'Stop'}</p>
                <p className="truncate text-[11px] text-[var(--color-faint)]">
                  {s.address ?? `${s.latitude?.toFixed(4)}, ${s.longitude?.toFixed(4)}`}
                  {s.weight_kg ? ` · ${s.weight_kg} kg` : ''}
                  {s.skip_reason ? ` · ${humanize(s.skip_reason)}` : ''}
                </p>
              </div>
              {s.priority > 0 && <Badge tone="danger">priority</Badge>}
              {s.contamination_flag && <Badge tone="warn">contaminated</Badge>}
              <StatusBadge status={s.status} />
            </div>
          ))}
        </div>
      </Panel>
      {toast && <Toast message={toast} />}
    </div>
  )
}
