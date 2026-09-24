/* Operations management: reports, complaints, fleet, devices, collections. */

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import {
  AlertTriangle, Bot, CheckCircle2, CircleDot, ClipboardList, Cpu, Inbox, MessageSquare,
  Radio, Smartphone, Trash2, Truck, Wifi, WifiOff,
} from 'lucide-react'
import { get, patch, post } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, DemoBadge, EmptyState, ErrorNote, Field, Modal, Panel, PanelHeader, SimBadge, Spinner, StatCard, StatusBadge, Toast } from '../ui'
import { fmtDate, fmtDateTime, fmtKg, humanize, timeAgo } from '../lib/format'

/* ------------------------------------------------------------------ reports */

interface ReportRow {
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
  reporter_name: string | null
  assigned_to_name: string | null
  zone_name: string | null
  resolution_notes: string | null
}

export function OpsReportsPage() {
  const { orgId, hasPerm } = useAuth()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const [lowConfidence, setLowConfidence] = useState(false)
  const [selected, setSelected] = useState<ReportRow | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['ops-reports', statusFilter],
    queryFn: () => get<{ items: ReportRow[] }>(`/waste/reports?page_size=100${statusFilter ? `&status_filter=${statusFilter}` : ''}`),
    enabled: !!orgId,
    refetchInterval: 20000,
  })

  const mutate = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => patch(`/waste/reports/${id}/status`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ops-reports'] })
      queryClient.invalidateQueries({ queryKey: ['ops-reports-map'] })
      setSelected(null)
      setToast('Report updated')
      setTimeout(() => setToast(null), 2000)
    },
  })

  const items = useMemo(() => {
    const all = q.data?.items ?? []
    return lowConfidence ? all.filter((r) => r.ai_confidence != null && r.ai_confidence < 0.75) : all
  }, [q.data, lowConfidence])

  return (
    <PageShell title="Waste reports" subtitle={`${items.length} reports${lowConfidence ? ' with low AI confidence' : ''}`}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {['', 'submitted', 'triaged', 'in_progress', 'resolved', 'rejected'].map((f) => (
          <FilterChip key={f} active={statusFilter === f} label={f ? humanize(f) : 'All statuses'} onClick={() => setStatusFilter(f)} />
        ))}
        <FilterChip active={lowConfidence} label="Low AI confidence" tone="purple" onClick={() => setLowConfidence(!lowConfidence)} />
      </div>

      <Panel>
        {items.length ? (
          <div className="divide-y divide-[var(--color-line)]">
            {items.map((r) => (
              <button key={r.id} className="table-row flex w-full items-center gap-4 px-5 py-3.5 text-left" onClick={() => setSelected(r)}>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{r.description ?? 'No description'}</p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-[var(--color-faint)]">
                    <span>{timeAgo(r.created_at)}</span>
                    {r.reporter_name && <span>· {r.reporter_name}</span>}
                    {r.zone_name && <span>· {r.zone_name}</span>}
                    {r.assigned_to_name && <span>· → {r.assigned_to_name}</span>}
                    {r.ai_category && <span>· AI: {humanize(r.ai_category)}</span>}
                  </p>
                </div>
                {r.ai_is_simulated && <SimBadge />}
                {r.ai_confidence != null && r.ai_confidence < 0.75 && <Badge tone="purple">review</Badge>}
                <StatusBadge status={r.status} />
              </button>
            ))}
          </div>
        ) : (
          <EmptyState icon={<ClipboardList size={28} />} title="No reports match" hint="Try clearing filters." />
        )}
      </Panel>

      <Modal open={!!selected} onClose={() => setSelected(null)} title="Report detail" wide>
        {selected && <ReportDetail r={selected} onMutate={(body) => mutate.mutate({ id: selected.id, body })} busy={mutate.isPending} canManage={hasPerm('report:triage') || hasPerm('report:resolve')} />}
      </Modal>
      {toast && <Toast message={toast} />}
    </PageShell>
  )
}

function ReportDetail({ r, onMutate, busy, canManage }: { r: ReportRow; onMutate: (body: Record<string, unknown>) => void; busy: boolean; canManage: boolean }) {
  const [notes, setNotes] = useState(r.resolution_notes ?? '')
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <div className="flex flex-col gap-4">
        <div>
          <p className="label">Description</p>
          <p className="text-sm">{r.description ?? '—'}</p>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><p className="label">Status</p><StatusBadge status={r.status} /></div>
          <div><p className="label">Severity</p><Badge tone={r.severity === 'urgent' || r.severity === 'high' ? 'danger' : r.severity === 'medium' ? 'warn' : 'info'}>{humanize(r.severity)}</Badge></div>
          <div><p className="label">Reporter</p><p>{r.reporter_name ?? 'Anonymous'}</p></div>
          <div><p className="label">Assignee</p><p>{r.assigned_to_name ?? '—'}</p></div>
          <div><p className="label">Zone</p><p>{r.zone_name ?? '—'}</p></div>
          <div><p className="label">Citizen guess</p><p>{r.category_guess ? humanize(r.category_guess) : '—'}</p></div>
          <div className="col-span-2"><p className="label">Location</p><p className="font-mono text-xs">{r.latitude.toFixed(5)}, {r.longitude.toFixed(5)}</p></div>
        </div>
        {r.address && <div><p className="label">Address</p><p className="text-sm">{r.address}</p></div>}
      </div>

      <div className="flex flex-col gap-4">
        <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-base)] p-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-faint)]"><Bot size={13} /> AI classification</p>
            {r.ai_is_simulated ? <SimBadge /> : null}
          </div>
          <div className="flex items-center justify-between">
            <span className="text-lg font-bold">{r.ai_category ? humanize(r.ai_category) : 'Pending'}</span>
            <span className="text-sm text-[var(--color-mute)]">
              {r.ai_confidence != null ? `${(r.ai_confidence * 100).toFixed(0)}% confidence` : '—'}
            </span>
          </div>
          {r.ai_confidence != null && r.ai_confidence < 0.75 && (
            <p className="mt-2 text-[11px] text-amber-300">Below the 75% acceptance threshold — confirm or correct via triage before resolution.</p>
          )}
        </div>

        {canManage && r.status !== 'resolved' && r.status !== 'rejected' && r.status !== 'closed' && (
          <>
            <Field label="Resolution notes">
              <textarea className="input min-h-20" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="What action was taken?" />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <button className="btn btn-ghost" disabled={busy} onClick={() => onMutate({ status: 'triaged', note: 'Triage started' })}>Triage</button>
              <button className="btn btn-ghost" disabled={busy} onClick={() => onMutate({ status: 'in_progress', note: notes || null })}>Start work</button>
              <button className="btn btn-primary" disabled={busy} onClick={() => onMutate({ status: 'resolved', resolution_notes: notes || null })}>Resolve</button>
              <button className="btn btn-ghost text-rose-300" disabled={busy} onClick={() => onMutate({ status: 'rejected', resolution_notes: notes || null })}>Reject</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ complaints */

interface CommentRow {
  id: string
  author_name: string | null
  body: string
  is_internal: boolean
  created_at: string
}

interface ComplaintRow {
  id: string
  subject: string
  description: string | null
  status: string
  priority: string
  category: string
  reporter_name: string | null
  assignee_name: string | null
  assigned_to: string | null
  zone_id: string | null
  latitude: number | null
  longitude: number | null
  due_at: string | null
  first_response_at: string | null
  resolved_at: string | null
  resolution_summary: string | null
  created_at: string
}

export function ComplaintsPage() {
  const { orgId } = useAuth()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('submitted')
  const [selected, setSelected] = useState<ComplaintRow | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['complaints', statusFilter],
    queryFn: () => get<{ items: ComplaintRow[] }>(`/complaints?${statusFilter ? `status_filter=${statusFilter}` : ''}page_size=100`),
    enabled: !!orgId,
    refetchInterval: 20000,
  })

  const detailQ = useQuery({
    queryKey: ['complaint', selected?.id],
    queryFn: () => get<ComplaintRow>(`/complaints/${selected?.id}`),
    enabled: !!selected,
  })
  const commentsQ = useQuery({
    queryKey: ['complaint-comments', selected?.id],
    queryFn: () => get<CommentRow[]>(`/complaints/${selected?.id}/comments`),
    enabled: !!selected,
  })

  const mutate = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => patch(`/complaints/${id}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['complaints'] })
      queryClient.invalidateQueries({ queryKey: ['complaint'] })
      setToast('Complaint updated')
      setTimeout(() => setToast(null), 2000)
    },
  })

  const c = detailQ.data

  return (
    <PageShell title="Complaints" subtitle="Citizen complaints with SLA due dates tracked against resolution">
      <div className="mb-4 flex flex-wrap gap-2">
        {['submitted', 'triaged', 'assigned', 'in_progress', 'resolved', 'closed', ''].map((f) => (
          <FilterChip key={f} active={statusFilter === f} label={f ? humanize(f) : 'All'} onClick={() => setStatusFilter(f)} />
        ))}
      </div>
      <Panel>
        {q.data?.items.length ? (
          <div className="divide-y divide-[var(--color-line)]">
            {q.data.items.map((cm) => {
              const overdue = cm.due_at && new Date(cm.due_at) < new Date() && !cm.resolved_at
              return (
                <button key={cm.id} className="table-row flex w-full items-center gap-4 px-5 py-3.5 text-left" onClick={() => setSelected(cm)}>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{cm.subject}</p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-[var(--color-faint)]">
                      <span>{timeAgo(cm.created_at)}</span>
                      {cm.reporter_name && <span>· {cm.reporter_name}</span>}
                      {cm.assignee_name && <span>· → {cm.assignee_name}</span>}
                    </p>
                  </div>
                  {overdue && <Badge tone="danger">overdue</Badge>}
                  <StatusBadge status={cm.status} />
                </button>
              )
            })}
          </div>
        ) : (
          <EmptyState icon={<Inbox size={28} />} title="No complaints" hint="Nothing matching this filter." />
        )}
      </Panel>

      <Modal open={!!selected} onClose={() => setSelected(null)} title={c?.subject ?? ''} wide>
        {c && (
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="flex flex-col gap-4">
              {c.description && <div><p className="label">Description</p><p className="text-sm">{c.description}</p></div>}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><p className="label">Priority</p><Badge tone={c.priority === 'urgent' ? 'danger' : c.priority === 'high' ? 'warn' : 'info'}>{humanize(c.priority)}</Badge></div>
                <div><p className="label">Category</p><p>{humanize(c.category)}</p></div>
                <div><p className="label">SLA due</p><p className={clsx(c.due_at && new Date(c.due_at) < new Date() && !c.resolved_at ? 'font-semibold text-rose-400' : '')}>{c.due_at ? fmtDateTime(c.due_at) : '—'}</p></div>
                <div><p className="label">First response</p><p>{c.first_response_at ? fmtDateTime(c.first_response_at) : '—'}</p></div>
              </div>
              {c.resolution_summary && <div><p className="label">Resolution</p><p className="text-sm">{c.resolution_summary}</p></div>}
              <div>
                <p className="label mb-2">Comments ({commentsQ.data?.length ?? 0})</p>
                <div className="flex max-h-48 flex-col gap-2 overflow-auto">
                  {(commentsQ.data ?? []).map((res) => (
                    <div key={res.id} className={clsx('rounded-lg border px-3 py-2', res.is_internal ? 'border-dashed border-[var(--color-line)]' : 'border-emerald-500/20 bg-emerald-500/5')}>
                      <p className="text-[11px] text-[var(--color-faint)]">{res.author_name ?? 'System'} · {timeAgo(res.created_at)}{res.is_internal && ' · internal note'}</p>
                      <p className="mt-1 text-sm">{res.body}</p>
                    </div>
                  ))}
                  {!commentsQ.data?.length && <p className="text-xs text-[var(--color-faint)]">No comments yet.</p>}
                </div>
              </div>
            </div>

            <ComplaintActions c={c} onMutate={(body) => mutate.mutate({ id: c.id, body })} busy={mutate.isPending} />
          </div>
        )}
      </Modal>
      {toast && <Toast message={toast} />}
    </PageShell>
  )
}

function ComplaintActions({ c, onMutate, busy }: { c: ComplaintRow; onMutate: (body: Record<string, unknown>) => void; busy: boolean }) {
  const queryClient = useQueryClient()
  const [body, setBody] = useState('')
  const [internal, setInternal] = useState(false)
  const [summary, setSummary] = useState('')
  const [assignee, setAssignee] = useState('')

  const resp = useMutation({
    mutationFn: () => post(`/complaints/${c.id}/comments`, { body, is_internal: internal }),
    onSuccess: () => {
      setBody('')
      queryClient.invalidateQueries({ queryKey: ['complaint-comments', c.id] })
      queryClient.invalidateQueries({ queryKey: ['complaint', c.id] })
    },
  })
  const { data: members } = useQuery({
    queryKey: ['assignable-users'],
    queryFn: () => get<{ items: { user_id: string; full_name: string; role_code: string }[] }>('/organizations/current/members?page_size=100'),
  })
  const staff = (members?.items ?? []).filter((m) => !['citizen', 'viewer'].includes(m.role_code))

  const open = !['resolved', 'closed', 'rejected'].includes(c.status)

  return (
    <div className="flex flex-col gap-4">
      {open && (
        <div className="grid grid-cols-2 gap-2">
          <button className="btn btn-primary btn-sm" disabled={busy || c.status !== 'submitted'} onClick={() => onMutate({ new_status: 'triaged' })}>Triage</button>
          <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onMutate({ new_status: 'in_progress' })}>Start work</button>
        </div>
      )}
      <Field label="Re-assign">
        <div className="flex gap-2">
          <select className="input" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value="">Select staff…</option>
            {staff.map((u) => <option key={u.user_id} value={u.user_id}>{u.full_name} · {humanize(u.role_code)}</option>)}
          </select>
          <button className="btn btn-ghost btn-sm" disabled={!assignee || busy} onClick={() => onMutate({ assignee })}>Assign</button>
        </div>
      </Field>
      {open && (
        <Field label="Resolution summary (required to resolve)">
          <textarea className="input min-h-16" value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="What was done about this complaint?" />
        </Field>
      )}
      {open && (
        <button className="btn btn-primary btn-sm" disabled={busy || summary.length < 3} onClick={() => onMutate({ new_status: 'resolved', resolution_summary: summary })}>
          <CheckCircle2 size={14} /> Resolve complaint
        </button>
      )}
      <Field label="Add comment">
        <textarea className="input min-h-20" value={body} onChange={(e) => setBody(e.target.value)} placeholder="Message the citizen (or an internal note)" />
      </Field>
      <label className="flex items-center gap-2 text-xs text-[var(--color-mute)]">
        <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} className="h-4 w-4 accent-emerald-500" />
        Internal note (not visible to the citizen)
      </label>
      <button className="btn btn-ghost btn-sm" disabled={!body || resp.isPending} onClick={() => resp.mutate()}>
        {resp.isPending ? <Spinner /> : <MessageSquare size={14} />} Post comment
      </button>
      <p className="text-[11px] leading-relaxed text-[var(--color-faint)]">
        The first public comment records the SLA first-response; unresolved complaints past their due
        date are surfaced as overdue until resolved or closed.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ fleet */

interface Vehicle {
  id: string
  code: string
  name: string | null
  vehicle_type: string
  status: string
  fuel_type: string
  plate_number: string | null
  capacity_kg: number | null
  current_lat: number | null
  current_lng: number | null
  current_route_id: string | null
  last_ping_at: string | null
  position_is_simulated: boolean
}

const VEHICLE_TYPES = ['compactor_truck', 'tipper_truck', 'van', 'ev_van', 'tricycle', 'loader', 'other']
const FUEL_TYPES = ['diesel', 'petrol', 'cng', 'electric', 'hybrid']

export function FleetPage() {
  const { orgId } = useAuth()
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)

  const q = useQuery({ queryKey: ['vehicles'], queryFn: () => get<Vehicle[]>('/fleet/vehicles'), enabled: !!orgId, refetchInterval: 20000 })

  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => post('/fleet/vehicles', body),
    onSuccess: () => { setAddOpen(false); queryClient.invalidateQueries({ queryKey: ['vehicles'] }) },
  })

  return (
    <PageShell
      title="Fleet"
      subtitle="Vehicles, capacity and live positions"
      actions={<button className="btn btn-primary" onClick={() => setAddOpen(true)}><Truck size={15} /> Add vehicle</button>}
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(q.data ?? []).map((v) => (
          <Panel key={v.id} className="p-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/10 text-violet-300"><Truck size={17} /></div>
                <div>
                  <p className="text-sm font-bold">{v.code}</p>
                  <p className="text-[11px] text-[var(--color-faint)]">{v.name ?? humanize(v.vehicle_type)} · {humanize(v.fuel_type)}</p>
                </div>
              </div>
              <StatusBadge status={v.status} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div><p className="text-[10px] text-[var(--color-faint)]">Capacity</p><p className="font-semibold">{v.capacity_kg ? `${v.capacity_kg} kg` : '—'}</p></div>
              <div><p className="text-[10px] text-[var(--color-faint)]">Plate</p><p className="font-mono font-semibold">{v.plate_number ?? '—'}</p></div>
              <div><p className="text-[10px] text-[var(--color-faint)]">Last ping</p><p className="font-semibold">{v.last_ping_at ? timeAgo(v.last_ping_at) : 'never'}</p></div>
              <div>
                <p className="text-[10px] text-[var(--color-faint)]">Position</p>
                <p className="font-mono">
                  {v.current_lat != null ? `${v.current_lat.toFixed(3)},${v.current_lng?.toFixed(3)}` : 'unknown'}
                  {v.position_is_simulated && <span className="ml-1.5"><SimBadge label="SIM" /></span>}
                </p>
              </div>
            </div>
            {v.current_route_id && (
              <a className="btn btn-ghost btn-sm mt-4 w-full" href={`#/ops/routes/${v.current_route_id}`}>View current route</a>
            )}
          </Panel>
        ))}
      </div>
      {!q.data?.length && <Panel><EmptyState icon={<Truck size={28} />} title="No vehicles" hint="Register vehicles to assign them to optimized routes." /></Panel>}

      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add vehicle">
        <CreateVehicle onSubmit={(b) => create.mutate(b)} busy={create.isPending} error={create.error instanceof Error ? create.error.message : null} />
      </Modal>
    </PageShell>
  )
}

function CreateVehicle({ onSubmit, busy, error }: { onSubmit: (body: Record<string, unknown>) => void; busy: boolean; error: string | null }) {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [type, setType] = useState('compactor_truck')
  const [fuel, setFuel] = useState('diesel')
  const [plate, setPlate] = useState('')
  const [capacity, setCapacity] = useState('5000')
  return (
    <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); onSubmit({ code, name: name || null, vehicle_type: type, fuel_type: fuel, plate_number: plate || null, capacity_kg: capacity ? parseFloat(capacity) : null }) }}>
      <Field label="Code"><input className="input" required value={code} onChange={(e) => setCode(e.target.value)} placeholder="TRK-042" /></Field>
      <Field label="Name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Riverline collector" /></Field>
      <Field label="Type">
        <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
          {VEHICLE_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
        </select>
      </Field>
      <Field label="Fuel">
        <select className="input" value={fuel} onChange={(e) => setFuel(e.target.value)}>
          {FUEL_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
        </select>
      </Field>
      <Field label="Plate number"><input className="input" value={plate} onChange={(e) => setPlate(e.target.value)} placeholder="KA-01-AB-1234" /></Field>
      <Field label="Capacity (kg)"><input className="input" type="number" min="0" value={capacity} onChange={(e) => setCapacity(e.target.value)} /></Field>
      <div className="sm:col-span-2">
        <ErrorNote message={error} />
        <button className="btn btn-primary w-full" disabled={busy}>{busy ? <Spinner /> : null} Create vehicle</button>
      </div>
    </form>
  )
}

/* ------------------------------------------------------------------ devices */

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

export function DevicesPage() {
  const { orgId, isDemo } = useAuth()
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)

  const q = useQuery({ queryKey: ['devices'], queryFn: () => get<Device[]>('/iot/devices'), enabled: !!orgId, refetchInterval: 15000 })

  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => post<{ device_key: string; api_key: string }>('/iot/devices', body),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['devices'] }) },
  })

  const online = (q.data ?? []).filter((d) => d.status === 'active').length
  const sim = (q.data ?? []).filter((d) => d.is_simulated).length

  return (
    <PageShell
      title="IoT devices"
      subtitle={
        <span className="inline-flex items-center gap-2">
          {isDemo && <><DemoBadge /> {sim} of {q.data?.length ?? 0} devices emit SIMULATED telemetry</>}
          {!isDemo && sim > 0 && <>{sim} simulated device(s) present</>}
          {!isDemo && sim === 0 && `${online}/${q.data?.length ?? 0} active`}
        </span>
      }
      actions={<button className="btn btn-primary" onClick={() => setAddOpen(true)}><Cpu size={15} /> Register device</button>}
    >
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Total devices" value={q.data?.length ?? 0} icon={<Cpu size={15} />} />
        <StatCard label="Active" value={online} icon={<Wifi size={15} />} tone="brand" />
        <StatCard label="Simulated" value={sim} icon={<Radio size={15} />} tone="purple" />
        <StatCard label="Inactive" value={(q.data?.length ?? 0) - online} icon={<WifiOff size={15} />} tone="danger" />
      </div>

      <Panel>
        {q.data?.length ? (
          <div className="divide-y divide-[var(--color-line)]">
            {q.data.map((d) => (
              <div key={d.id} className="table-row flex flex-wrap items-center gap-4 px-5 py-3.5">
                <div className={clsx('flex h-9 w-9 items-center justify-center rounded-lg', d.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400')}>
                  <Smartphone size={15} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm font-semibold">
                    {d.name}
                    {d.is_simulated && <SimBadge />}
                  </p>
                  <p className="text-[11px] text-[var(--color-faint)]">
                    <span className="font-mono">{d.device_key}</span> · {humanize(d.kind)} · last telemetry {d.last_telemetry_at ? timeAgo(d.last_telemetry_at) : 'never'}
                  </p>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  {d.current_fill_pct != null && (
                    <span className={clsx('font-semibold', d.current_fill_pct > 85 ? 'text-rose-400' : d.current_fill_pct > 60 ? 'text-amber-400' : 'text-sky-400')}>
                      {d.current_fill_pct.toFixed(0)}% fill
                    </span>
                  )}
                  {d.current_battery_pct != null && <span className={d.current_battery_pct < 15 ? 'text-rose-400' : 'text-[var(--color-mute)]'}>{d.current_battery_pct.toFixed(0)}% bat</span>}
                </div>
                <StatusBadge status={d.status} />
              </div>
            ))}
          </div>
        ) : (
          <EmptyState icon={<Cpu size={28} />} title="No devices registered" hint="Register smart-bin sensors to receive authenticated telemetry." />
        )}
      </Panel>

      <Modal open={addOpen} onClose={() => { setAddOpen(false); create.reset() }} title="Register device">
        <RegisterDevice onSubmit={(b) => create.mutate(b)} busy={create.isPending} error={create.error instanceof Error ? create.error.message : null} created={create.data} />
      </Modal>
    </PageShell>
  )
}

function RegisterDevice({ onSubmit, busy, error, created }: { onSubmit: (body: Record<string, unknown>) => void; busy: boolean; error: string | null; created: { device_key: string; api_key: string } | undefined }) {
  const [name, setName] = useState('')
  const [kind, setKind] = useState('fill_sensor')
  const [lat, setLat] = useState('')
  const [lng, setLng] = useState('')

  if (created) {
    return (
      <div className="flex flex-col gap-3 text-center">
        <CheckCircle2 className="mx-auto text-emerald-400" size={28} />
        <p className="text-sm">Device registered. Provision this API key to the device — it is shown once.</p>
        <code className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 font-mono text-xs break-all text-emerald-300">{created.api_key}</code>
        <p className="text-[11px] text-[var(--color-faint)]">
          Telemetry ingestion must authenticate with this key (X-Device-Key header); device IDs alone are never trusted.
        </p>
      </div>
    )
  }

  return (
    <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); onSubmit({ name, kind, latitude: lat ? parseFloat(lat) : null, longitude: lng ? parseFloat(lng) : null }) }}>
      <Field label="Device name"><input className="input" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Riverline Bin 014 sensor" /></Field>
      <Field label="Kind">
        <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
          {['fill_sensor', 'camera', 'weight_scale', 'temperature_sensor', 'gps_tracker', 'compactor', 'other'].map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
        </select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Latitude"><input className="input" type="number" step="0.0001" value={lat} onChange={(e) => setLat(e.target.value)} /></Field>
        <Field label="Longitude"><input className="input" type="number" step="0.0001" value={lng} onChange={(e) => setLng(e.target.value)} /></Field>
      </div>
      <ErrorNote message={error} />
      <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : null} Register</button>
    </form>
  )
}

/* ------------------------------------------------------------------ collections */

interface CollectionEvent {
  id: string
  collection_point_id: string
  point_name: string | null
  point_code: string | null
  waste_category_id: string | null
  scheduled_date: string
  status: string
  route_id: string | null
  vehicle_id: string | null
  completed_at: string | null
  weight_kg: number | null
  contamination_flag: boolean
  skip_reason: string | null
  notes: string | null
}

export function CollectionPage() {
  const { orgId } = useAuth()
  const [statusFilter, setStatusFilter] = useState('')

  // last 30 days window
  const dateFrom = useMemo(() => {
    const d = new Date()
    d.setDate(d.getDate() - 29)
    return d.toISOString().slice(0, 10)
  }, [])

  const q = useQuery({
    queryKey: ['collections', statusFilter, dateFrom],
    queryFn: () => get<{ items: CollectionEvent[]; pagination: { total: number } }>(`/collection/events?date_from=${dateFrom}${statusFilter ? `&status_filter=${statusFilter}` : ''}&page_size=100`),
    enabled: !!orgId,
  })

  const totals = (q.data?.items ?? []).reduce(
    (acc, e) => {
      acc.weight += e.weight_kg ?? 0
      if (e.status === 'completed') acc.completed += 1
      if (e.status === 'missed') acc.missed += 1
      if (e.contamination_flag) acc.contaminated += 1
      return acc
    },
    { weight: 0, completed: 0, missed: 0, contaminated: 0 },
  )

  return (
    <PageShell title="Collection events" subtitle="Ground-truth waste tonnage from schedules and route execution (last 30 days)">
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Events" value={q.data?.pagination.total ?? 0} icon={<Trash2 size={15} />} />
        <StatCard label="Collected weight" value={fmtKg(totals.weight)} icon={<CircleDot size={15} />} tone="purple" />
        <StatCard label="Completed" value={totals.completed} icon={<CheckCircle2 size={15} />} tone="brand" />
        <StatCard label="Missed" value={totals.missed} icon={<AlertTriangle size={15} />} tone="danger" />
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {['', 'scheduled', 'completed', 'missed', 'skipped', 'partial'].map((f) => (
          <FilterChip key={f} active={statusFilter === f} label={f ? humanize(f) : 'All'} onClick={() => setStatusFilter(f)} />
        ))}
      </div>
      <Panel>
        {q.data?.items.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-line)] text-[11px] uppercase tracking-wider text-[var(--color-faint)]">
                  <th className="px-5 py-3 font-medium">Point</th>
                  <th className="px-3 py-3 font-medium">Date</th>
                  <th className="px-3 py-3 font-medium">Completed</th>
                  <th className="px-3 py-3 font-medium">Weight</th>
                  <th className="px-3 py-3 font-medium">Flags</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((e) => (
                  <tr key={e.id} className="border-b border-[var(--color-line)]/50 last:border-0">
                    <td className="px-5 py-3">
                      <p>{e.point_name ?? e.point_code ?? '—'}</p>
                    </td>
                    <td className="px-3 py-3 text-xs">{fmtDate(e.scheduled_date)}</td>
                    <td className="px-3 py-3 text-xs">{e.completed_at ? fmtDateTime(e.completed_at) : '—'}</td>
                    <td className="px-3 py-3">{e.weight_kg != null ? `${e.weight_kg} kg` : '—'}</td>
                    <td className="px-3 py-3">
                      {e.contamination_flag && <Badge tone="warn">contaminated</Badge>}
                      {e.skip_reason && <span className="ml-1"><Badge tone="neutral">{humanize(e.skip_reason)}</Badge></span>}
                    </td>
                    <td className="px-5 py-3"><StatusBadge status={e.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon={<Trash2 size={28} />} title="No collection events" hint="Events come from schedules and route stop execution." />
        )}
      </Panel>
    </PageShell>
  )
}

/* ------------------------------------------------------------------ shared */

function PageShell({ title, subtitle, actions, children }: { title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight md:text-2xl">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-[var(--color-mute)]">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </div>
  )
}

function FilterChip({ active, label, onClick, tone }: { active: boolean; label: string; onClick: () => void; tone?: 'purple' }) {
  return (
    <button
      onClick={onClick}
      className={clsx('chip border transition-all',
        active
          ? tone === 'purple' ? 'border-purple-500/40 bg-purple-500/15 text-purple-300' : 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300'
          : 'border-[var(--color-line)] text-[var(--color-mute)] hover:text-[var(--color-ink)]')}
    >
      {label}
    </button>
  )
}
