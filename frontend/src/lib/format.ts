/* Formatting helpers */

export function fmtNumber(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

export function fmtKg(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  if (Math.abs(n) >= 1000) return `${fmtNumber(n / 1000, 1)} t`
  return `${fmtNumber(n)} kg`
}

export function fmtPct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined) return '—'
  return `${(x * 100).toFixed(digits)}%`
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—'
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return fmtDate(iso)
}

export function fmtDuration(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '—'
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

export const SEVERITY_ORDER = ['urgent', 'high', 'medium', 'low'] as const

export function statusColor(status: string): string {
  switch (status) {
    case 'resolved':
    case 'completed':
    case 'active':
    case 'succeeded':
    case 'approved':
    case 'clean':
      return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25'
    case 'in_progress':
    case 'assigned':
    case 'running':
    case 'acknowledged':
      return 'text-sky-400 bg-sky-500/10 border-sky-500/25'
    case 'submitted':
    case 'queued':
    case 'registered':
    case 'draft':
    case 'pending':
    case 'scheduled':
      return 'text-slate-300 bg-slate-500/10 border-slate-500/25'
    case 'triaged':
      return 'text-violet-300 bg-violet-500/10 border-violet-500/25'
    case 'missed':
    case 'skipped':
    case 'needs_review':
    case 'maintenance':
    case 'warning':
      return 'text-amber-400 bg-amber-500/10 border-amber-500/25'
    case 'failed':
    case 'rejected':
    case 'critical':
    case 'revoked':
    case 'suspended':
      return 'text-rose-400 bg-rose-500/10 border-rose-500/25'
    default:
      return 'text-slate-300 bg-slate-500/10 border-slate-500/25'
  }
}

export function humanize(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
