/* Operations command center: live map, alerts, dispatch overview. */

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import {
  Activity, AlertTriangle, CheckCircle2, CircleDot, Compass, Radio, Route as RouteIcon,
  Trash2, Truck, Wifi, WifiOff,
} from 'lucide-react'
import { get, patch, post } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, DemoBadge, EmptyState, Modal, Panel, PanelHeader, SimBadge, Spinner, StatCard, StatusBadge, Toast } from '../ui'
import { fmtKg, fmtPct, humanize, timeAgo } from '../lib/format'
import { MapLegend, MapView, type MapPoint, type MapRoute, type MapZone } from '../map'

interface Device {
  id: string
  device_key: string
  name: string
  kind: string
  status: string
  collection_point_id: string | null
  zone_id: string | null
  latitude: number | null
  longitude: number | null
  current_fill_pct: number | null
  current_temperature_c: number | null
  current_battery_pct: number | null
  last_telemetry_at: string | null
  is_simulated: boolean
}

interface AlertItem {
  id: string
  severity: string
  title: string
  message: string | null
  status: string
  triggered_at: string
  device_id: string | null
  metadata: Record<string, unknown>
}

interface VehicleItem {
  id: string
  code: string
  name: string | null
  status: string
  fuel_type: string
  current_lat: number | null
  current_lng: number | null
  current_route_id: string | null
  last_ping_at: string | null
  position_is_simulated: boolean
}

type Layer = 'bins' | 'reports' | 'complaints' | 'vehicles' | 'routes' | 'zones'

export function CommandCenterPage() {
  const { orgId, isDemo, hasPerm } = useAuth()
  const queryClient = useQueryClient()
  const [layers, setLayers] = useState<Record<Layer, boolean>>({
    bins: true, reports: true, complaints: true, vehicles: true, routes: true, zones: true,
  })
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const opsQ = useQuery({ queryKey: ['ops-dash'], queryFn: () => get('/analytics/operations'), enabled: !!orgId, refetchInterval: 20000 })
  const devicesQ = useQuery({ queryKey: ['devices'], queryFn: () => get<Device[]>('/iot/devices'), enabled: !!orgId && hasPerm('device:read'), refetchInterval: 15000 })
  const vehiclesQ = useQuery({ queryKey: ['vehicles'], queryFn: () => get<VehicleItem[]>('/fleet/vehicles'), enabled: !!orgId && hasPerm('fleet:read'), refetchInterval: 15000 })
  const alertsQ = useQuery({ queryKey: ['alerts'], queryFn: () => get<{ items: AlertItem[] }>('/iot/alerts?status_filter=open'), enabled: !!orgId && hasPerm('alert:read'), refetchInterval: 15000 })
  const reportsQ = useQuery({ queryKey: ['ops-reports-map'], queryFn: () => get<{ items: MapReport[] }>('/waste/reports?page_size=100'), enabled: !!orgId && hasPerm('report:read_all'), refetchInterval: 30000 })
  const complaintsQ = useQuery({ queryKey: ['complaints-map'], queryFn: () => get<{ items: MapComplaint[] }>('/complaints?page_size=100'), enabled: !!orgId && hasPerm('complaint:read_all'), refetchInterval: 30000 })
  const zonesQ = useQuery({ queryKey: ['zones'], queryFn: () => get<ZoneRow[]>('/organizations/current/zones'), enabled: !!orgId })
  const routesQ = useQuery({ queryKey: ['routes-map'], queryFn: () => get<MapRouteRow[]>('/routes'), enabled: !!orgId && hasPerm('route:read') })

  const alertMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => patch(`/iot/alerts/${id}`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedAlert(null)
      setToast('Alert updated')
      setTimeout(() => setToast(null), 2000)
    },
  })

  const d = opsQ.data as OperationsDash | undefined

  const mapPoints = useMemo(() => {
    const pts: MapPoint[] = []
    if (layers.bins) {
      for (const dev of devicesQ.data ?? []) {
        if (dev.latitude == null || dev.longitude == null) continue
        pts.push({
          id: dev.id, lat: dev.latitude, lng: dev.longitude, kind: 'bin',
          title: dev.name, status: `fill ${dev.current_fill_pct?.toFixed(0) ?? '—'}%`,
          fillPct: dev.current_fill_pct, simulated: dev.is_simulated,
        })
      }
    }
    if (layers.reports) {
      for (const r of reportsQ.data?.items ?? []) {
        pts.push({
          id: r.id, lat: r.latitude, lng: r.longitude, kind: 'report',
          title: r.description?.slice(0, 60) ?? 'Waste report',
          status: humanize(r.status),
        })
      }
    }
    if (layers.complaints) {
      for (const c of complaintsQ.data?.items ?? []) {
        if (c.latitude == null || c.longitude == null) continue
        pts.push({ id: c.id, lat: c.latitude, lng: c.longitude, kind: 'complaint', title: c.subject, status: humanize(c.status) })
      }
    }
    if (layers.vehicles) {
      for (const v of vehiclesQ.data ?? []) {
        if (v.current_lat == null || v.current_lng == null) continue
        pts.push({
          id: v.id, lat: v.current_lat, lng: v.current_lng, kind: 'vehicle',
          title: `${v.code}${v.name ? ` · ${v.name}` : ''}`, status: humanize(v.status),
          simulated: v.position_is_simulated,
        })
      }
    }
    return pts
  }, [layers, devicesQ.data, reportsQ.data, complaintsQ.data, vehiclesQ.data])

  const mapRoutes = useMemo<MapRoute[]>(
    () =>
      layers.routes
        ? (routesQ.data ?? [])
            .filter((r) => r.geometry)
            .slice(0, 6)
            .map((r) => ({
              id: r.id,
              coordinates: (r.geometry.coordinates as [number, number][]).map(([lng, lat]) => [lat, lng]),
              estimated: r.geometry_is_estimated,
            }))
        : [],
    [layers.routes, routesQ.data],
  )

  const layerNames: { key: Layer; label: string }[] = [
    { key: 'zones', label: 'Zones' }, { key: 'bins', label: 'Smart bins' }, { key: 'vehicles', label: 'Vehicles' },
    { key: 'reports', label: 'Waste reports' }, { key: 'complaints', label: 'Complaints' }, { key: 'routes', label: 'Routes' },
  ]

  return (
    <div className="mx-auto max-w-[1400px]">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-3 text-xl font-bold tracking-tight md:text-2xl">
            <Compass className="text-emerald-400" size={24} /> Command center
            {isDemo && <DemoBadge />}
          </h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-[var(--color-mute)]">
            <span className="inline-flex items-center gap-1.5"><span className="pulse-dot inline-block h-2 w-2 rounded-full bg-emerald-400" /> Live operational picture
            </span>
          </p>
        </div>
        <a href="#/ops/routes" className="btn btn-primary"><RouteIcon size={15} /> Generate route</a>
      </div>

      {/* KPI strip */}
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard label="Completion (30d)" value={d?.collection.completion_rate != null ? fmtPct(d.collection.completion_rate, 0) : '—'} sub={`${d?.collection.completed ?? 0}/${d?.collection.total_events ?? 0} events`} icon={<Trash2 size={15} />} />
        <StatCard label="Collected" value={fmtKg(d?.collection.weight_collected_kg)} sub="last 30 days" icon={<Activity size={15} />} tone="purple" />
        <StatCard label="Open reports" value={d?.work.open_reports ?? '—'} icon={<CircleDot size={15} />} tone="danger" />
        <StatCard label="Open complaints" value={d?.work.open_complaints ?? '—'} icon={<AlertTriangle size={15} />} tone="warn" />
        <StatCard label="Routes running" value={d?.fleet.routes_in_progress ?? 0} sub={`${d?.fleet.active_vehicles ?? 0} active vehicles`} icon={<Truck size={15} />} tone="info" />
        <StatCard label="Open alerts" value={d?.work.open_alerts ?? '—'} sub={`${d?.iot.devices_online ?? 0}/${d?.iot.devices_total ?? 0} devices online`} icon={<Radio size={15} />} tone="warn" />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {/* Map */}
        <Panel className="relative overflow-hidden xl:col-span-2">
          <div className="absolute left-3 top-3 z-[500] flex flex-wrap gap-1.5">
            {layerNames.map((l) => (
              <button
                key={l.key}
                onClick={() => setLayers((s) => ({ ...s, [l.key]: !s[l.key] }))}
                className={clsx(
                  'chip border backdrop-blur transition-all',
                  layers[l.key] ? 'border-emerald-500/40 bg-emerald-950/80 text-emerald-300' : 'border-[var(--color-line)] bg-[var(--color-base)]/80 text-[var(--color-faint)]',
                )}
              >
                {l.label}
              </button>
            ))}
          </div>
          <MapView
            className="h-[560px] rounded-none border-0"
            points={mapPoints}
            routes={mapRoutes}
            zones={layers.zones
              ? (zonesQ.data ?? []).map((z) => ({ id: z.id, name: z.name, color: z.color_hex, boundary: z.boundary }))
              : []}
            fit={false}
          />
          <MapLegend
            items={[
              { color: '#38bdf8', label: 'Bin <60% fill' },
              { color: '#f59e0b', label: 'Bin 60–85%' },
              { color: '#f43f5e', label: 'Bin >85% / report' },
              { color: '#a78bfa', label: 'Vehicle' },
              { color: '#10b981', label: 'Route', dashed: true },
            ]}
          />
        </Panel>

        {/* Right column */}
        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHeader title="Open alerts" subtitle="Threshold alerts from smart-bin telemetry" icon={<AlertTriangle size={16} />} />
            <div className="max-h-72 divide-y divide-[var(--color-line)] overflow-auto">
              {(alertsQ.data?.items ?? []).slice(0, 12).map((a) => (
                <button key={a.id} className="table-row flex w-full items-start gap-3 px-4 py-3 text-left" onClick={() => setSelectedAlert(a)}>
                  <span className={clsx('mt-1 h-2 w-2 shrink-0 rounded-full',
                    a.severity === 'critical' ? 'bg-rose-500' : a.severity === 'high' ? 'bg-amber-500' : a.severity === 'warning' ? 'bg-amber-300' : 'bg-sky-500')} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold">{a.title}</p>
                    <p className="truncate text-[11px] text-[var(--color-faint)]">{timeAgo(a.triggered_at)}</p>
                  </div>
                </button>
              ))}
              {!alertsQ.data?.items.length && (
                <EmptyState icon={<CheckCircle2 size={24} />} title="No open alerts" hint="Telemetry thresholds are being evaluated on every reading." />
              )}
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Fleet" subtitle="Live vehicle status" icon={<Truck size={16} />} />
            <div className="max-h-72 divide-y divide-[var(--color-line)] overflow-auto">
              {(vehiclesQ.data ?? []).map((v) => (
                <div key={v.id} className="table-row flex items-center gap-3 px-4 py-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/10 text-violet-300"><Truck size={14} /></div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold">{v.code}{v.name ? ` · ${v.name}` : ''}</p>
                    <p className="text-[11px] text-[var(--color-faint)]">
                      {v.last_ping_at ? `ping ${timeAgo(v.last_ping_at)}` : 'no ping'}
                      {v.current_route_id ? ' · on route' : ''}
                    </p>
                  </div>
                  {v.position_is_simulated && <SimBadge label="SIM GPS" />}
                  <StatusBadge status={v.status} />
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>

      {/* Alert detail */}
      <Modal open={!!selectedAlert} onClose={() => setSelectedAlert(null)} title={selectedAlert?.title ?? ''}>
        {selectedAlert && (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-[var(--color-mute)]">{selectedAlert.message}</p>
            <div className="flex items-center gap-2">
              <Badge tone={selectedAlert.severity === 'critical' ? 'danger' : selectedAlert.severity === 'high' ? 'warn' : 'info'}>
                {humanize(selectedAlert.severity)}
              </Badge>
              <span className="text-xs text-[var(--color-faint)]">{timeAgo(selectedAlert.triggered_at)}</span>
            </div>
            {typeof selectedAlert.metadata?.value === 'number' && (
              <p className="rounded-lg border border-[var(--color-line)] bg-[var(--color-base)] px-3 py-2 font-mono text-xs">
                {String(selectedAlert.metadata.metric)} = {selectedAlert.metadata.value} (threshold {String(selectedAlert.metadata.threshold)})
              </p>
            )}
            <div className="flex gap-2">
              <button className="btn btn-primary flex-1" disabled={alertMutation.isPending} onClick={() => alertMutation.mutate({ id: selectedAlert.id, status: 'acknowledged' })}>
                Acknowledge
              </button>
              <button className="btn btn-ghost flex-1" disabled={alertMutation.isPending} onClick={() => alertMutation.mutate({ id: selectedAlert.id, status: 'resolved' })}>
                Resolve
              </button>
            </div>
          </div>
        )}
      </Modal>
      {toast && <Toast message={toast} />}
    </div>
  )
}

interface MapReport { id: string; latitude: number; longitude: number; description: string | null; status: string }
interface MapComplaint { id: string; latitude: number | null; longitude: number | null; subject: string; status: string }
interface MapRouteRow { id: string; geometry: { coordinates: [number, number][] }; geometry_is_estimated: boolean }
interface ZoneRow { id: string; name: string; color_hex: string; boundary: { type: string; coordinates: [number, number][][] } }
interface OperationsDash {
  collection: { total_events: number; completed: number; missed: number; completion_rate: number | null; weight_collected_kg: number }
  work: { open_reports: number; open_complaints: number; open_alerts: number }
  fleet: { active_vehicles: number; routes_in_progress: number }
  iot: { devices_online: number; devices_total: number }
}
