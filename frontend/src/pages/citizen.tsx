/* Citizen experience: dashboard, report wizard, my reports, impact, schedule. */

import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import {
  CalendarDays, Camera, CheckCircle2, ChevronLeft, ChevronRight, ClipboardList, Compass,
  ImagePlus, Leaf, MapPin, Recycle, Sprout, Trophy,
} from 'lucide-react'
import { get, post, postForm } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, DemoBadge, EmptyState, ErrorNote, Field, Panel, Spinner, StatCard, StatusBadge, Toast } from '../ui'
import { fmtDate, fmtKg, fmtPct, humanize, timeAgo } from '../lib/format'
import { MapView, type MapPoint, type MapZone } from '../map'

function toMapZones(zones: ZoneRow[]): MapZone[] {
  return zones.map((z) => ({ id: z.id, name: z.name, color: z.color_hex, boundary: z.boundary }))
}

/* ------------------------------------------------------------------ dashboard */

export function CitizenDashboard() {
  const { orgId, isDemo } = useAuth()
  const { data: me } = useQuery({ queryKey: ['analytics', 'citizen'], queryFn: () => get<CitizenAnalytics>('/analytics/citizen'), enabled: !!orgId })
  const { data: rewards } = useQuery({ queryKey: ['rewards'], queryFn: () => get<RewardsMe>('/rewards/me'), enabled: !!orgId })
  const { data: reports } = useQuery({
    queryKey: ['my-reports-recent'],
    queryFn: () => get<{ items: ReportOut[] }>('/waste/reports?mine=true&page_size=4'),
    enabled: !!orgId,
  })
  const { data: zones } = useQuery({ queryKey: ['zones'], queryFn: () => get<ZoneRow[]>('/organizations/current/zones'), enabled: !!orgId })

  const d = me
  return (
    <Shell title="Community dashboard" subtitle={isDemo ? <span className="inline-flex items-center gap-2"><DemoBadge /> Aurora Municipal Corporation — synthetic demo data</span> : undefined}>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="My reports" value={d?.my_reports ?? '—'} sub={`${d?.my_resolved ?? 0} resolved`} icon={<ClipboardList size={16} />} />
        <StatCard label="Community reports (30d)" value={d?.community_reports_30d ?? '—'} sub={`${d?.collection_points ?? 0} collection points`} icon={<Compass size={16} />} tone="info" />
        <StatCard label="Waste processed" value={fmtKg(d?.community_weight_kg)} sub="total recorded treatments" icon={<Recycle size={16} />} tone="purple" />
        <StatCard label="Sustainability points" value={rewards?.points ?? '—'} sub={`Level ${rewards?.level ?? 1}`} icon={<Sprout size={16} />} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <div className="border-b border-[var(--color-line)] px-5 py-4">
            <h3 className="text-sm font-semibold">My recent reports</h3>
          </div>
          {reports?.items.length ? (
            <div className="divide-y divide-[var(--color-line)]">
              {reports.items.map((r) => <ReportRow key={r.id} r={r} />)}
            </div>
          ) : (
            <EmptyState icon={<Camera size={28} />} title="No reports yet" hint="Spot waste in your neighborhood? Create your first report — it takes 30 seconds." />
          )}
          <div className="border-t border-[var(--color-line)] p-4">
            <a href="#/app/report" className="btn btn-primary w-full"><Camera size={15} /> Report waste</a>
          </div>
        </Panel>

        <div className="flex flex-col gap-6">
          <Panel className="p-5">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><CalendarDays size={15} className="text-emerald-400" /> Upcoming collection days</h3>
            <div className="flex flex-col gap-2">
              {(d?.upcoming_collection_days ?? []).slice(0, 5).map((u) => (
                <div key={u.date} className="flex items-center justify-between rounded-lg border border-[var(--color-line)] px-3 py-2">
                  <span className="text-xs font-medium">{fmtDate(u.date)}</span>
                  <span className="text-xs text-[var(--color-mute)]">{u.scheduled} collections</span>
                </div>
              ))}
              {!d?.upcoming_collection_days?.length && (
                <p className="text-xs text-[var(--color-faint)]">No upcoming collections scheduled.</p>
              )}
            </div>
          </Panel>
          <Panel className="p-5">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Trophy size={15} className="text-amber-400" /> Community leaderboard</h3>
            <Leaderboard />
          </Panel>
        </div>
      </div>

      {zones && zones.length > 0 && d && (
        <Panel className="mt-6 overflow-hidden">
          <div className="border-b border-[var(--color-line)] px-5 py-4">
            <h3 className="text-sm font-semibold">Service areas</h3>
          </div>
          <MapView className="h-80" zones={toMapZones(zones)} points={[]} fit={false} zoom={12} />
        </Panel>
      )}
    </Shell>
  )
}

function Leaderboard() {
  const { orgId } = useAuth()
  const { data } = useQuery({ queryKey: ['leaderboard'], queryFn: () => get<{ items: LeaderUser[] }>('/rewards/leaderboard'), enabled: !!orgId })
  return (
    <div className="flex flex-col gap-1.5">
      {(data?.items ?? []).slice(0, 6).map((u: LeaderUser) => (
        <div key={u.user_id} className="flex items-center gap-3">
          <span className={clsx('flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold',
            u.rank === 1 ? 'bg-amber-500/20 text-amber-300' : 'bg-[var(--color-line)] text-[var(--color-mute)]')}>
            {u.rank}
          </span>
          <span className="flex-1 truncate text-xs">{u.name}</span>
          <span className="text-xs font-semibold text-emerald-400">{u.points} pts</span>
        </div>
      ))}
      {!data?.items?.length && <p className="text-xs text-[var(--color-faint)]">No community activity yet.</p>}
    </div>
  )
}

/* ------------------------------------------------------------------ types */

interface ReportOut {
  id: string
  description: string | null
  latitude: number
  longitude: number
  address: string | null
  status: string
  severity: string
  category_guess: string | null
  ai_category: string | null
  ai_confidence: number | null
  ai_is_simulated: boolean | null
  created_at: string
  resolved_at: string | null
  resolution_notes: string | null
  zone_name: string | null
}

interface CitizenAnalytics {
  my_reports: number
  my_resolved: number
  community_reports_30d: number
  collection_points: number
  community_weight_kg: number
  upcoming_collection_days: { date: string; scheduled: number }[]
}

interface RewardsMe {
  points: number
  level: number
  next_level_at: number
  by_reason: Record<string, number>
}

interface ZoneRow {
  id: string
  name: string
  color_hex: string
  boundary: { type: string; coordinates: [number, number][][] }
}

interface LeaderUser { user_id: string; name: string; points: number; rank: number }

function Shell({ title, subtitle, actions, children }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight md:text-2xl">{title}</h1>
          {subtitle && <p className="mt-1 flex items-center gap-2 text-sm text-[var(--color-mute)]">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </div>
  )
}

function ReportRow({ r }: { r: ReportOut }) {
  return (
    <a href={`#/app/reports`} className="table-row flex items-center gap-4 px-5 py-3.5">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{r.description ?? 'Waste report'}</p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-[var(--color-faint)]">
          <span>{timeAgo(r.created_at)}</span>
          {r.zone_name && <span>· {r.zone_name}</span>}
          {r.ai_category && <span>· AI: {humanize(r.ai_category)}</span>}
        </p>
      </div>
      {r.ai_is_simulated && <Badge tone="purple">sim</Badge>}
      <StatusBadge status={r.status} />
    </a>
  )
}

/* ------------------------------------------------------------------ report wizard */

const WIZARD_STEPS = ['Describe', 'Location', 'Review & submit'] as const

export function ReportWizardPage() {
  const { orgId } = useAuth()
  const queryClient = useQueryClient()
  const [step, setStep] = useState(0)
  const [description, setDescription] = useState('')
  const [categoryGuess, setCategoryGuess] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const [mediaId, setMediaId] = useState<string | null>(null)
  const [lat, setLat] = useState<number | null>(null)
  const [lng, setLng] = useState<number | null>(null)
  const [address, setAddress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [result, setResult] = useState<ReportOut | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: categories } = useQuery({
    queryKey: ['categories'],
    queryFn: () => get<{ code: string; name: string; color_hex: string }[]>('/waste/categories'),
    enabled: !!orgId,
  })

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return postForm<{ id: string; mime_type: string }>('/media/upload', form)
    },
    onSuccess: (data) => {
      setMediaId(data.id)
      setError(null)
    },
    onError: (e: Error) => setError(`Upload failed: ${e.message}`),
  })

  const submitMutation = useMutation({
    mutationFn: () =>
      post<ReportOut>('/waste/reports', {
        description: description || null,
        category_guess: categoryGuess || null,
        latitude: lat,
        longitude: lng,
        address: address || null,
        photo_media_id: mediaId,
      }),
    onSuccess: (r) => {
      setResult(r)
      queryClient.invalidateQueries({ queryKey: ['my-reports-recent'] })
      queryClient.invalidateQueries({ queryKey: ['analytics'] })
      setToast('Report submitted — AI classification attached')
      setTimeout(() => setToast(null), 3500)
    },
    onError: (e: Error) => setError(e.message),
  })

  function pickPhoto(f: File | null) {
    if (!f) return
    if (f.size > 10 * 1024 * 1024) {
      setError('Image exceeds the 10 MiB limit.')
      return
    }
    setPhoto(f)
    setPhotoPreview(URL.createObjectURL(f))
    uploadMutation.mutate(f)
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setError('Geolocation is not available in this browser.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude)
        setLng(pos.coords.longitude)
        setError(null)
      },
      () => setError('Could not read your location. You can click the map instead.'),
      { enableHighAccuracy: true, timeout: 8000 },
    )
  }

  const mapPoints: MapPoint[] = useMemo(() => {
    if (lat === null || lng === null) return []
    return [{ id: 'draft', lat, lng, title: 'Report location', kind: 'report' }]
  }, [lat, lng])

  if (result) {
    return (
      <Shell title="Report submitted">
        <Panel className="mx-auto max-w-xl p-6">
          <div className="mb-4 flex items-center gap-3">
            <CheckCircle2 className="text-emerald-400" size={28} />
            <div>
              <h2 className="text-base font-bold">Thank you</h2>
              <p className="text-xs text-[var(--color-mute)]">{timeAgo(result.created_at)}</p>
            </div>
          </div>
          {result.description && <p className="mb-4 text-sm text-[var(--color-mute)]">{result.description}</p>}
          <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-base)] p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-faint)]">AI classification</span>
              {result.ai_is_simulated && <Badge tone="purple">simulated</Badge>}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold capitalize">{humanize(result.ai_category ?? 'unknown')}</span>
              <span className="text-sm text-[var(--color-mute)]">
                confidence {result.ai_confidence !== null ? fmtPct(result.ai_confidence, 0) : '—'}
              </span>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-[var(--color-faint)]">
              {result.ai_confidence !== null && result.ai_confidence < 0.75
                ? 'Below the confidence threshold — routed to human review. An operator will confirm the classification.'
                : 'Classification accepted; operators can still review and correct it.'}
            </p>
          </div>
          <div className="mt-5 flex gap-2">
            <a href="#/app/reports" className="btn btn-primary flex-1"><ClipboardList size={15} /> Track my reports</a>
            <button className="btn btn-ghost" onClick={() => { setResult(null); setStep(0); setDescription(''); setPhoto(null); setPhotoPreview(null); setMediaId(null); setLat(null); setLng(null) }}>
              Report another
            </button>
          </div>
        </Panel>
        {toast && <Toast message={toast} />}
      </Shell>
    )
  }

  const canNext = step === 0 ? true : step === 1 ? lat !== null && lng !== null : true

  return (
    <Shell title="Report waste" subtitle="Photo, location, done — the AI pipeline classifies it and routes it to operations">
      <Panel className="mx-auto max-w-2xl p-6">
        {/* Steps indicator */}
        <div className="mb-6 flex items-center gap-2">
          {WIZARD_STEPS.map((s, i) => (
            <div key={s} className="flex flex-1 items-center gap-2">
              <div className={clsx('flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold transition-all',
                i < step ? 'bg-emerald-500/20 text-emerald-300' : i === step ? 'bg-emerald-500 text-emerald-950' : 'bg-[var(--color-line)] text-[var(--color-faint)]')}>
                {i < step ? <CheckCircle2 size={14} /> : i + 1}
              </div>
              <span className={clsx('hidden text-xs font-medium sm:block', i === step ? 'text-[var(--color-ink)]' : 'text-[var(--color-faint)]')}>{s}</span>
              {i < WIZARD_STEPS.length - 1 && <div className="h-px flex-1 bg-[var(--color-line)]" />}
            </div>
          ))}
        </div>

        {step === 0 && (
          <div className="flex flex-col gap-5">
            <Field label="What did you spot?" hint="A short description helps the AI classify and prioritize your report.">
              <textarea className="input min-h-24" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. Heap of plastic bottles and cardboard dumped beside the bus stop" />
            </Field>
            <Field label="Your guess (optional)">
              <div className="flex flex-wrap gap-2">
                {(categories ?? []).map((c) => (
                  <button key={c.code} type="button" onClick={() => setCategoryGuess(categoryGuess === c.code ? '' : c.code)}
                    className={clsx('chip border transition-all', categoryGuess === c.code ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300' : 'border-[var(--color-line)] text-[var(--color-mute)] hover:text-[var(--color-ink)]')}>
                    <span className="h-2 w-2 rounded-full" style={{ background: c.color_hex }} />
                    {c.name}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Photo (optional)" hint="JPEG/PNG/WebP up to 10 MiB. Validated and virus-scan queued on the server.">
              <button type="button" onClick={() => fileRef.current?.click()} className="flex h-32 w-full items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--color-line-strong)] text-sm text-[var(--color-mute)] transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
                {photoPreview ? (
                  <img src={photoPreview} alt="Selected" className="h-full w-full rounded-xl object-cover" />
                ) : (
                  <><ImagePlus size={20} /> {uploadMutation.isPending ? 'Uploading…' : 'Add a photo'}</>
                )}
              </button>
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => pickPhoto(e.target.files?.[0] ?? null)} />
            </Field>
          </div>
        )}

        {step === 1 && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-[var(--color-mute)]">Where is it? Tap the map or use your location.</p>
              <button type="button" className="btn btn-ghost btn-sm" onClick={useMyLocation}><MapPin size={14} /> Use my location</button>
            </div>
            <div className="relative">
              <MapView
                className="h-72"
                points={mapPoints}
                center={lat !== null && lng !== null ? [lat, lng] : [12.96, 77.6]}
                zoom={lat !== null ? 16 : 12}
                fit={false}
              />
              <div
                className="absolute inset-0 z-[500] cursor-crosshair"
                onClick={(e) => {
                  const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect()
                  const x = e.clientX - rect.left
                  const y = e.clientY - rect.top
                  // approximate lat/lng from container proportion at current zoom
                  const cLat = lat ?? 12.96
                  const cLng = lng ?? 77.6
                  const zoomLevel = lat !== null ? 16 : 12
                  const degPerPx = 360 / (256 * 2 ** zoomLevel)
                  setLng(cLng + (x - rect.width / 2) * degPerPx)
                  setLat(cLat - (y - rect.height / 2) * degPerPx)
                }}
              />
            </div>
            <Field label="Address or landmark (optional)">
              <input className="input" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="12 Maple Street, near the park entrance" />
            </Field>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col gap-4">
            <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-base)] p-4 text-sm">
              <p className="font-medium">{description || 'No description provided'}</p>
              <p className="mt-2 text-xs text-[var(--color-mute)]">
                {lat !== null && lng !== null ? `Location: ${lat.toFixed(5)}, ${lng.toFixed(5)}` : 'Location missing'}
                {address && ` · ${address}`}
                {categoryGuess && ` · guess: ${humanize(categoryGuess)}`}
              </p>
              <p className="mt-2 text-xs text-[var(--color-faint)]">
                {mediaId ? 'Photo attached and uploaded.' : 'No photo attached.'}
              </p>
            </div>
            <ErrorNote message={error} />
            <button className="btn btn-primary btn-lg" disabled={submitMutation.isPending} onClick={() => submitMutation.mutate()}>
              {submitMutation.isPending ? <Spinner /> : <Camera size={16} />} Submit report
            </button>
          </div>
        )}

        {step < 2 && (
          <div className="mt-6 flex items-center justify-between">
            <button className="btn btn-ghost" disabled={step === 0} onClick={() => setStep(step - 1)}><ChevronLeft size={15} /> Back</button>
            <div className="flex items-center gap-3">
              <ErrorNote message={error} />
              <button className="btn btn-primary" disabled={!canNext} onClick={() => setStep(step + 1)}>
                Continue <ChevronRight size={15} />
              </button>
            </div>
          </div>
        )}
      </Panel>
      {toast && <Toast message={toast} />}
    </Shell>
  )
}

/* ------------------------------------------------------------------ my reports */

export function MyReportsPage() {
  const { orgId } = useAuth()
  const [filter, setFilter] = useState('')
  const { data } = useQuery({
    queryKey: ['my-reports', filter],
    queryFn: () => get<{ items: ReportOut[]; pagination: { total: number } }>(`/waste/reports?mine=true${filter ? `&status_filter=${filter}` : ''}&page_size=50`),
    enabled: !!orgId,
  })

  return (
    <Shell title="My reports" subtitle={`${data?.pagination.total ?? 0} total`}>
      <div className="mb-4 flex flex-wrap gap-2">
        {['', 'submitted', 'in_progress', 'resolved', 'rejected'].map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={clsx('chip border', filter === f ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300' : 'border-[var(--color-line)] text-[var(--color-mute)]')}>
            {f ? humanize(f) : 'All'}
          </button>
        ))}
      </div>
      <Panel>
        {data?.items.length ? (
          <div className="divide-y divide-[var(--color-line)]">
            {data.items.map((r) => <ReportRow key={r.id} r={r} />)}
          </div>
        ) : (
          <EmptyState icon={<ClipboardList size={28} />} title="Nothing here yet" hint="Reports you submit will appear here with their status and AI classification." />
        )}
      </Panel>
    </Shell>
  )
}

/* ------------------------------------------------------------------ impact */

export function ImpactPage() {
  const { orgId } = useAuth()
  const { data: rewards } = useQuery({ queryKey: ['rewards'], queryFn: () => get<RewardsMe>('/rewards/me'), enabled: !!orgId })
  const { data: board } = useQuery({ queryKey: ['leaderboard'], queryFn: () => get<{ items: LeaderUser[] }>('/rewards/leaderboard'), enabled: !!orgId })

  const progress = rewards ? Math.min(100, (rewards.points / rewards.next_level_at) * 100) : 0

  return (
    <Shell title="My impact" subtitle="Sustainability points recognize your community participation — they are not a financial instrument.">
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-4xl font-extrabold tracking-tight text-emerald-400">{rewards?.points ?? 0}</p>
              <p className="mt-1 text-sm text-[var(--color-mute)]">sustainability points · level {rewards?.level ?? 1}</p>
            </div>
            <Sprout size={40} className="text-emerald-500/40" />
          </div>
          <div className="mt-5">
            <div className="mb-1.5 flex justify-between text-[11px] text-[var(--color-faint)]">
              <span>Level {rewards?.level ?? 1}</span>
              <span>{rewards?.next_level_at ?? 500} pts for level {(rewards?.level ?? 1) + 1}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[var(--color-line)]">
              <div className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all duration-700" style={{ width: `${progress}%` }} />
            </div>
          </div>
          <div className="mt-6 grid grid-cols-2 gap-3">
            {Object.entries(rewards?.by_reason ?? {}).map(([reason, pts]) => (
              <div key={reason} className="rounded-lg border border-[var(--color-line)] px-3 py-2">
                <p className="text-[11px] text-[var(--color-faint)]">{humanize(reason)}</p>
                <p className="text-sm font-semibold text-emerald-400">+{pts}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel className="p-6">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold"><Trophy size={15} className="text-amber-400" /> Community leaderboard</h3>
          <div className="flex flex-col gap-2">
            {(board?.items ?? []).map((u: LeaderUser) => (
              <div key={u.user_id} className="flex items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-white/5">
                <span className={clsx('flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold',
                  u.rank === 1 ? 'bg-amber-500/20 text-amber-300' : u.rank <= 3 ? 'bg-emerald-500/15 text-emerald-300' : 'bg-[var(--color-line)] text-[var(--color-mute)]')}>
                  {u.rank}
                </span>
                <span className="flex-1 truncate text-sm">{u.name}</span>
                <span className="text-sm font-semibold text-emerald-400">{u.points}</span>
              </div>
            ))}
            {!board?.items?.length && <p className="text-xs text-[var(--color-faint)]">No community activity yet.</p>}
          </div>
        </Panel>
      </div>

      <Panel className="mt-6 p-5">
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><Leaf size={15} className="text-emerald-400" /> How points work</h3>
        <div className="grid gap-3 text-xs text-[var(--color-mute)] sm:grid-cols-3">
          <div className="rounded-lg border border-[var(--color-line)] p-3">Submit a report <span className="block text-base font-bold text-emerald-400">+10</span></div>
          <div className="rounded-lg border border-[var(--color-line)] p-3">Report resolved <span className="block text-base font-bold text-emerald-400">+25</span></div>
          <div className="rounded-lg border border-[var(--color-line)] p-3">Complaint resolved <span className="block text-base font-bold text-emerald-400">+15</span></div>
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-[var(--color-faint)]">
          EcoMind points are engagement recognition only. They are deliberately not tokens, credits or
          tradable instruments. Impact claims on this platform distinguish measured, estimated and modeled data.
        </p>
      </Panel>
    </Shell>
  )
}

/* ------------------------------------------------------------------ schedule */

export function SchedulePage() {
  const { orgId } = useAuth()
  const { data: analytics } = useQuery({ queryKey: ['analytics', 'citizen'], queryFn: () => get<CitizenAnalytics>('/analytics/citizen'), enabled: !!orgId })

  const days = analytics?.upcoming_collection_days ?? []
  return (
    <Shell title="Collection schedule" subtitle="Scheduled collection activity across the coming days">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {days.map((d) => (
          <Panel key={d.date} className="p-5">
            <p className="text-sm font-semibold">{fmtDate(d.date)}</p>
            <p className="mt-1 text-xs text-[var(--color-mute)]">{d.scheduled} scheduled collections</p>
          </Panel>
        ))}
      </div>
      {!days.length && (
        <Panel>
          <EmptyState icon={<CalendarDays size={28} />} title="No upcoming collections" hint="Your organization has not scheduled upcoming collection events yet." />
        </Panel>
      )}
    </Shell>
  )
}
