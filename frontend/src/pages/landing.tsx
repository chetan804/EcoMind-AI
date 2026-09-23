/* Public marketing landing page. */

import { Link } from 'react-router-dom'
import {
  Activity, ArrowRight, BarChart3, Building2, Camera, Globe2, Leaf, MapPin, Recycle,
  ShieldCheck, Sparkles, Truck,
} from 'lucide-react'

function Nav() {
  return (
    <header className="glass sticky top-0 z-40 border-x-0 border-t-0">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-2.5">
          <img src="/favicon.svg" alt="" className="h-8 w-8" />
          <span className="text-base font-bold tracking-tight">EcoMind<span className="text-emerald-400">-AI</span></span>
        </div>
        <nav className="flex items-center gap-2">
          <Link to="/login" className="btn btn-ghost btn-sm">Sign in</Link>
          <Link to="/register" className="btn btn-primary btn-sm">Get started</Link>
        </nav>
      </div>
    </header>
  )
}

const FEATURES = [
  { icon: <Camera size={20} />, title: 'AI-assisted waste reports', text: 'Citizens photograph waste; a validated AI pipeline classifies it, flags low confidence for human review, and never fabricates results.' },
  { icon: <MapPin size={20} />, title: 'GIS command center', text: 'Live operational map with zones, bins, vehicles, complaints and routes — layered, filterable, clustered by relevance.' },
  { icon: <Truck size={20} />, title: 'Real route optimization', text: 'OR-Tools capacitated routing with priorities and time windows. Road geometry via OSRM with honest fallback labelling.' },
  { icon: <Activity size={20} />, title: 'IoT smart bins', text: 'Authenticated device ingestion, threshold alerting with cooldowns, and a clearly-labelled telemetry simulator for demos.' },
  { icon: <Leaf size={20} />, title: 'Transparent sustainability', text: 'Versioned emission factors, measured/estimated/modeled labels, methodology visible on every number.' },
  { icon: <ShieldCheck size={20} />, title: 'Multi-tenant by design', text: 'Organization isolation enforced in the data layer and proven by an automated cross-tenant test suite.' },
]

export function LandingPage() {
  return (
    <div className="min-h-screen">
      <Nav />

      {/* Hero */}
      <section className="relative mx-auto max-w-6xl px-4 pb-20 pt-16 text-center md:pt-24">
        <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-4 py-1.5 text-xs font-semibold text-emerald-300">
          <Sparkles size={13} />
          Smart waste management & environmental intelligence
        </div>
        <h1 className="mx-auto max-w-3xl text-4xl font-extrabold leading-[1.08] tracking-tight md:text-6xl">
          Waste operations, <span className="gradient-text">intelligently orchestrated</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-[var(--color-mute)] md:text-lg">
          EcoMind-AI unifies citizen reporting, collection operations, fleet routing, smart-bin
          telemetry and sustainability accounting into one configurable platform for municipalities
          and waste organizations.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link to="/login" className="btn btn-primary btn-lg">
            Explore the live demo <ArrowRight size={16} />
          </Link>
          <Link to="/register" className="btn btn-ghost btn-lg">Create your organization</Link>
        </div>
        <p className="mt-4 text-xs text-[var(--color-faint)]">
          Demo organization <span className="font-semibold text-amber-300">Aurora Municipal Corporation</span> · all demo data is clearly labelled
        </p>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-4 pb-20">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="panel panel-hover p-6 text-left">
              <div className="mb-4 inline-flex rounded-xl bg-emerald-500/10 p-2.5 text-emerald-400">{f.icon}</div>
              <h3 className="text-sm font-semibold tracking-tight">{f.title}</h3>
              <p className="mt-2 text-[13px] leading-relaxed text-[var(--color-mute)]">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Roles strip */}
      <section className="border-y border-[var(--color-line)] bg-[var(--color-base)]/60">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 py-14 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: <Camera size={16} />, role: 'Citizens', text: 'Report waste with photos, track resolution, earn sustainability points.' },
            { icon: <Truck size={16} />, role: 'Field teams', text: 'One-tap route execution with weights, skips and contamination flags.' },
            { icon: <BarChart3 size={16} />, role: 'Operations', text: 'Command center with live map, alerts, dispatch and route generation.' },
            { icon: <Building2 size={16} />, role: 'Leadership', text: 'Executive KPIs, sustainability metrics with full methodology transparency.' },
          ].map((r) => (
            <div key={r.role}>
              <div className="mb-2 flex items-center gap-2 text-emerald-400">{r.icon}<span className="text-sm font-semibold text-[var(--color-ink)]">{r.role}</span></div>
              <p className="text-[13px] leading-relaxed text-[var(--color-mute)]">{r.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Trust footer */}
      <section className="mx-auto max-w-6xl px-4 py-16 text-center">
        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-xs font-medium text-[var(--color-faint)]">
          <span className="inline-flex items-center gap-1.5"><ShieldCheck size={14} className="text-emerald-500/70" /> Permission-based RBAC</span>
          <span className="inline-flex items-center gap-1.5"><Globe2 size={14} className="text-emerald-500/70" /> Multi-tenant isolation, tested</span>
          <span className="inline-flex items-center gap-1.5"><Recycle size={14} className="text-emerald-500/70" /> Versioned emission factors</span>
          <span className="inline-flex items-center gap-1.5"><Activity size={14} className="text-emerald-500/70" /> Audited AI decisions</span>
        </div>
        <p className="mt-10 text-xs text-[var(--color-faint)]">
          © 2026 EcoMind-AI · Built as a configurable platform, ready to adapt to your organization
        </p>
      </section>
    </div>
  )
}
