/* Map components — Leaflet with dark tiles, layers, popups.
 * OSM raster tiles are used for basemap rendering only. */

import { useEffect, useMemo } from 'react'
import L from 'leaflet'
import { MapContainer, TileLayer, useMap, CircleMarker, Polyline, Polygon, Tooltip } from 'react-leaflet'
import { clsx } from 'clsx'

export interface MapPoint {
  id: string
  lat: number
  lng: number
  title: string
  kind: 'bin' | 'report' | 'complaint' | 'vehicle' | 'facility'
  status?: string
  fillPct?: number | null
  simulated?: boolean
  meta?: string[]
}

export interface MapRoute {
  id: string
  coordinates: [number, number][]
  color?: string
  estimated?: boolean
}

export interface MapZone {
  id: string
  name: string
  color: string
  boundary: { type: string; coordinates: [number, number][][] }
}

const KIND_COLORS: Record<string, string> = {
  bin: '#38bdf8',
  report: '#f43f5e',
  complaint: '#f59e0b',
  vehicle: '#a78bfa',
  facility: '#10b981',
}

function fillColor(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '#38bdf8'
  if (pct >= 85) return '#f43f5e'
  if (pct >= 60) return '#f59e0b'
  return '#38bdf8'
}

function FitBounds({ points }: { points: MapPoint[] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length > 0) {
      const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lng] as [number, number]))
      map.fitBounds(bounds.pad(0.15), { animate: false })
    }
  }, [map]) // fit once on mount — user pan/zoom is respected afterwards
  return null
}

export interface MapViewProps {
  points: MapPoint[]
  routes?: MapRoute[]
  zones?: MapZone[]
  className?: string
  center?: [number, number]
  zoom?: number
  fit?: boolean
  onPointClick?: (p: MapPoint) => void
}

export function MapView({ points, routes = [], zones = [], className, center = [12.96, 77.60], zoom = 13, fit = true, onPointClick }: MapViewProps) {
  return (
    <div className={clsx('overflow-hidden rounded-xl border border-[var(--color-line)]', className)}>
      <MapContainer center={center} zoom={zoom} className="h-full w-full" scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        {fit && <FitBounds points={points} />}
        {zones.map((z) => (
          <Polygon
            key={z.id}
            positions={z.boundary.coordinates[0].map(([lng, lat]) => [lat, lng])}
            pathOptions={{ color: z.color, weight: 1.5, opacity: 0.5, fillOpacity: 0.04 }}
          >
            <Tooltip sticky>{z.name}</Tooltip>
          </Polygon>
        ))}
        {routes.map((r) => (
          <Polyline
            key={r.id}
            positions={r.coordinates}
            pathOptions={{
              color: r.color ?? '#10b981',
              weight: 3,
              opacity: 0.85,
              dashArray: r.estimated ? '8 6' : undefined,
            }}
          >
            <Tooltip sticky>{r.estimated ? 'Route (estimated geometry)' : 'Route'}</Tooltip>
          </Polyline>
        ))}
        {points.map((p) => (
          <CircleMarker
            key={`${p.kind}-${p.id}`}
            center={[p.lat, p.lng]}
            radius={p.kind === 'vehicle' ? 7 : 6}
            pathOptions={{
              color: p.kind === 'bin' ? fillColor(p.fillPct) : KIND_COLORS[p.kind],
              fillColor: p.kind === 'bin' ? fillColor(p.fillPct) : KIND_COLORS[p.kind],
              fillOpacity: 0.9,
              weight: p.simulated ? 2 : 1.5,
              className: p.simulated ? 'pulse-dot' : undefined,
            }}
            eventHandlers={{ click: () => onPointClick?.(p) }}
          >
            <Tooltip>
              <div className="min-w-32">
                <div className="font-semibold">{p.title}</div>
                {p.status && <div className="opacity-70">{p.status}</div>}
                {p.fillPct !== undefined && p.fillPct !== null && (
                  <div className="opacity-70">Fill: {Math.round(p.fillPct)}%</div>
                )}
                {p.simulated && <div className="mt-0.5 text-violet-300">● simulated position</div>}
              </div>
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}

export function MapLegend({ items }: { items: { color: string; label: string; dashed?: boolean }[] }) {
  return (
    <div className="glass pointer-events-none absolute bottom-3 right-3 z-[400] rounded-lg px-3 py-2">
      <div className="flex flex-col gap-1.5">
        {items.map((i) => (
          <div key={i.label} className="flex items-center gap-2">
            <span
              className="inline-block h-0.5 w-4 rounded"
              style={{ background: i.dashed ? 'transparent' : i.color, borderTop: i.dashed ? `2px dashed ${i.color}` : undefined }}
            />
            <span className="text-[10px] font-medium text-[var(--color-mute)]">{i.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
