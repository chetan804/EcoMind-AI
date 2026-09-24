/* Field collector experience: touch-friendly, large controls, one-tap actions. */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { Check, ChevronRight, MapPin, Navigation, Route as RouteIcon, SkipForward, TriangleAlert } from 'lucide-react'
import { get, patch } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, EmptyState, Field, Modal, Panel, Spinner, StatusBadge, Toast } from '../ui'
import { fmtDate, humanize } from '../lib/format'

interface Stop {
  id: string
  sequence_no: number
  collection_point_id: string
  point_name: string | null
  point_code: string | null
  latitude: number | null
  longitude: number | null
  address: string | null
  status: string
  priority: number
  weight_kg: number | null
  skip_reason: string | null
  notes: string | null
}

interface RouteDetail {
  id: string
  code: string
  name: string
  status: string
  total_distance_km: number | null
  total_duration_min: number | null
  stops: Stop[]
  completed_stops: number
  vehicle_id: string | null
}

const SKIP_REASONS = ['bin_blocked', 'no_access', 'vehicle_full', 'safety_hazard', 'not_present']

export function FieldPage() {
  const { orgId } = useAuth()
  const queryClient = useQueryClient()
  const [activeStop, setActiveStop] = useState<Stop | null>(null)
  const [weight, setWeight] = useState('')
  const [skipReason, setSkipReason] = useState(SKIP_REASONS[0])
  const [notes, setNotes] = useState('')
  const [contaminated, setContaminated] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const { data: today, isLoading } = useQuery({
    queryKey: ['field', 'today'],
    queryFn: () => get<{ items: RouteDetail[] }>('/routes/my/today'),
    enabled: !!orgId,
  })

  const route = today?.items?.[0]
  const detail = useQuery({
    queryKey: ['field', 'route', route?.id],
    queryFn: () => get<RouteDetail>(`/routes/${route?.id}`),
    enabled: !!route,
    refetchInterval: 15000,
  })

  const stopMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      patch(`/routes/stops/${id}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['field'] })
      setActiveStop(null)
      setWeight('')
      setNotes('')
      setContaminated(false)
      setToast('Stop updated')
      setTimeout(() => setToast(null), 2500)
    },
  })

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center"><Spinner className="text-emerald-400" /></div>
  }

  if (!route) {
    return (
      <div className="mx-auto max-w-lg px-4 py-10">
        <Panel>
          <EmptyState icon={<RouteIcon size={30} />} title="No route assigned for today" hint="Your supervisor assigns routes from the operations console. Check back later." />
        </Panel>
      </div>
    )
  }

  const stops = detail.data?.stops ?? []
  const done = stops.filter((s) => s.status !== 'pending').length
  const nextStop = stops.find((s) => s.status === 'pending')

  return (
    <div className="mx-auto max-w-lg px-4 py-5">
      {/* Route header */}
      <Panel className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-400">{route.code}</p>
            <h1 className="text-lg font-bold leading-tight">{route.name}</h1>
          </div>
          <StatusBadge status={route.status} />
        </div>
        <div className="mt-3 flex items-center gap-4 text-xs text-[var(--color-mute)]">
          <span>{stops.length} stops</span>
          <span>{done} done</span>
          {route.total_distance_km != null && <span>{route.total_distance_km.toFixed(1)} km</span>}
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--color-line)]">
          <div className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all" style={{ width: `${stops.length ? (done / stops.length) * 100 : 0}%` }} />
        </div>
      </Panel>

      {/* Next stop hero */}
      {nextStop && (
        <button
          className="panel panel-hover mt-4 w-full p-5 text-left"
          onClick={() => setActiveStop(nextStop)}
        >
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-faint)]">Next stop</p>
          <div className="mt-1 flex items-center justify-between gap-3">
            <div>
              <p className="text-lg font-bold leading-tight">{nextStop.point_name ?? 'Collection point'}</p>
              <p className="mt-0.5 text-xs text-[var(--color-mute)]">{nextStop.address ?? `${nextStop.latitude?.toFixed(4)}, ${nextStop.longitude?.toFixed(4)}`}</p>
            </div>
            {nextStop.priority > 0 && <Badge tone="danger">priority</Badge>}
          </div>
          <div className="mt-3 flex gap-2">
            {nextStop.latitude && nextStop.longitude && (
              <a
                href={`https://www.openstreetmap.org/?mlat=${nextStop.latitude}&mlon=${nextStop.longitude}#map=18/${nextStop.latitude}/${nextStop.longitude}`}
                target="_blank"
                rel="noreferrer"
                className="btn btn-ghost btn-sm"
                onClick={(e) => e.stopPropagation()}
              >
                <Navigation size={14} /> Navigate
              </a>
            )}
            <span className="btn btn-primary btn-sm">Open <ChevronRight size={14} /></span>
          </div>
        </button>
      )}

      {/* Stop list */}
      <div className="mt-4 flex flex-col gap-2">
        {stops.map((s) => (
          <button
            key={s.id}
            className={clsx('panel flex items-center gap-3 p-3.5 text-left transition-all', s.status !== 'pending' && 'opacity-60')}
            onClick={() => s.status === 'pending' && setActiveStop(s)}
          >
            <span className={clsx('flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold',
              s.status === 'completed' ? 'bg-emerald-500/20 text-emerald-300'
                : s.status === 'skipped' ? 'bg-amber-500/20 text-amber-300'
                : 'bg-[var(--color-line)] text-[var(--color-mute)]')}>
              {s.status === 'completed' ? <Check size={16} /> : s.sequence_no}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{s.point_name ?? 'Stop'}</p>
              <p className="truncate text-[11px] text-[var(--color-faint)]">
                {s.weight_kg ? `${s.weight_kg} kg` : s.skip_reason ? humanize(s.skip_reason) : s.address ?? ''}
              </p>
            </div>
            {s.status === 'pending' && <ChevronRight size={16} className="text-[var(--color-faint)]" />}
          </button>
        ))}
      </div>

      {/* Stop action sheet */}
      <Modal open={!!activeStop} onClose={() => setActiveStop(null)} title={activeStop ? `Stop ${activeStop.sequence_no} — ${activeStop.point_name ?? ''}` : ''}>
        {activeStop && (
          <div className="flex flex-col gap-4">
            {activeStop.address && <p className="flex items-center gap-2 text-xs text-[var(--color-mute)]"><MapPin size={13} /> {activeStop.address}</p>}
            <Field label="Collected weight (kg)">
              <input className="input text-lg" type="number" inputMode="decimal" min="0" max="50000" step="0.1" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="e.g. 180" />
            </Field>
            <label className="flex items-center gap-3 rounded-lg border border-[var(--color-line)] px-3 py-2.5">
              <input type="checkbox" checked={contaminated} onChange={(e) => setContaminated(e.target.checked)} className="h-4 w-4 accent-emerald-500" />
              <span className="flex items-center gap-2 text-sm"><TriangleAlert size={14} className="text-amber-400" /> Contamination observed</span>
            </label>
            <Field label="Notes (optional)">
              <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Anything the ops team should know" />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <button
                className="btn btn-primary btn-lg"
                disabled={stopMutation.isPending}
                onClick={() => stopMutation.mutate({
                  id: activeStop.id,
                  body: { status: 'completed', weight_kg: weight ? parseFloat(weight) : null, contamination_flag: contaminated, notes: notes || null },
                })}
              >
                {stopMutation.isPending ? <Spinner /> : <Check size={18} />} Collected
              </button>
              <button
                className="btn btn-ghost btn-lg"
                disabled={stopMutation.isPending}
                onClick={() => stopMutation.mutate({ id: activeStop.id, body: { status: 'skipped', skip_reason: skipReason, notes: notes || null } })}
              >
                <SkipForward size={17} /> Skip
              </button>
            </div>
            <Field label="Skip reason (if skipping)">
              <select className="input" value={skipReason} onChange={(e) => setSkipReason(e.target.value)}>
                {SKIP_REASONS.map((r) => <option key={r} value={r}>{humanize(r)}</option>)}
              </select>
            </Field>
          </div>
        )}
      </Modal>
      {toast && <Toast message={toast} />}
    </div>
  )
}
