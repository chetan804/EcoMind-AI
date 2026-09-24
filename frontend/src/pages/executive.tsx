/* Executive dashboard: KPIs, trends, service quality. */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { clsx } from 'clsx'
import {
  Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis,
} from 'recharts'
import { Activity, CheckCircle2, Leaf, Route as RouteIcon, TrendingUp, Users } from 'lucide-react'
import { get } from '../lib/api'
import { useAuth } from '../lib/auth'
import { DemoBadge, Panel, PanelHeader, Spinner, StatCard } from '../ui'
import { fmtKg, fmtPct } from '../lib/format'

interface ExecutiveDash {
  period_days: number
  collection: {
    total_events: number
    completed: number
    missed: number
    skipped: number
    completion_rate: number | null
    weight_collected_kg: number
  }
  trend: { date: string; total: number; completed: number; weight_kg: number }[]
  work: { open_reports: number; open_complaints: number; open_alerts: number }
  fleet: { active_vehicles: number; routes_in_progress: number }
  iot: { devices_online: number; devices_total: number }
  complaints: { total: number; resolved: number; resolution_rate: number | null; avg_resolution_hours: number | null }
  routes: { completed: number; avg_distance_km: number; total_distance_km: number; avg_duration_min: number }
  participation: { citizens_with_activity: number }
}

interface SustSummary {
  waste: { total_collected_kg: number; diverted_kg: number; diversion_rate: number }
  emissions: { total_co2e_kg: number; avoided_kg_modeled: number }
}

export function ExecutivePage() {
  const { orgId } = useAuth()
  const [days, setDays] = useState(90)

  const q = useQuery({
    queryKey: ['executive', days],
    queryFn: () => get<ExecutiveDash>(`/analytics/executive?days=${days}`),
    enabled: !!orgId,
  })
  const sustQ = useQuery({
    queryKey: ['sustainability', 30],
    queryFn: () => get<SustSummary>('/sustainability/summary?days=30'),
    enabled: !!orgId,
  })

  if (q.isLoading) return <div className="flex min-h-[50vh] items-center justify-center"><Spinner className="text-emerald-400" /></div>
  const d = q.data
  if (!d) return <div className="p-8 text-center text-sm text-[var(--color-mute)]">Executive analytics unavailable.</div>

  const trend = d.trend.map((x) => ({ ...x, label: x.date.slice(5) }))
  const s = sustQ.data

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex flex-wrap items-center gap-3 text-xl font-bold tracking-tight md:text-2xl">
            Executive overview
            <DemoBadge />
          </h1>
          <p className="mt-1 text-sm text-[var(--color-mute)]">Last {d.period_days} days · carbon panel shows last 30 days</p>
        </div>
        <div className="flex items-center gap-2">
          {[30, 90, 365].map((n) => (
            <button key={n} onClick={() => setDays(n)}
              className={clsx('chip border', days === n ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300' : 'border-[var(--color-line)] text-[var(--color-mute)]')}>
              {n}d
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Collection completion" value={d.collection.completion_rate != null ? fmtPct(d.collection.completion_rate, 1) : '—'} sub={`${d.collection.completed}/${d.collection.total_events} events · ${d.collection.missed} missed`} icon={<CheckCircle2 size={16} />} />
        <StatCard label="Waste collected" value={fmtKg(d.collection.weight_collected_kg)} sub={`${d.period_days}-day tonnage`} icon={<Activity size={16} />} tone="purple" />
        <StatCard label="Complaint resolution" value={d.complaints.resolution_rate != null ? fmtPct(d.complaints.resolution_rate, 1) : '—'} sub={d.complaints.avg_resolution_hours != null ? `avg ${d.complaints.avg_resolution_hours}h to resolve` : `${d.complaints.total} total complaints`} icon={<TrendingUp size={16} />} tone="brand" />
        <StatCard label="Citizen participation" value={d.participation.citizens_with_activity} sub={`${d.work.open_reports} open reports · ${d.work.open_complaints} open complaints`} icon={<Users size={16} />} tone="info" />
      </div>

      <Panel className="mt-6">
        <PanelHeader title="Daily collection performance" subtitle="Scheduled vs completed events and collected weight" icon={<TrendingUp size={15} />} />
        <div className="h-72 p-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trend} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="gTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gDone" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
              <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} allowDecimals={false} />
              <RTooltip contentStyle={{ background: '#0d1117', border: '1px solid #1f2937', borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area type="monotone" dataKey="total" name="Scheduled" stroke="#38bdf8" fill="url(#gTotal)" strokeWidth={2} />
              <Area type="monotone" dataKey="completed" name="Completed" stroke="#10b981" fill="url(#gDone)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Panel className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><RouteIcon size={15} className="text-emerald-400" /> Routes & fleet</h3>
          <div className="flex flex-col gap-3 text-sm">
            <Row label="Completed routes" value={String(d.routes.completed)} />
            <Row label="Total distance" value={`${d.routes.total_distance_km} km`} />
            <Row label="Avg route duration" value={`${Math.round(d.routes.avg_duration_min)} min`} />
            <Row label="Active vehicles" value={String(d.fleet.active_vehicles)} />
            <Row label="Routes in progress" value={String(d.fleet.routes_in_progress)} />
          </div>
        </Panel>
        <Panel className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Users size={15} className="text-emerald-400" /> Service quality</h3>
          <div className="flex flex-col gap-3 text-sm">
            <Row label="Open complaints" value={String(d.work.open_complaints)} />
            <Row label="Open reports" value={String(d.work.open_reports)} />
            <Row label="Open alerts" value={String(d.work.open_alerts)} />
            <Row label="Devices online" value={`${d.iot.devices_online}/${d.iot.devices_total}`} />
          </div>
        </Panel>
        <Panel className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Leaf size={15} className="text-emerald-400" /> Carbon (30d)</h3>
          {s ? (
            <div className="flex flex-col gap-3 text-sm">
              <Row label="Diversion rate" value={fmtPct(s.waste.diversion_rate, 1)} />
              <Row label="Diverted" value={`${fmtKg(s.waste.diverted_kg)}`} />
              <Row label="Net emissions" value={`${fmtKg(s.emissions.total_co2e_kg)} CO2e`} />
              <Row label="Avoided (modeled)" value={`${fmtKg(s.emissions.avoided_kg_modeled)} CO2e`} />
            </div>
          ) : (
            <p className="text-xs text-[var(--color-faint)]">Sustainability data not yet computed.</p>
          )}
          <p className="mt-3 text-[10px] leading-relaxed text-[var(--color-faint)]">
            Avoided emissions use a modeled counterfactual and stay separate from net treatment emissions.
          </p>
        </Panel>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-[var(--color-mute)]">{label}</span>
      <span className="text-sm font-semibold">{value}</span>
    </div>
  )
}
