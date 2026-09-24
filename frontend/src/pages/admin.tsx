/* Administration: members, organization settings, alert rules, audit log. */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clsx } from 'clsx'
import {
  Bell, Check, Copy, Mail, Plus, ScrollText, Settings, Shield, ShieldCheck, UserPlus, Users,
} from 'lucide-react'
import { get, patch, post } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, EmptyState, ErrorNote, Field, Modal, Panel, PanelHeader, Spinner, StatusBadge, Toast } from '../ui'
import { fmtDateTime, humanize, timeAgo } from '../lib/format'

/* ------------------------------------------------------------------ members */

interface Member {
  user_id: string
  email: string
  full_name: string
  role_code: string
  is_active: boolean
  joined_at: string
}

const ROLE_OPTIONS = [
  'org_admin', 'ops_manager', 'field_supervisor', 'collector',
  'sustainability_analyst', 'citizen', 'viewer',
]

export function AdminUsersPage() {
  const { orgId } = useAuth()
  const queryClient = useQueryClient()
  const [inviteOpen, setInviteOpen] = useState(false)
  const [selected, setSelected] = useState<Member | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['members'],
    queryFn: () => get<{ items: Member[]; pagination: { total: number } }>('/organizations/current/members?page_size=100'),
    enabled: !!orgId,
  })

  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => patch(`/organizations/current/members/${id}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] })
      setSelected(null)
      setToast('Member updated')
      setTimeout(() => setToast(null), 2000)
    },
  })

  return (
    <AdminShell
      title="Members & roles"
      subtitle={`${q.data?.pagination.total ?? 0} members · role-based access control enforced server-side`}
      actions={<button className="btn btn-primary" onClick={() => setInviteOpen(true)}><UserPlus size={15} /> Invite user</button>}
    >
      <Panel>
        {q.data?.items.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-line)] text-[11px] uppercase tracking-wider text-[var(--color-faint)]">
                  <th className="px-5 py-3 font-medium">Member</th>
                  <th className="px-3 py-3 font-medium">Role</th>
                  <th className="px-3 py-3 font-medium">Active</th>
                  <th className="px-3 py-3 font-medium">Joined</th>
                  <th className="px-5 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((m) => (
                  <tr key={m.user_id} className="border-b border-[var(--color-line)]/50 last:border-0">
                    <td className="px-5 py-3">
                      <p className="font-medium">{m.full_name}</p>
                      <p className="text-[11px] text-[var(--color-faint)]">{m.email}</p>
                    </td>
                    <td className="px-3 py-3"><RoleBadge role={m.role_code} /></td>
                    <td className="px-3 py-3">
                      {m.is_active ? <Badge tone="brand">active</Badge> : <Badge tone="danger">disabled</Badge>}
                    </td>
                    <td className="px-3 py-3 text-xs">{timeAgo(m.joined_at)}</td>
                    <td className="px-5 py-3">
                      <button className="btn btn-ghost btn-sm" onClick={() => setSelected(m)}>Manage</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon={<Users size={28} />} title="No members" />
        )}
      </Panel>

      <Modal open={!!selected} onClose={() => setSelected(null)} title={selected?.full_name ?? ''}>
        {selected && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><p className="label">Email</p><p className="truncate">{selected.email}</p></div>
              <div><p className="label">Joined</p><p>{timeAgo(selected.joined_at)}</p></div>
            </div>
            <Field label="Role">
              <div className="flex flex-wrap gap-2">
                {ROLE_OPTIONS.map((r) => (
                  <button key={r} className={clsx('chip border', selected.role_code === r ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300' : 'border-[var(--color-line)] text-[var(--color-mute)]')}
                    onClick={() => update.mutate({ id: selected.user_id, body: { role_code: r } })}>
                    {humanize(r)}
                  </button>
                ))}
              </div>
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <button className="btn btn-ghost btn-sm" disabled={selected.is_active || update.isPending}
                onClick={() => update.mutate({ id: selected.user_id, body: { is_active: true } })}>
                <Check size={14} /> Activate
              </button>
              <button className="btn btn-ghost btn-sm text-rose-300" disabled={!selected.is_active || update.isPending}
                onClick={() => update.mutate({ id: selected.user_id, body: { is_active: false } })}>
                <Shield size={14} /> Deactivate
              </button>
            </div>
            <p className="text-[11px] leading-relaxed text-[var(--color-faint)]">
              Role and active changes take effect immediately; permissions are re-evaluated on every request.
            </p>
          </div>
        )}
      </Modal>

      <Modal open={inviteOpen} onClose={() => setInviteOpen(false)} title="Invite user">
        <InviteForm onSubmit={(b) => post('/organizations/current/invitations', b)} onDone={() => { setInviteOpen(false); setToast('Invitation created'); setTimeout(() => setToast(null), 2500) }} />
      </Modal>
      {toast && <Toast message={toast} />}
    </AdminShell>
  )
}

function InviteForm({ onSubmit, onDone }: { onSubmit: (body: Record<string, unknown>) => Promise<unknown>; onDone: () => void }) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('citizen')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [token, setToken] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const out = (await onSubmit({ email, role_code: role })) as { invite_token: string }
      setToken(out.invite_token)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invite failed')
    } finally {
      setBusy(false)
    }
  }

  if (token) {
    return (
      <div className="flex flex-col gap-3 text-center">
        <Check className="mx-auto text-emerald-400" size={28} />
        <p className="text-sm">Invitation created. Share this one-time token with the invitee — it is not shown again.</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 font-mono text-xs break-all text-emerald-300">{token}</code>
          <button className="btn btn-ghost btn-sm" onClick={() => navigator.clipboard?.writeText(token)}><Copy size={14} /></button>
        </div>
        <p className="text-[11px] text-[var(--color-faint)]">They accept it at POST /organizations/invitations/accept with the token.</p>
        <button className="btn btn-primary" onClick={onDone}>Done</button>
      </div>
    )
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={submit}>
      <Field label="Email"><input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="new.member@organization.org" /></Field>
      <Field label="Role">
        <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
          {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{humanize(r)}</option>)}
        </select>
      </Field>
      <ErrorNote message={error} />
      <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : <Mail size={15} />} Create invitation</button>
    </form>
  )
}

function RoleBadge({ role }: { role: string }) {
  const tone = role === 'org_admin' ? 'danger' : role === 'citizen' ? 'brand' : 'info'
  return <Badge tone={tone as 'danger' | 'brand' | 'info'}>{humanize(role)}</Badge>
}

/* ------------------------------------------------------------------ settings */

interface OrgSettings {
  id: string
  name: string
  slug: string
  org_type: string
  status: string
  timezone: string
  locale: string
  city: string | null
  country: string | null
  contact_email: string | null
  is_demo: boolean
  allow_citizen_signup: boolean
  allow_anonymous_reports: boolean
  settings: Record<string, unknown>
  created_at: string
}

interface AlertRule {
  id: string
  name: string
  metric: string
  operator: string
  threshold: number
  severity: string
  cooldown_minutes: number
  is_active: boolean
}

export function AdminSettingsPage() {
  const { orgId, hasPerm } = useAuth()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'general' | 'alerts'>('general')
  const [toast, setToast] = useState<string | null>(null)

  const q = useQuery({ queryKey: ['org-settings'], queryFn: () => get<OrgSettings>('/organizations/current'), enabled: !!orgId })
  const rulesQ = useQuery({ queryKey: ['alert-rules'], queryFn: () => get<AlertRule[]>('/iot/alert-rules'), enabled: !!orgId })

  const update = useMutation({
    mutationFn: (body: Record<string, unknown>) => patch('/organizations/current', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-settings'] })
      setToast('Settings saved')
      setTimeout(() => setToast(null), 2000)
    },
  })

  if (q.isLoading || !q.data) return <div className="flex min-h-[50vh] items-center justify-center"><Spinner className="text-emerald-400" /></div>
  const s = q.data

  return (
    <AdminShell title="Settings" subtitle="Organization configuration">
      <div className="flex flex-wrap gap-1 rounded-xl border border-[var(--color-line)] bg-[var(--color-base)] p-1">
        {[
          { key: 'general', label: 'General', icon: <Settings size={14} /> },
          { key: 'alerts', label: 'Alert rules', icon: <Bell size={14} /> },
        ].map((t) => (
          <button key={t.key} onClick={() => setTab(t.key as typeof tab)}
            className={clsx('flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all',
              tab === t.key ? 'bg-emerald-500/15 text-emerald-300' : 'text-[var(--color-mute)] hover:text-[var(--color-ink)]')}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === 'general' && (
        <Panel className="mt-4 p-6">
          <GeneralSettings s={s} onSave={(b) => update.mutate(b)} busy={update.isPending} />
        </Panel>
      )}

      {tab === 'alerts' && (
        <div className="mt-4">
          <AlertRulesPanel rules={rulesQ.data} canManage={hasPerm('alert:manage')} />
        </div>
      )}
      {toast && <Toast message={toast} />}
    </AdminShell>
  )
}

function GeneralSettings({ s, onSave, busy }: { s: OrgSettings; onSave: (body: Record<string, unknown>) => void; busy: boolean }) {
  const [name, setName] = useState(s.name)
  const [city, setCity] = useState(s.city ?? '')
  const [country, setCountry] = useState(s.country ?? '')
  const [tz, setTz] = useState(s.timezone)
  const [contact, setContact] = useState(s.contact_email ?? '')
  const [citizenSignup, setCitizenSignup] = useState(s.allow_citizen_signup)
  const [anonReports, setAnonReports] = useState(s.allow_anonymous_reports)
  const dirty = name !== s.name || city !== (s.city ?? '') || country !== (s.country ?? '') || tz !== s.timezone
    || contact !== (s.contact_email ?? '') || citizenSignup !== s.allow_citizen_signup || anonReports !== s.allow_anonymous_reports
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Organization name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Slug" hint="Immutable identifier"><input className="input" value={s.slug} disabled /></Field>
      <Field label="City"><input className="input" value={city} onChange={(e) => setCity(e.target.value)} /></Field>
      <Field label="Country"><input className="input" value={country} onChange={(e) => setCountry(e.target.value)} /></Field>
      <Field label="Timezone"><input className="input" value={tz} onChange={(e) => setTz(e.target.value)} placeholder="Asia/Kolkata" /></Field>
      <Field label="Contact email"><input className="input" type="email" value={contact} onChange={(e) => setContact(e.target.value)} /></Field>
      <label className="flex items-center gap-3 rounded-lg border border-[var(--color-line)] px-3 py-2.5">
        <input type="checkbox" checked={citizenSignup} onChange={(e) => setCitizenSignup(e.target.checked)} className="h-4 w-4 accent-emerald-500" />
        <span className="text-sm">Allow public citizen signup (listed on registration)</span>
      </label>
      <label className="flex items-center gap-3 rounded-lg border border-[var(--color-line)] px-3 py-2.5">
        <input type="checkbox" checked={anonReports} onChange={(e) => setAnonReports(e.target.checked)} className="h-4 w-4 accent-emerald-500" />
        <span className="text-sm">Allow anonymous waste reports</span>
      </label>
      <div className="sm:col-span-2">
        <button className="btn btn-primary" disabled={!dirty || busy} onClick={() => onSave({
          name, city: city || null, country: country || null, timezone: tz,
          contact_email: contact || null, allow_citizen_signup: citizenSignup, allow_anonymous_reports: anonReports,
        })}>
          {busy ? <Spinner /> : null} Save changes
        </button>
      </div>
    </div>
  )
}

function AlertRulesPanel({ rules, canManage }: { rules: AlertRule[] | undefined; canManage: boolean }) {
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => post('/iot/alert-rules', body),
    onSuccess: () => {
      setAddOpen(false)
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] })
    },
  })

  return (
    <Panel>
      <PanelHeader
        title="Telemetry alert rules"
        subtitle="Evaluated on every device reading — org-scoped"
        icon={<ShieldCheck size={15} />}
        actions={canManage && (
          <button className="btn btn-primary btn-sm" onClick={() => setAddOpen(true)}><Plus size={14} /> New rule</button>
        )}
      />
      <div className="divide-y divide-[var(--color-line)]">
        {(rules ?? []).map((rule) => (
          <div key={rule.id} className="table-row flex flex-wrap items-center gap-4 px-5 py-3.5">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{rule.name}</p>
              <p className="font-mono text-[11px] text-[var(--color-faint)]">
                {rule.metric} {rule.operator} {rule.threshold} · cooldown {rule.cooldown_minutes} min
              </p>
            </div>
            <Badge tone={rule.severity === 'critical' ? 'danger' : rule.severity === 'high' ? 'warn' : 'info'}>{humanize(rule.severity)}</Badge>
            <Badge tone={rule.is_active ? 'brand' : 'neutral'}>{rule.is_active ? 'active' : 'disabled'}</Badge>
          </div>
        ))}
        {!rules?.length && <EmptyState icon={<Bell size={28} />} title="No alert rules" hint="Default rules are seeded for new organizations." />}
      </div>
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="New alert rule">
        <CreateAlertRule onSubmit={(b) => create.mutate(b)} busy={create.isPending} error={create.error instanceof Error ? create.error.message : null} />
      </Modal>
    </Panel>
  )
}

function CreateAlertRule({ onSubmit, busy, error }: { onSubmit: (body: Record<string, unknown>) => void; busy: boolean; error: string | null }) {
  const [name, setName] = useState('')
  const [metric, setMetric] = useState('fill_pct')
  const [operator, setOperator] = useState('gte')
  const [threshold, setThreshold] = useState('90')
  const [severity, setSeverity] = useState('warning')
  const [cooldown, setCooldown] = useState('60')
  return (
    <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); onSubmit({ name, metric, operator, threshold: parseFloat(threshold), severity, cooldown_minutes: parseInt(cooldown) }) }}>
      <div className="sm:col-span-2">
        <Field label="Rule name"><input className="input" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Bin nearly full" /></Field>
      </div>
      <Field label="Metric">
        <select className="input" value={metric} onChange={(e) => setMetric(e.target.value)}>
          {['fill_pct', 'temperature_c', 'battery_pct', 'offline_hours'].map((m) => <option key={m} value={m}>{humanize(m)}</option>)}
        </select>
      </Field>
      <Field label="Condition">
        <div className="flex gap-2">
          <select className="input" value={operator} onChange={(e) => setOperator(e.target.value)}>
            {['gt', 'gte', 'lt', 'lte'].map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
          <input className="input" type="number" step="0.1" required value={threshold} onChange={(e) => setThreshold(e.target.value)} />
        </div>
      </Field>
      <Field label="Severity">
        <select className="input" value={severity} onChange={(e) => setSeverity(e.target.value)}>
          {['info', 'warning', 'high', 'critical'].map((sv) => <option key={sv} value={sv}>{humanize(sv)}</option>)}
        </select>
      </Field>
      <Field label="Cooldown (minutes)"><input className="input" type="number" min="1" max="10080" value={cooldown} onChange={(e) => setCooldown(e.target.value)} /></Field>
      <div className="sm:col-span-2">
        <ErrorNote message={error} />
        <button className="btn btn-primary w-full" disabled={busy}>{busy ? <Spinner /> : null} Create rule</button>
      </div>
    </form>
  )
}

/* ------------------------------------------------------------------ audit */

interface AuditEntry {
  id: string
  action: string
  resource_type: string
  resource_id: string | null
  actor_label: string | null
  actor_user_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  request_id: string | null
  created_at: string
}

const AUDIT_PREFIXES = [
  '', 'auth', 'member', 'org', 'device', 'route', 'report', 'complaint', 'collection', 'vehicle', 'media',
]

export function AuditPage() {
  const { orgId } = useAuth()
  const [prefix, setPrefix] = useState('')
  const q = useQuery({
    queryKey: ['audit', prefix],
    queryFn: () => get<{ items: AuditEntry[]; pagination: { total: number } }>(`/admin/audit?page_size=100${prefix ? `&action_prefix=${prefix}` : ''}`),
    enabled: !!orgId,
  })

  return (
    <AdminShell title="Audit log" subtitle={`${q.data?.pagination.total ?? 0} events · immutable record of security-relevant actions`}>
      <div className="mb-4 flex flex-wrap gap-2">
        {AUDIT_PREFIXES.map((p) => (
          <button key={p} className={clsx('chip border font-mono', prefix === p ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300' : 'border-[var(--color-line)] text-[var(--color-mute)]')} onClick={() => setPrefix(p)}>
            {p || 'all'}
          </button>
        ))}
      </div>
      <Panel>
        {q.data?.items.length ? (
          <div className="divide-y divide-[var(--color-line)]">
            {q.data.items.map((a) => (
              <div key={a.id} className="table-row flex flex-wrap items-center gap-3 px-5 py-3 font-mono text-xs">
                <span className="w-36 shrink-0 text-[var(--color-faint)]">{fmtDateTime(a.created_at)}</span>
                <span className="font-semibold text-emerald-400">{a.action}</span>
                <span className="text-[var(--color-mute)]">{a.resource_type}{a.resource_id ? `/${a.resource_id.slice(0, 8)}` : ''}</span>
                <span className="ml-auto text-[var(--color-faint)]">{a.actor_label ?? 'system'}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState icon={<ScrollText size={28} />} title="No audit entries" />
        )}
      </Panel>
    </AdminShell>
  )
}

/* ------------------------------------------------------------------ shared */

function AdminShell({ title, subtitle, actions, children }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode }) {
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
