/* Sustainability analyst dashboard: emissions, diversion, methodology transparency. */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from 'recharts'
import { Beaker, Leaf, Recycle, Scale, TrendingDown } from 'lucide-react'
import { get, post as apiPost } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, DemoBadge, EmptyState, Panel, PanelHeader, Spinner, StatCard } from '../ui'
import { fmtKg, fmtPct, fmtNumber } from '../lib/format'

interface CarbonRecord {
  id: string
  scope: string
  category: string
  activity_value: number
  activity_unit: string
  co2e_kg: number
  quality: 'measured' | 'estimated' | 'modeled'
  factor_code: string
  factor_version: string
  methodology: string
  assumptions: string | null
}

interface Summary {
  period: { start: string; end: string }
  waste: {
    total_collected_kg: number
    by_destination: Record<string, number>
    diverted_kg: number
    diversion_rate: number
  }
  emissions: {
    total_co2e_kg: number
    scope1_kg: number
    scope3_kg: number
    avoided_kg_modeled: number
  }
  records: CarbonRecord[]
}

interface FactorRow {
  code: string
  name: string
  category: string
  source: string
  year: number
  unit: string
  value: number
  methodology: string
  version: string
  uncertainty_pct: number | null
}

const DEST_COLORS: Record<string, string> = {
  recycling: '#10b981',
  composting: '#84cc16',
  landfill: '#f43f5e',
  incineration: '#f59e0b',
  ad: '#a78bfa',
  reuse: '#38bdf8',
  other: '#64748b',
}

const QUALITY_TONE: Record<string, 'brand' | 'info' | 'purple'> = {
  measured: 'brand',
  estimated: 'info',
  modeled: 'purple',
}

export function SustainabilityPage() {
  const { orgId, isDemo, hasPerm } = useAuth()
  const [days, setDays] = useState(30)

  const q = useQuery({
    queryKey: ['sustainability', days],
    queryFn: () => get<Summary>(`/sustainability/summary?days=${days}`),
    enabled: !!orgId,
  })
  const factorsQ = useQuery({
    queryKey: ['sustainability-factors'],
    queryFn: () => get<{ items: FactorRow[] }>('/sustainability/factors'),
    enabled: !!orgId,
  })
  const recompute = useMutationLight()

  if (q.isLoading) return <div className="flex min-h-[50vh] items-center justify-center"><Spinner className="text-emerald-400" /></div>
  if (q.isError || !q.data) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <Panel><EmptyState icon={<Leaf size={30} />} title="Sustainability analytics unavailable" hint={hasPerm('sustainability:recompute') ? 'Try running a recompute for this period.' : 'Contact your organization admin.'} /></Panel>
      </div>
    )
  }

  const d = q.data
  const treatmentData = Object.entries(d.waste.by_destination).map(([k, v]) => ({ name: k, value: v }))
  const scopeData = [
    { name: 'Scope 1', value: d.emissions.scope1_kg, fill: '#f59e0b' },
    { name: 'Scope 3', value: d.emissions.scope3_kg, fill: '#f43f5e' },
    { name: 'Avoided (modeled)', value: d.emissions.avoided_kg_modeled, fill: '#a78bfa' },
  ]
  const qualityTotals = d.records.reduce<Record<string, number>>((acc, r) => {
    acc[r.quality] = (acc[r.quality] ?? 0) + r.co2e_kg
    return acc
  }, {})

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex flex-wrap items-center gap-3 text-xl font-bold tracking-tight md:text-2xl">
            Sustainability intelligence
            {isDemo && <DemoBadge />}
          </h1>
          <p className="mt-1 text-sm text-[var(--color-mute)]">
            {d.period.start} → {d.period.end} · every figure traced to versioned emission factors
          </p>
        </div>
        <div className="flex items-center gap-2">
          {[30, 90, 365].map((n) => (
            <button key={n} onClick={() => setDays(n)}
              className={clsx('chip border', days === n ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300' : 'border-[var(--color-line)] text-[var(--color-mute)]')}>
              {n}d
            </button>
          ))}
          {hasPerm('sustainability:recompute') && (
            <button className="btn btn-ghost btn-sm" disabled={recompute.busy} onClick={() => recompute.run(days)}>
              {recompute.busy ? <Spinner /> : <Beaker size={14} />} Recompute
            </button>
          )}
        </div>
      </div>

      {recompute.message && <div className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-xs text-emerald-300">{recompute.message}</div>}

      {/* Headline stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Waste treated" value={fmtKg(d.waste.total_collected_kg)} sub="recorded treatments" icon={<Recycle size={16} />} />
        <StatCard label="Diverted from landfill" value={fmtKg(d.waste.diverted_kg)} sub={d.waste.diversion_rate ? `${fmtPct(d.waste.diversion_rate)} diversion rate` : 'no data'} icon={<TrendingDown size={16} />} tone="brand" />
        <StatCard label="Net emissions" value={fmtKg(d.emissions.total_co2e_kg)} sub="scope 1 + scope 3 CO2e" icon={<Scale size={16} />} tone="warn" />
        <StatCard label="Avoided emissions" value={fmtKg(d.emissions.avoided_kg_modeled)} sub="modeled counterfactual" icon={<Leaf size={16} />} tone="purple" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        {/* Treatment mix donut */}
        <Panel className="lg:col-span-2">
          <PanelHeader title="Treatment mix" subtitle="By destination" icon={<Recycle size={15} />} />
          <div className="h-64 p-4">
            {treatmentData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={treatmentData} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" paddingAngle={3}>
                    {treatmentData.map((entry) => (
                      <Cell key={entry.name} fill={DEST_COLORS[entry.name] ?? '#64748b'} stroke="transparent" />
                    ))}
                  </Pie>
                  <RTooltip
                    contentStyle={{ background: '#0d1117', border: '1px solid #1f2937', borderRadius: 8, fontSize: 12 }}
                    formatter={(v: number) => [`${fmtNumber(v)} kg`, '']}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState title="No treatments recorded" hint="Record collection weights to see treatment mix." />
            )}
          </div>
          <div className="flex flex-wrap gap-2 border-t border-[var(--color-line)] px-5 py-3">
            {treatmentData.map((entry) => (
              <span key={entry.name} className="flex items-center gap-1.5 text-[11px] text-[var(--color-mute)]">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: DEST_COLORS[entry.name] ?? '#64748b' }} />
                {entry.name} · {fmtKg(entry.value)}
              </span>
            ))}
          </div>
        </Panel>

        {/* Scope bars */}
        <Panel className="lg:col-span-3">
          <PanelHeader title="Emissions by scope" subtitle="kg CO2e for the selected period" icon={<Scale size={15} />} />
          <div className="h-64 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={scopeData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                <RTooltip
                  contentStyle={{ background: '#0d1117', border: '1px solid #1f2937', borderRadius: 8, fontSize: 12 }}
                  formatter={(v: number) => [`${fmtNumber(v)} kg CO2e`, '']}
                />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {scopeData.map((s) => <Cell key={s.name} fill={s.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="border-t border-[var(--color-line)] px-5 py-3">
            <div className="mb-2 flex flex-wrap gap-2">
              {Object.entries(qualityTotals).map(([quality, kg]) => (
                <Badge key={quality} tone={QUALITY_TONE[quality] ?? 'info'}>{quality}: {fmtKg(kg)} CO2e</Badge>
              ))}
            </div>
            <p className="text-[11px] leading-relaxed text-[var(--color-faint)]">
              Net emissions exclude the avoided counterfactual. Avoided emissions are modeled (recycling
              displacing virgin production) and are never presented as offsets or tradable credits.
            </p>
          </div>
        </Panel>
      </div>

      {/* Records ledger */}
      <Panel className="mt-6">
        <PanelHeader title="Carbon records" subtitle={`${d.records.length} computed records — full provenance`} icon={<Beaker size={15} />} />
        {d.records.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-line)] text-[11px] uppercase tracking-wider text-[var(--color-faint)]">
                  <th className="px-5 py-3 font-medium">Category</th>
                  <th className="px-3 py-3 font-medium">Scope</th>
                  <th className="px-3 py-3 font-medium">Activity</th>
                  <th className="px-3 py-3 font-medium">CO2e</th>
                  <th className="px-3 py-3 font-medium">Quality</th>
                  <th className="px-3 py-3 font-medium">Factor</th>
                  <th className="px-5 py-3 font-medium">Methodology</th>
                </tr>
              </thead>
              <tbody>
                {d.records.map((r) => (
                  <tr key={r.id} className="border-b border-[var(--color-line)]/50 last:border-0">
                    <td className="px-5 py-3">{r.category}</td>
                    <td className="px-3 py-3 text-xs">{r.scope}</td>
                    <td className="px-3 py-3 text-xs">{fmtNumber(r.activity_value)} {r.activity_unit}</td>
                    <td className="px-3 py-3 font-semibold">{fmtNumber(r.co2e_kg)} kg</td>
                    <td className="px-3 py-3"><Badge tone={QUALITY_TONE[r.quality] ?? 'info'}>{r.quality}</Badge></td>
                    <td className="px-3 py-3 font-mono text-[11px]">{r.factor_code}@{r.factor_version}</td>
                    <td className="px-5 py-3 font-mono text-[11px]">{r.methodology}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No carbon records for this period" hint="Run a recompute after recording collection weights." />
        )}
      </Panel>

      {/* Factor library */}
      <Panel className="mt-6">
        <PanelHeader title="Emission factor library" subtitle="Platform-level, versioned — read-only reference" icon={<Scale size={15} />} />
        <div className="grid gap-2 p-5 sm:grid-cols-2 lg:grid-cols-3">
          {(factorsQ.data?.items ?? []).slice(0, 12).map((f) => (
            <div key={f.code} className="rounded-lg border border-[var(--color-line)] px-3 py-2.5">
              <p className="text-xs font-semibold">{f.name}</p>
              <p className="mt-0.5 font-mono text-[10px] text-[var(--color-faint)]">{f.code} · v{f.version} · {f.source} {f.year}</p>
              <p className="mt-1 text-[11px] text-emerald-400">{f.value} kg CO2e / {f.unit}{f.uncertainty_pct ? ` · ±${f.uncertainty_pct}%` : ''}</p>
            </div>
          ))}
          {!factorsQ.data?.items.length && <p className="text-xs text-[var(--color-faint)]">No factors loaded.</p>}
        </div>
      </Panel>
    </div>
  )
}

/* Small helper: POST /sustainability/recompute with local busy state. */
function useMutationLight() {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string | null>(null)
  const m = useMutation({
    mutationFn: (days: number) => apiPost<{ records?: number }>(`/sustainability/recompute?days=${days}`, {}),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['sustainability'] })
      setMessage(`Recomputed ${data?.records ?? 0} carbon records for the period.`)
      setTimeout(() => setMessage(null), 4000)
    },
    onError: (e: Error) => setMessage(`Recompute failed: ${e.message}`),
  })
  return { busy: m.isPending, run: m.mutate, message }
}
