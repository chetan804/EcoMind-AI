/* Organization self-service onboarding. */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Building2, Check, MapPin, Sparkles, Trash2, Truck, Users } from 'lucide-react'
import { post } from '../lib/api'
import { useAuth } from '../lib/auth'
import { ErrorNote, Field, Panel, Spinner } from '../ui'
import type { Org } from '../lib/api'

const STEPS = [
  { icon: <Building2 size={16} />, title: 'Create organization', text: 'Legal name, type and locale. You become the organization administrator.' },
  { icon: <MapPin size={16} />, title: 'Configure service area', text: 'Define zones with GeoJSON polygons — used for report routing and analytics.' },
  { icon: <Users size={16} />, title: 'Invite your team', text: 'Assign roles: operations managers, field supervisors, collectors, analysts.' },
  { icon: <Trash2 size={16} />, title: 'Set up operations', text: 'Waste categories and alert rules are pre-configured; add collection points, vehicles and bins.' },
  { icon: <Truck size={16} />, title: 'Start operating', text: 'Generate your first optimized route and begin recording collections.' },
]

export function OnboardingPage() {
  const { refreshMe, user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [orgType, setOrgType] = useState('municipality')
  const [city, setCity] = useState('')
  const [country, setCountry] = useState('')
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () =>
      post<Org>('/organizations', {
        name,
        slug: slug || name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, ''),
        org_type: orgType,
        city: city || null,
        country: country || null,
      }),
    onSuccess: async () => {
      await refreshMe()
      queryClient.clear()
      navigate('/admin/settings')
    },
    onError: (e: Error) => setError(e.message),
  })

  if (user && user.memberships.length > 0) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <Panel className="p-10">
          <Check className="mx-auto mb-4 text-emerald-400" size={32} />
          <h1 className="text-lg font-bold">You already belong to an organization</h1>
          <p className="mt-2 text-sm text-[var(--color-mute)]">
            Use the organization switcher in the top bar, or create another organization below.
          </p>
          <div className="mt-6">
            <CreateForm />
          </div>
        </Panel>
      </div>
    )
  }

  function CreateForm() {
    return (
      <form
        className="grid gap-4 text-left sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault()
          setError(null)
          create.mutate()
        }}
      >
        <div className="sm:col-span-2">
          <Field label="Organization name">
            <input className="input" required minLength={2} value={name} onChange={(e) => setName(e.target.value)} placeholder="Greenfield Municipal Corporation" />
          </Field>
        </div>
        <Field label="Slug (optional)" hint="Lowercase letters, numbers, dashes">
          <input className="input" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="greenfield" />
        </Field>
        <Field label="Type">
          <select className="input" value={orgType} onChange={(e) => setOrgType(e.target.value)}>
            <option value="municipality">Municipality</option>
            <option value="municipal_corporation">Municipal corporation</option>
            <option value="private_operator">Private operator</option>
            <option value="residential_community">Residential community</option>
            <option value="campus">Campus</option>
            <option value="industrial_facility">Industrial facility</option>
            <option value="commercial_facility">Commercial facility</option>
            <option value="nonprofit">Nonprofit</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="City">
          <input className="input" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Greenfield" />
        </Field>
        <Field label="Country">
          <input className="input" value={country} onChange={(e) => setCountry(e.target.value)} placeholder="Country" />
        </Field>
        <div className="sm:col-span-2">
          <ErrorNote message={error} />
        </div>
        <div className="sm:col-span-2">
          <button className="btn btn-primary w-full" disabled={create.isPending || !name}>
            {create.isPending ? <Spinner /> : <Sparkles size={15} />} Create organization
          </button>
          <p className="mt-2 text-center text-[11px] text-[var(--color-faint)]">
            Waste categories and default alert rules are configured automatically.
          </p>
        </div>
      </form>
    )
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold tracking-tight">Set up your organization</h1>
        <p className="mt-2 text-sm text-[var(--color-mute)]">
          Five steps from signup to operating. Everything here is also available later in Administration.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          {STEPS.map((s, i) => (
            <Panel key={s.title} className="flex items-start gap-4 p-4">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                {s.icon}
              </div>
              <div>
                <p className="text-sm font-semibold">
                  <span className="mr-2 text-[var(--color-faint)]">{String(i + 1).padStart(2, '0')}</span>
                  {s.title}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-[var(--color-mute)]">{s.text}</p>
              </div>
            </Panel>
          ))}
        </div>
        <Panel className="h-fit p-6">
          <h2 className="mb-4 text-sm font-semibold">Create organization</h2>
          <CreateForm />
        </Panel>
      </div>
    </div>
  )
}
