/* App shell + router. Role-aware navigation. */

import { useEffect, useMemo, useState } from 'react'
import { NavLink, Route, HashRouter as Router, Routes, Navigate, useLocation, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { clsx } from 'clsx'
import {
  Activity, AlertTriangle, BarChart3, Bell, Building2, Camera, ChevronDown,
  ClipboardList, Compass, Gauge, Leaf, LogOut, Map, Menu,
  Route as RouteIcon, Settings, ShieldCheck, Sprout, Trash2, Truck, User,
  Users, X,
} from 'lucide-react'
import { AuthProvider, homeRouteFor, useAuth } from './lib/auth'
import { get } from './lib/api'
import { Badge, DemoBadge, Spinner } from './ui'

/* ------------------------------------------------------------------ shell */

function TopBar({ onMenu }: { onMenu: () => void }) {
  const { user, activeMembership, switchOrg, logout, isDemo } = useAuth()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  const { data: notifications } = useQuery({
    queryKey: ['notifications', 'badge'],
    queryFn: () => get<{ unread: number }>('/notifications?unread_only=true&page_size=1'),
    refetchInterval: 30000,
  })

  return (
    <header className="glass sticky top-0 z-40 flex h-14 items-center justify-between gap-3 border-x-0 border-t-0 px-4">
      <div className="flex items-center gap-3">
        <button className="btn btn-ghost btn-sm md:hidden" onClick={onMenu} aria-label="Open navigation">
          <Menu size={18} />
        </button>
        <div className="hidden items-center gap-2 md:flex">
          <img src="/favicon.svg" alt="" className="h-6 w-6" />
          <span className="text-sm font-bold tracking-tight">EcoMind<span className="text-emerald-400">-AI</span></span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {isDemo && <DemoBadge />}
        {user && user.memberships.length > 0 && (
          <div className="relative">
            <button className="btn btn-ghost btn-sm" onClick={() => setOpen(!open)}>
              <Building2 size={14} />
              <span className="max-w-36 truncate">{activeMembership?.organization_name ?? 'Select org'}</span>
              <ChevronDown size={13} />
            </button>
            {open && (
              <div className="panel absolute right-0 top-11 z-50 w-72 p-1.5">
                <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-faint)]">
                  Your organizations
                </p>
                {user.memberships.map((m) => (
                  <button
                    key={m.organization_id}
                    className={clsx(
                      'nav-item w-full !justify-start',
                      m.organization_id === activeMembership?.organization_id && 'active',
                    )}
                    onClick={() => {
                      switchOrg(m.organization_id)
                      setOpen(false)
                      navigate(homeRouteFor(m, user.is_platform_admin))
                    }}
                  >
                    <Building2 size={15} />
                    <span className="flex-1 truncate text-left">{m.organization_name}</span>
                    {m.is_demo && <Badge tone="warn">demo</Badge>}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        <NavLink to="/notifications" className="btn btn-ghost btn-sm relative" aria-label="Notifications">
          <Bell size={16} />
          {!!notifications?.unread && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white">
              {notifications.unread > 9 ? '9+' : notifications.unread}
            </span>
          )}
        </NavLink>
        <NavLink to="/profile" className="btn btn-ghost btn-sm" aria-label="Profile">
          <User size={16} />
        </NavLink>
        <button className="btn btn-ghost btn-sm" onClick={() => void logout()} aria-label="Log out">
          <LogOut size={16} />
        </button>
      </div>
    </header>
  )
}

interface NavSection {
  label: string
  items: { to: string; label: string; icon: React.ReactNode; perm?: string }[]
}

function navFor(role: string | undefined, hasPerm: (c: string) => boolean): NavSection[] {
  const sections: NavSection[] = []
  if (hasPerm('report:read') && role === 'citizen') {
    sections.push({
      label: 'Community',
      items: [
        { to: '/app', label: 'Dashboard', icon: <Gauge size={16} /> },
        { to: '/app/report', label: 'Report waste', icon: <Camera size={16} /> },
        { to: '/app/reports', label: 'My reports', icon: <ClipboardList size={16} /> },
        { to: '/app/impact', label: 'My impact', icon: <Sprout size={16} /> },
        { to: '/app/schedule', label: 'Collection days', icon: <CalendarDays size={16} /> },
      ],
    })
  }
  if (hasPerm('analytics:read') || role === 'ops_manager' || role === 'org_admin' || role === 'field_supervisor') {
    sections.push({
      label: 'Operations',
      items: [
        { to: '/ops', label: 'Command center', icon: <Compass size={16} /> },
        { to: '/ops/routes', label: 'Routes', icon: <RouteIcon size={16} /> },
        { to: '/ops/reports', label: 'Waste reports', icon: <ClipboardList size={16} /> },
        { to: '/ops/complaints', label: 'Complaints', icon: <AlertTriangle size={16} /> },
        { to: '/ops/collection', label: 'Collection', icon: <Trash2 size={16} /> },
        { to: '/ops/fleet', label: 'Fleet', icon: <Truck size={16} /> },
        { to: '/ops/devices', label: 'Smart bins', icon: <Activity size={16} /> },
      ],
    })
  }
  if (hasPerm('route:execute') && role === 'collector') {
    sections.push({
      label: 'Field',
      items: [{ to: '/field', label: 'My route today', icon: <Map size={16} /> }],
    })
  }
  if (hasPerm('sustainability:read') && role !== 'citizen') {
    sections.push({
      label: 'Intelligence',
      items: [
        { to: '/sustainability', label: 'Sustainability', icon: <Leaf size={16} /> },
        { to: '/exec', label: 'Executive view', icon: <BarChart3 size={16} /> },
      ],
    })
  }
  if (hasPerm('org:update') || hasPerm('user:read') || hasPerm('audit:read')) {
    sections.push({
      label: 'Administration',
      items: [
        { to: '/admin/users', label: 'Members', icon: <Users size={16} />, perm: 'user:read' },
        { to: '/admin/settings', label: 'Organization', icon: <Settings size={16} />, perm: 'org:update' },
        { to: '/admin/audit', label: 'Audit log', icon: <ShieldCheck size={16} />, perm: 'audit:read' },
      ],
    })
  }
  return sections
}

function CalendarDays({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2v4M16 2v4" /><rect width="18" height="18" x="3" y="4" rx="2" /><path d="M3 10h18" />
    </svg>
  )
}

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { activeMembership, hasPerm } = useAuth()
  const sections = useMemo(
    () => navFor(activeMembership?.role_code, hasPerm),
    [activeMembership?.role_code, hasPerm],
  )
  return (
    <>
      {open && <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={onClose} />}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-64 shrink-0 overflow-y-auto border-r border-[var(--color-line)] bg-[var(--color-base)] px-4 py-5 transition-transform md:sticky md:top-0 md:h-screen md:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="mb-6 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <img src="/favicon.svg" alt="EcoMind-AI logo" className="h-8 w-8" />
            <div>
              <div className="text-sm font-bold leading-none tracking-tight">EcoMind<span className="text-emerald-400">-AI</span></div>
              <div className="mt-1 text-[10px] uppercase tracking-widest text-[var(--color-faint)]">
                {activeMembership ? activeMembership.role_name : 'Platform'}
              </div>
            </div>
          </Link>
          <button className="btn btn-ghost btn-sm md:hidden" onClick={onClose} aria-label="Close navigation">
            <X size={16} />
          </button>
        </div>

        <nav className="flex flex-col gap-5" aria-label="Main navigation">
          {sections.map((s) => (
            <div key={s.label}>
              <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-widest text-[var(--color-faint)]">
                {s.label}
              </p>
              <div className="flex flex-col gap-0.5">
                {s.items
                  .filter((i) => !i.perm || hasPerm(i.perm))
                  .map((i) => (
                    <NavLink key={i.to} to={i.to} onClick={onClose} className={({ isActive }) => clsx('nav-item', isActive && 'active')}>
                      {i.icon}
                      {i.label}
                    </NavLink>
                  ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="mt-8 rounded-xl border border-[var(--color-line)] bg-[var(--color-panel)] p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-[var(--color-mute)]">
            <ShieldCheck size={13} className="text-emerald-400" />
            Permission-based access
          </div>
          <p className="mt-1 text-[10px] leading-relaxed text-[var(--color-faint)]">
            Your navigation reflects the permissions granted to your role in this organization.
          </p>
        </div>
      </aside>
    </>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false)
  return (
    <div className="flex min-h-screen">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenu={() => setMenuOpen(true)} />
        <main className="flex-1 px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  )
}

function Page({ title, subtitle, actions, children }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight md:text-2xl">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-[var(--color-mute)]">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  )
}

/* ------------------------------------------------------------------ guards */

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="text-emerald-400" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <>{children}</>
}

function RequirePerm({ perm, children }: { perm: string; children: React.ReactNode }) {
  const { hasPerm } = useAuth()
  if (!hasPerm(perm)) {
    return (
      <Shell>
        <Page title="Access restricted">
          <div className="panel p-8 text-center text-sm text-[var(--color-mute)]">
            Your role does not include the <code className="rounded bg-[var(--color-line)] px-1.5 py-0.5 text-xs">{perm}</code> permission.
          </div>
        </Page>
      </Shell>
    )
  }
  return <>{children}</>
}

/* ------------------------------------------------------------------ pages (imported) */

import { LandingPage } from './pages/landing'
import { LoginPage, RegisterPage } from './pages/auth'
import { OnboardingPage } from './pages/onboarding'
import {
  CitizenDashboard, ReportWizardPage, MyReportsPage, ImpactPage, SchedulePage,
} from './pages/citizen'
import { FieldPage } from './pages/field'
import { CommandCenterPage } from './pages/command-center'
import { RoutesPage, RouteDetailPage } from './pages/routes'
import { OpsReportsPage, ComplaintsPage, FleetPage, DevicesPage, CollectionPage } from './pages/ops-manage'
import { SustainabilityPage } from './pages/sustainability'
import { ExecutivePage } from './pages/executive'
import { AdminUsersPage, AdminSettingsPage, AuditPage } from './pages/admin'
import { NotificationsPage, ProfilePage } from './pages/misc'

function AppRoutes() {
  const { user, activeMembership } = useAuth()
  const home = homeRouteFor(activeMembership, user?.is_platform_admin)
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route path="/onboarding" element={<RequireAuth><OnboardingPage /></RequireAuth>} />

      {/* Citizen */}
      <Route path="/app" element={<RequireAuth><CitizenDashboard /></RequireAuth>} />
      <Route path="/app/report" element={<RequireAuth><ReportWizardPage /></RequireAuth>} />
      <Route path="/app/reports" element={<RequireAuth><MyReportsPage /></RequireAuth>} />
      <Route path="/app/impact" element={<RequireAuth><ImpactPage /></RequireAuth>} />
      <Route path="/app/schedule" element={<RequireAuth><SchedulePage /></RequireAuth>} />

      {/* Field */}
      <Route path="/field" element={<RequireAuth><RequirePerm perm="route:read"><FieldPage /></RequirePerm></RequireAuth>} />

      {/* Operations */}
      <Route path="/ops" element={<RequireAuth><CommandCenterPage /></RequireAuth>} />
      <Route path="/ops/routes" element={<RequireAuth><RoutesPage /></RequireAuth>} />
      <Route path="/ops/routes/:id" element={<RequireAuth><RouteDetailPage /></RequireAuth>} />
      <Route path="/ops/reports" element={<RequireAuth><OpsReportsPage /></RequireAuth>} />
      <Route path="/ops/complaints" element={<RequireAuth><ComplaintsPage /></RequireAuth>} />
      <Route path="/ops/collection" element={<RequireAuth><CollectionPage /></RequireAuth>} />
      <Route path="/ops/fleet" element={<RequireAuth><FleetPage /></RequireAuth>} />
      <Route path="/ops/devices" element={<RequireAuth><DevicesPage /></RequireAuth>} />

      {/* Intelligence */}
      <Route path="/sustainability" element={<RequireAuth><SustainabilityPage /></RequireAuth>} />
      <Route path="/exec" element={<RequireAuth><ExecutivePage /></RequireAuth>} />

      {/* Admin */}
      <Route path="/admin/users" element={<RequireAuth><AdminUsersPage /></RequireAuth>} />
      <Route path="/admin/settings" element={<RequireAuth><AdminSettingsPage /></RequireAuth>} />
      <Route path="/admin/audit" element={<RequireAuth><AuditPage /></RequireAuth>} />

      <Route path="/notifications" element={<RequireAuth><NotificationsPage /></RequireAuth>} />
      <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />

      <Route path="*" element={<Navigate to={home} replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </Router>
  )
}
