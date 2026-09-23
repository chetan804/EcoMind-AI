/* Notifications and profile. */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck, ShieldCheck } from 'lucide-react'
import { get, post } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Badge, EmptyState, Panel, Spinner, Toast } from '../ui'
import { fmtDateTime, humanize } from '../lib/format'

interface NotificationItem {
  id: string
  category: string
  title: string
  body: string | null
  data: Record<string, unknown>
  read_at: string | null
  created_at: string
}

export function NotificationsPage() {
  const { orgId } = useAuth()
  const queryClient = useQueryClient()
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['notifications', unreadOnly],
    queryFn: () => get<{ items: NotificationItem[]; unread: number }>(`/notifications?${unreadOnly ? 'unread_only=true&' : ''}page_size=100`),
    enabled: !!orgId,
    refetchInterval: 20000,
  })

  const markAll = useMutation({
    mutationFn: () => post('/notifications/read-all', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      setToast('All notifications marked read')
      setTimeout(() => setToast(null), 2000)
    },
  })

  const markOne = useMutation({
    mutationFn: (id: string) => post(`/notifications/${id}/read`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight md:text-2xl">Notifications</h1>
          <p className="mt-1 text-sm text-[var(--color-mute)]">{q.data?.unread ?? 0} unread</p>
        </div>
        <div className="flex gap-2">
          <button
            className={`chip border ${unreadOnly ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300' : 'border-[var(--color-line)] text-[var(--color-mute)]'}`}
            onClick={() => setUnreadOnly(!unreadOnly)}
          >
            Unread only
          </button>
          <button className="btn btn-ghost btn-sm" disabled={markAll.isPending || !q.data?.unread} onClick={() => markAll.mutate()}>
            {markAll.isPending ? <Spinner /> : <CheckCheck size={14} />} Mark all read
          </button>
        </div>
      </div>

      <Panel>
        {q.data?.items.length ? (
          <div className="divide-y divide-[var(--color-line)]">
            {q.data.items.map((n) => (
              <div
                key={n.id}
                className={`table-row flex items-start gap-3 px-5 py-4 ${n.read_at ? '' : 'bg-emerald-500/[0.04]'}`}
              >
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read_at ? 'bg-[var(--color-line)]' : 'bg-emerald-400'}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{n.title}</p>
                  {n.body && <p className="mt-0.5 text-xs text-[var(--color-mute)]">{n.body}</p>}
                  <p className="mt-1 text-[11px] text-[var(--color-faint)]">
                    <Badge tone="info">{humanize(n.category)}</Badge> <span className="ml-1">{fmtDateTime(n.created_at)}</span>
                  </p>
                </div>
                {!n.read_at && (
                  <button className="text-[11px] text-emerald-400 hover:underline" onClick={() => markOne.mutate(n.id)}>mark read</button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState icon={<Bell size={28} />} title={unreadOnly ? 'No unread notifications' : 'No notifications yet'} hint="Alerts, complaints, route events and rewards appear here." />
        )}
      </Panel>
      {toast && <Toast message={toast} />}
    </div>
  )
}

/* ------------------------------------------------------------------ profile */

interface ProfileData {
  id: string
  full_name: string
  email: string
  phone: string | null
  locale: string
  created_at: string
  is_platform_admin: boolean
  memberships: {
    organization_id: string
    organization_name: string
    organization_slug: string
    role_code: string
    role_name: string
    is_default: boolean
    is_demo: boolean
  }[]
}

export function ProfilePage() {
  const q = useQuery({
    queryKey: ['me-profile'],
    queryFn: () => get<ProfileData>('/auth/me'),
  })

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-xl font-bold tracking-tight md:text-2xl">Profile</h1>
      <div className="grid gap-4">
        <Panel className="p-6">
          <div className="mb-5 flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10 text-xl font-bold text-emerald-400">
              {(q.data?.full_name ?? q.data?.email ?? '?').slice(0, 1).toUpperCase()}
            </div>
            <div>
              <p className="font-bold">{q.data?.full_name ?? '—'}</p>
              <p className="text-sm text-[var(--color-mute)]">{q.data?.email}</p>
              {q.data?.is_platform_admin && <Badge tone="purple">platform admin</Badge>}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><p className="label">Phone</p><p>{q.data?.phone ?? '—'}</p></div>
            <div><p className="label">Locale</p><p>{q.data?.locale}</p></div>
            <div className="col-span-2"><p className="label">Member since</p><p>{fmtDateTime(q.data?.created_at)}</p></div>
          </div>
          <p className="mt-4 text-[11px] leading-relaxed text-[var(--color-faint)]">
            Profile fields are managed by your account settings; contact your organization admin for changes.
          </p>
        </Panel>

        <Panel className="p-6">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold"><ShieldCheck size={15} className="text-emerald-400" /> Organization memberships</h3>
          <div className="flex flex-col gap-2">
            {(q.data?.memberships ?? []).map((m) => (
              <div key={m.organization_id} className="flex items-center justify-between rounded-lg border border-[var(--color-line)] px-4 py-3">
                <div>
                  <p className="flex items-center gap-2 text-sm font-medium">
                    {m.organization_name}
                    {m.is_demo && <Badge tone="warn">demo</Badge>}
                    {m.is_default && <Badge tone="brand">default</Badge>}
                  </p>
                  <p className="font-mono text-[11px] text-[var(--color-faint)]">{m.organization_slug}</p>
                </div>
                <Badge tone={m.role_code === 'org_admin' ? 'danger' : 'info'}>{m.role_name}</Badge>
              </div>
            ))}
          </div>
          <p className="mt-4 text-[11px] leading-relaxed text-[var(--color-faint)]">
            Switch organizations from the top bar. Data is strictly isolated per organization — users, reports,
            devices and analytics never cross tenant boundaries.
          </p>
        </Panel>
      </div>
    </div>
  )
}
