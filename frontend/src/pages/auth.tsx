/* Authentication pages. */

import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Building2, Lock, Mail, User } from 'lucide-react'
import { get } from '../lib/api'
import { useAuth } from '../lib/auth'
import { ErrorNote, Field, Spinner } from '../ui'

function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <Link to="/" className="mb-8 flex items-center justify-center gap-2.5">
          <img src="/favicon.svg" alt="" className="h-10 w-10" />
          <span className="text-lg font-bold tracking-tight">EcoMind<span className="text-emerald-400">-AI</span></span>
        </Link>
        <div className="panel p-8">
          <h1 className="text-xl font-bold tracking-tight">{title}</h1>
          <p className="mt-1 mb-6 text-sm text-[var(--color-mute)]">{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  )
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation() as { state?: { from?: string } }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      navigate(location.state?.from ?? '/app', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your EcoMind-AI account">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Email">
          <div className="relative">
            <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-faint)]" />
            <input className="input pl-9" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@organization.org" autoComplete="email" />
          </div>
        </Field>
        <Field label="Password">
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-faint)]" />
            <input className="input pl-9" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••••" autoComplete="current-password" />
          </div>
        </Field>
        <ErrorNote message={error} />
        <button className="btn btn-primary w-full" disabled={busy}>
          {busy ? <Spinner /> : <ArrowRight size={15} />} Sign in
        </button>
      </form>

      <div className="mt-6 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3.5">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-amber-400">Demo accounts</p>
        <div className="mt-2 grid grid-cols-1 gap-1 text-xs text-[var(--color-mute)]">
          {[
            ['admin@aurora.demo', 'Organization admin'],
            ['ops@aurora.demo', 'Operations manager'],
            ['driver1@aurora.demo', 'Collector / driver'],
            ['citizen1@aurora.demo', 'Citizen'],
            ['analyst@aurora.demo', 'Sustainability analyst'],
          ].map(([demoEmail, role]) => (
            <button
              key={demoEmail}
              type="button"
              className="flex items-center justify-between rounded-md px-2 py-1 text-left hover:bg-white/5"
              onClick={() => { setEmail(demoEmail); setPassword('EcoDemo2026!') }}
            >
              <span className="font-mono text-[11px]">{demoEmail}</span>
              <span className="text-[10px] text-[var(--color-faint)]">{role}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-[10px] text-[var(--color-faint)]">Password: EcoDemo2026! · click to fill</p>
      </div>

      <p className="mt-6 text-center text-xs text-[var(--color-mute)]">
        No account? <Link to="/register" className="font-semibold text-emerald-400 hover:underline">Create one</Link>
      </p>
    </AuthShell>
  )
}

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [joinSlug, setJoinSlug] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const { data: orgs } = useQuery({
    queryKey: ['public-orgs'],
    queryFn: () => get<{ items: { slug: string; name: string; is_demo: boolean }[] }>('/auth/public/organizations'),
  })

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register(email, password, fullName, joinSlug || undefined)
      navigate('/app', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Create your account" subtitle="Join an open organization or create your own afterwards">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Full name">
          <div className="relative">
            <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-faint)]" />
            <input className="input pl-9" required value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Asha Verma" autoComplete="name" />
          </div>
        </Field>
        <Field label="Email">
          <div className="relative">
            <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-faint)]" />
            <input className="input pl-9" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.org" autoComplete="email" />
          </div>
        </Field>
        <Field label="Password" hint="At least 10 characters">
          <div className="relative">
            <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-faint)]" />
            <input className="input pl-9" type="password" required minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••••" autoComplete="new-password" />
          </div>
        </Field>
        <Field label="Join an open organization (optional)">
          <div className="relative">
            <Building2 size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-faint)]" />
            <select className="input pl-9" value={joinSlug} onChange={(e) => setJoinSlug(e.target.value)}>
              <option value="">— none, I'll create or get invited —</option>
              {orgs?.items.map((o) => (
                <option key={o.slug} value={o.slug}>{o.name}{o.is_demo ? ' (demo)' : ''}</option>
              ))}
            </select>
          </div>
        </Field>
        <ErrorNote message={error} />
        <button className="btn btn-primary w-full" disabled={busy}>
          {busy ? <Spinner /> : <ArrowRight size={15} />} Create account
        </button>
      </form>
      <p className="mt-6 text-center text-xs text-[var(--color-mute)]">
        Already registered? <Link to="/login" className="font-semibold text-emerald-400 hover:underline">Sign in</Link>
      </p>
    </AuthShell>
  )
}
