import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import './App.css'

type Role = 'Admin' | 'Citizen' | 'Collector'
type View = 'overview' | 'reports' | 'collections' | 'routes' | 'notifications'

type Profile = { id: number; name: string; email: string; role_id: number }
type Report = {
  id: number
  waste_type: string
  description: string
  location: string
  status: string
  ai_waste_type?: string
  ai_confidence?: number
}
type Collection = { id: number; report_id: number; status: string; scheduled_at?: string }
type Route = { id: number; status: string; estimated_distance_km: number; stops: { id: number }[] }
type Notification = { id: number; title: string; message: string; read_at?: string }

type DashboardStats = {
  total_users: number
  citizens: number
  collectors: number
  total_reports: number
  pending_reports: number
  completed_collections: number
  pending_collections: number
  total_complaints: number
  unresolved_complaints: number
}

type DashboardData = {
  stats?: DashboardStats
  reports?: Report[]
  collections?: Collection[]
  routes?: Route[]
  notifications?: Notification[]
  points?: number
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const roleNames: Record<number, Role> = { 4: 'Admin', 5: 'Citizen', 6: 'Collector' }

async function api<T>(path: string, token: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Request failed (${response.status})`)
  }
  return response.json()
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('ecomind_token'))
  const [profile, setProfile] = useState<Profile | null>(null)
  const [view, setView] = useState<View>('overview')
  const [loading, setLoading] = useState(Boolean(token))
  const [error, setError] = useState('')
  const [data, setData] = useState<DashboardData>({})

  useEffect(() => {
    if (!token) return
    setLoading(true)
    api<Profile>('/users/me', token)
      .then(setProfile)
      .catch(() => {
        localStorage.removeItem('ecomind_token')
        setToken(null)
      })
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => {
    if (!token || !profile) return
    setError('')
    const requests: Promise<void>[] = []
    if (profile.role_id === 4) {
      requests.push(api<DashboardStats>('/analytics/dashboard', token).then((stats) => setData((current) => ({ ...current, stats }))))
    }
    if (profile.role_id === 5) {
      requests.push(api<Report[]>('/waste-reports/my-reports', token).then((reports) => setData((current) => ({ ...current, reports }))))
      requests.push(api<{ points: number }>('/rewards/me', token).then(({ points }) => setData((current) => ({ ...current, points }))))
    }
    if (profile.role_id === 6) {
      requests.push(api<Collection[]>('/collections/my-collections', token).then((collections) => setData((current) => ({ ...current, collections }))))
      requests.push(api<Route[]>('/routes/my-routes', token).then((routes) => setData((current) => ({ ...current, routes }))))
    }
    requests.push(api<Notification[]>('/notifications/', token).then((notifications) => setData((current) => ({ ...current, notifications }))))
    Promise.all(requests).catch((requestError: Error) => setError(requestError.message))
  }, [profile, token])

  if (!token || !profile) {
    return <Login onLogin={(nextToken) => { localStorage.setItem('ecomind_token', nextToken); setToken(nextToken) }} loading={loading} error={error} />
  }

  const role = roleNames[profile.role_id] ?? 'Citizen'
  const signOut = () => { localStorage.removeItem('ecomind_token'); setToken(null); setProfile(null); setData({}) }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark"><span>EM</span><div><strong>EcoMind</strong><small>operations console</small></div></div>
        <div className="side-label">Workspace</div>
        <nav aria-label="Primary navigation">
          <NavButton active={view === 'overview'} onClick={() => setView('overview')}>Overview</NavButton>
          {role === 'Citizen' && <NavButton active={view === 'reports'} onClick={() => setView('reports')}>My reports</NavButton>}
          {role === 'Collector' && <><NavButton active={view === 'collections'} onClick={() => setView('collections')}>Collections</NavButton><NavButton active={view === 'routes'} onClick={() => setView('routes')}>Routes</NavButton></>}
          <NavButton active={view === 'notifications'} onClick={() => setView('notifications')}>Notifications <span className="nav-count">{data.notifications?.filter((item) => !item.read_at).length ?? 0}</span></NavButton>
        </nav>
        <div className="sidebar-footer"><span className="status-dot" /> API connected<div className="version">EcoMind AI / v0.1</div></div>
      </aside>
      <section className="workspace">
        <header className="topbar"><div><p className="eyebrow">{role} workspace</p><h1>{view === 'overview' ? 'Good work starts with visibility.' : viewTitle(view)}</h1></div><div className="user-menu"><div className="avatar">{profile.name.slice(0, 1).toUpperCase()}</div><div><strong>{profile.name}</strong><small>{profile.email}</small></div><button className="text-button" onClick={signOut}>Sign out</button></div></header>
        {error && <div className="alert" role="alert">{error}</div>}
        {view === 'overview' && <Overview role={role} profile={profile} data={data} />}
        {view === 'reports' && <ReportList reports={data.reports ?? []} points={data.points ?? 0} />}
        {view === 'collections' && <CollectionList collections={data.collections ?? []} />}
        {view === 'routes' && <RouteList routes={data.routes ?? []} />}
        {view === 'notifications' && <NotificationList notifications={data.notifications ?? []} />}
      </section>
    </main>
  )
}

function Login({ onLogin, loading, error }: { onLogin: (token: string) => void; loading: boolean; error: string }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState(error)
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSubmitting(true); setMessage('')
    try {
      const body = new URLSearchParams({ username: email, password })
      const response = await fetch(`${API_URL}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail ?? 'Unable to sign in')
      onLogin(result.access_token)
    } catch (loginError) { setMessage((loginError as Error).message) } finally { setSubmitting(false) }
  }
  return <main className="login-screen"><div className="login-panel"><div className="brand-mark large"><span>EM</span><div><strong>EcoMind</strong><small>smart waste operations</small></div></div><div className="login-copy"><p className="eyebrow">Environmental intelligence</p><h1>Make every collection count.</h1><p>One operational view for reports, routes, collections, and community impact.</p></div><form onSubmit={submit}><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>{message && <div className="form-error">{message}</div>}<button className="primary-button" disabled={submitting || loading}>{submitting ? 'Signing in...' : 'Sign in to workspace'}</button></form><small className="login-note">Use an account registered in the EcoMind backend.</small></div><div className="login-aside"><div className="signal-line" /><p>Waste is not the end of a system. It is a signal.</p><span>Track it. Act on it. Learn from it.</span></div></main>
}

function Overview({ role, profile, data }: { role: Role; profile: Profile; data: DashboardData }) {
  if (role === 'Admin' && data.stats) { const stats = data.stats; return <><section className="welcome"><div><p className="eyebrow">Live operations</p><h2>Platform overview</h2><p>Monitor the system from intake through resolution.</p></div><div className="date-chip">{new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</div></section><div className="metric-grid"><Metric label="Total users" value={stats.total_users} detail={`${stats.citizens} citizens`} accent="mint" /><Metric label="Open reports" value={stats.pending_reports} detail={`${stats.total_reports} total reports`} accent="amber" /><Metric label="Collections pending" value={stats.pending_collections} detail={`${stats.completed_collections} completed`} accent="coral" /><Metric label="Unresolved complaints" value={stats.unresolved_complaints} detail={`${stats.total_complaints} total complaints`} accent="blue" /></div><section className="content-grid"><div className="panel feature-panel"><div className="panel-heading"><div><p className="eyebrow">System health</p><h3>Operational pulse</h3></div><span className="live-badge"><span className="status-dot" /> Live</span></div><div className="pulse-graphic"><div className="pulse-bar one" /><div className="pulse-bar two" /><div className="pulse-bar three" /><div className="pulse-bar four" /><div className="pulse-bar five" /><div className="pulse-bar six" /><div className="pulse-bar seven" /></div><p className="muted">Metrics are calculated by the backend from current database records.</p></div><div className="panel"><div className="panel-heading"><div><p className="eyebrow">Next move</p><h3>Keep the loop closed</h3></div></div><p className="panel-copy">Assign pending collections, review unresolved complaints, and keep field teams moving.</p><button className="secondary-button">Open operations queue <span>↗</span></button></div></section></> }
  return <><section className="welcome"><div><p className="eyebrow">{role} workspace</p><h2>Welcome back, {profile.name.split(' ')[0]}.</h2><p>Your sustainability activity stays in one clear place.</p></div><div className="impact-number"><strong>{role === 'Citizen' ? data.points ?? 0 : data.collections?.filter((item) => item.status === 'collected').length ?? 0}</strong><span>{role === 'Citizen' ? 'points earned' : 'collections completed'}</span></div></section><div className="metric-grid"><Metric label={role === 'Citizen' ? 'Reward points' : 'Assigned work'} value={role === 'Citizen' ? data.points ?? 0 : data.collections?.length ?? 0} detail={role === 'Citizen' ? 'Server-verified activity' : 'Current assignments'} accent="mint" /><Metric label="Notifications" value={data.notifications?.filter((item) => !item.read_at).length ?? 0} detail="Unread updates" accent="amber" /><Metric label={role === 'Citizen' ? 'My reports' : 'Optimized routes'} value={role === 'Citizen' ? data.reports?.length ?? 0 : data.routes?.length ?? 0} detail="From the backend" accent="blue" /></div></>
}

function Metric({ label, value, detail, accent }: { label: string; value: number; detail: string; accent: string }) { return <article className={`metric-card ${accent}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article> }
function NavButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) { return <button className={`nav-button ${active ? 'active' : ''}`} onClick={onClick}>{children}</button> }
function ReportList({ reports, points }: { reports: Report[]; points: number }) { return <section className="panel-list"><div className="section-intro"><div><p className="eyebrow">Citizen activity</p><h2>Waste reports</h2></div><span className="count-pill">{points} points</span></div>{reports.length === 0 ? <EmptyState text="No reports submitted yet." /> : reports.map((report) => <div className="list-row" key={report.id}><div className="row-icon">{report.waste_type.slice(0, 1).toUpperCase()}</div><div className="row-main"><strong>{report.description}</strong><span>{report.location} · {report.ai_waste_type ?? report.waste_type}</span></div><Status value={report.status} /></div>)}</section> }
function CollectionList({ collections }: { collections: Collection[] }) { return <section className="panel-list"><div className="section-intro"><div><p className="eyebrow">Field operations</p><h2>Assigned collections</h2></div><span className="count-pill">{collections.length} tasks</span></div>{collections.length === 0 ? <EmptyState text="No collections assigned." /> : collections.map((item) => <div className="list-row" key={item.id}><div className="row-icon">C</div><div className="row-main"><strong>Collection #{item.id}</strong><span>Report #{item.report_id}{item.scheduled_at ? ` · ${new Date(item.scheduled_at).toLocaleString()}` : ''}</span></div><Status value={item.status} /></div>)}</section> }
function RouteList({ routes }: { routes: Route[] }) { return <section className="panel-list"><div className="section-intro"><div><p className="eyebrow">Route planning</p><h2>Optimized routes</h2></div><span className="count-pill">{routes.length} routes</span></div>{routes.length === 0 ? <EmptyState text="No optimized routes yet." /> : routes.map((route) => <div className="list-row" key={route.id}><div className="row-icon">R</div><div className="row-main"><strong>Route #{route.id}</strong><span>{route.stops.length} stops · {route.estimated_distance_km.toFixed(2)} km</span></div><Status value={route.status} /></div>)}</section> }
function NotificationList({ notifications }: { notifications: Notification[] }) { return <section className="panel-list"><div className="section-intro"><div><p className="eyebrow">Updates</p><h2>Notifications</h2></div></div>{notifications.length === 0 ? <EmptyState text="You're all caught up." /> : notifications.map((item) => <div className={`list-row ${item.read_at ? 'read' : ''}`} key={item.id}><div className="row-icon">N</div><div className="row-main"><strong>{item.title}</strong><span>{item.message}</span></div><small>{item.read_at ? 'Read' : 'New'}</small></div>)}</section> }
function Status({ value }: { value: string }) { return <span className={`status status-${value.replace('_', '-')}`}>{value.replace('_', ' ')}</span> }
function EmptyState({ text }: { text: string }) { return <div className="empty-state">{text}</div> }
function viewTitle(view: View) { return { overview: 'Overview', reports: 'My reports', collections: 'Collections', routes: 'Routes', notifications: 'Notifications' }[view] }

export default App
