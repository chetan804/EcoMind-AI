import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { BrowserRouter, Link, NavLink, Outlet, Route, Routes, useNavigate } from 'react-router-dom'
import './App.css'
import { trackEvent } from './analytics'
import { api, API_URL } from './services/api'

type Role = 'Admin' | 'Citizen' | 'Collector'
type View = 'overview' | 'reports' | 'create-report' | 'collections' | 'routes' | 'complaints' | 'create-complaint' | 'notifications'

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
type Complaint = { id: number; title?: string; description: string; location: string; status: string; ai_priority?: string }

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
  complaints?: Complaint[]
  points?: number
}

const roleNames: Record<number, Role> = { 4: 'Admin', 5: 'Citizen', 6: 'Collector' }

function usePageMeta(title: string, description: string) {
  useEffect(() => {
    document.title = title
    const metaDescription = document.querySelector('meta[name="description"]')
    if (metaDescription) {
      metaDescription.setAttribute('content', description)
    }
    const metaOgTitle = document.querySelector('meta[property="og:title"]')
    if (metaOgTitle) {
      metaOgTitle.setAttribute('content', title)
    }
    const metaOgDescription = document.querySelector('meta[property="og:description"]')
    if (metaOgDescription) {
      metaOgDescription.setAttribute('content', description)
    }
  }, [title, description])
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('ecomind_token'))
  const [cookieNoticeAccepted, setCookieNoticeAccepted] = useState(
    () => localStorage.getItem('ecomind_cookie_notice_seen') === 'true',
  )

  const handleLogin = (nextToken: string) => {
    localStorage.setItem('ecomind_token', nextToken)
    setToken(nextToken)
  }

  const dismissCookieNotice = () => {
    localStorage.setItem('ecomind_cookie_notice_seen', 'true')
    setCookieNoticeAccepted(true)
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PublicLayout cookieNoticeAccepted={cookieNoticeAccepted} onDismissCookieNotice={dismissCookieNotice} />}>
          <Route index element={<HomePage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="features" element={<FeaturesPage />} />
          <Route path="how-it-works" element={<HowItWorksPage />} />
          <Route path="technology" element={<TechnologyPage />} />
          <Route path="sustainability" element={<SustainabilityPage />} />
          <Route path="contact" element={<ContactPage />} />
          <Route path="privacy" element={<PrivacyPage />} />
          <Route path="terms" element={<TermsPage />} />
        </Route>
        <Route path="/app" element={token ? <AuthenticatedApp token={token} onSignOut={() => { localStorage.removeItem('ecomind_token'); setToken(null) }} /> : <Login onLogin={handleLogin} loading={false} error="" />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}

function PublicLayout({
  cookieNoticeAccepted,
  onDismissCookieNotice,
}: {
  cookieNoticeAccepted: boolean
  onDismissCookieNotice: () => void
}) {
  const navItems = [
    { label: 'Home', to: '/' },
    { label: 'About', to: '/about' },
    { label: 'Features', to: '/features' },
    { label: 'Technology', to: '/technology' },
    { label: 'Contact', to: '/contact' },
  ]

  return (
    <div className="site-shell">
      <header className="site-header">
        <div className="site-brand">
          <div className="brand-mark" aria-label="EcoMind AI brand mark">
            <span>EM</span>
            <div>
              <strong>EcoMind</strong>
              <small>AI waste operations</small>
            </div>
          </div>
        </div>

        <nav className="site-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'site-nav-link active' : 'site-nav-link')}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="site-actions">
          <Link to="/app" className="secondary-button site-secondary">Open app</Link>
          <Link to="/app" className="primary-button site-primary">Report Waste</Link>
        </div>
      </header>

      <main className="site-main">
        <Outlet />
      </main>

      <footer className="site-footer">
        <div>
          <strong>EcoMind AI</strong>
          <p>Intelligent waste management for cleaner, smarter cities.</p>
        </div>
        <div className="footer-links">
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms & Conditions</Link>
          <Link to="/contact">Contact</Link>
        </div>
      </footer>

      {!cookieNoticeAccepted && (
        <div className="cookie-banner" role="dialog" aria-live="polite">
          <div>
            <strong>Privacy notice</strong>
            <p>EcoMind uses essential local session storage for authentication. We do not use non-essential tracking cookies by default.</p>
          </div>
          <button type="button" className="primary-button" onClick={onDismissCookieNotice}>Understood</button>
        </div>
      )}
    </div>
  )
}

function HomePage() {
  usePageMeta('EcoMind AI | Intelligent Waste Management & Sustainability', 'EcoMind AI helps communities report waste, optimize collections, reduce landfill risk, and improve sustainability through AI-powered operations.')
  trackEvent('public_home_view')

  return (
    <>
      <section className="hero section-shell">
        <div className="hero-copy">
          <p className="eyebrow">Intelligent Waste Management</p>
          <h1>EcoMind AI helps cities act on waste before it becomes a problem.</h1>
          <p className="lede">From citizen reports to AI classification, route planning, complaint handling, and sustainability insights, EcoMind brings operational clarity to modern waste systems.</p>
          <div className="cta-row">
            <Link to="/app" className="primary-button">Report Waste</Link>
            <Link to="/features" className="secondary-button">Explore features</Link>
          </div>
          <ul className="stat-row" aria-label="Impact metrics">
            <li><strong>AI</strong><span>Waste review</span></li>
            <li><strong>Smart</strong><span>Collection routing</span></li>
            <li><strong>Impact</strong><span>Cleaner communities</span></li>
          </ul>
        </div>
        <div className="hero-panel">
          <div className="mini-card">
            <span className="panel-label">Live operations</span>
            <h3>Report · Classify · Collect</h3>
            <div className="mini-metrics">
              <div>
                <strong>92%</strong>
                <span>Route efficiency</span>
              </div>
              <div>
                <strong>1.4k</strong>
                <span>Reports tracked</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section-shell">
        <div className="section-heading">
          <p className="eyebrow">How it works</p>
          <h2>One system for the full waste loop</h2>
        </div>
        <div className="feature-grid three-up">
          <article className="info-card">
            <h3>1. Report</h3>
            <p>Citizens log waste issues with location, description, and context.</p>
          </article>
          <article className="info-card">
            <h3>2. Classify</h3>
            <p>EcoMind applies AI-supported waste categorization and confidence scoring.</p>
          </article>
          <article className="info-card">
            <h3>3. Resolve</h3>
            <p>Collectors receive optimized routes and admins monitor service outcomes.</p>
          </article>
        </div>
      </section>

      <section className="section-shell alt-section">
        <div className="section-heading">
          <p className="eyebrow">Sustainability</p>
          <h2>Built for environmental impact</h2>
        </div>
        <div className="feature-grid four-up">
          <article className="info-card">
            <h3>AI route optimization</h3>
            <p>Minimize idle travel and improve collection efficiency across service zones.</p>
          </article>
          <article className="info-card">
            <h3>Complaint management</h3>
            <p>Flag issues fast, assign ownership, and track resolution accountability.</p>
          </article>
          <article className="info-card">
            <h3>Carbon marketplace</h3>
            <p>Support reward and incentive loops tied to waste reduction and sustainability action.</p>
          </article>
          <article className="info-card">
            <h3>Open-source ecosystem</h3>
            <p>EcoMind is designed to integrate with open-source AI and optimization technologies such as Hugging Face, PyTorch, Ollama, OR-Tools, PostgreSQL, and OSRM.</p>
          </article>
        </div>
      </section>
    </>
  )
}

function AboutPage() {
  usePageMeta('About EcoMind AI | Smart Waste Management', 'Learn how EcoMind AI brings community reporting, AI classification, route planning, and sustainability oversight into one operational platform.')
  return (
    <section className="section-shell narrow-shell">
      <p className="eyebrow">About EcoMind</p>
      <h1>EcoMind AI connects communities, teams, and sustainability goals.</h1>
      <p>EcoMind is designed as a modern waste and environmental operations platform for cities, residential communities, and sustainability-focused organizations. The system supports citizen reporting, collector workflows, admin oversight, AI-assisted classification, and operational analytics in one connected environment.</p>
      <p>It focuses on practical action: turn reports into workflows, route teams efficiently, identify risk early, and help organizations measure impact beyond cleanup alone.</p>
    </section>
  )
}

function FeaturesPage() {
  usePageMeta('EcoMind AI Features | AI-Powered Waste Management', 'Explore the EcoMind platform features for waste reporting, AI classification, collection operations, complaints, analytics, rewards, and route optimization.')
  const features = [
    'AI waste classification baseline',
    'Citizen waste reporting',
    'Collector assignment and route planning',
    'Complaint and issue management',
    'Environmental monitoring records',
    'Carbon credit and rewards flows',
    'Municipal and service-area integration ready',
    'Context-aware analytics dashboards',
  ]

  return (
    <section className="section-shell">
      <p className="eyebrow">Features</p>
      <h1>Everything waste teams need to operate with clarity.</h1>
      <div className="feature-grid feature-list">
        {features.map((feature) => (
          <article key={feature} className="info-card compact-card">
            <h3>{feature}</h3>
          </article>
        ))}
      </div>
    </section>
  )
}

function HowItWorksPage() {
  usePageMeta('How EcoMind AI Works', 'Follow a waste report from citizen submission through classification, collection, and measurable impact.')
  return (
    <section className="section-shell narrow-shell">
      <p className="eyebrow">How it works</p>
      <h1>Turn a reported problem into a verified operational outcome.</h1>
      <div className="feature-grid feature-list">
        {['Report with context and location', 'Classify with a documented AI baseline', 'Assign and schedule collection work', 'Route field teams with optional road data', 'Verify completion and notify the citizen', 'Measure rewards and sustainability impact'].map((step, index) => (
          <article key={step} className="info-card compact-card"><h3>{index + 1}. {step}</h3></article>
        ))}
      </div>
    </section>
  )
}

function TechnologyPage() {
  usePageMeta('EcoMind AI Technology', 'Explore the open-source technologies and adapter-based architecture behind EcoMind AI.')
  return (
    <section className="section-shell narrow-shell">
      <p className="eyebrow">Technology</p>
      <h1>Open architecture for practical environmental operations.</h1>
      <p>EcoMind is built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, React, TypeScript, and Vite. Optional adapters provide controlled integration points for OSRM routing, local AI providers, future optimization, notifications, and IoT.</p>
      <p>Current AI classification uses an explicitly documented deterministic fallback. External models and live services are enabled only when configured and verified in the deployment environment.</p>
    </section>
  )
}

function SustainabilityPage() {
  usePageMeta('EcoMind AI Sustainability', 'Understand how EcoMind AI connects waste operations, rewards, and sustainability measurement.')
  return (
    <section className="section-shell narrow-shell">
      <p className="eyebrow">Sustainability</p>
      <h1>Measure the work behind cleaner communities.</h1>
      <p>EcoMind connects verified reports, completed collections, environmental records, and citizen participation so teams can understand operational impact over time.</p>
      <p>Reward points and sustainability records are separate from legally recognized carbon credits. Any environmental calculation must be configured with a documented methodology and source.</p>
    </section>
  )
}

function ContactPage() {
  usePageMeta('Contact EcoMind AI', 'Contact EcoMind AI to learn more about the waste management platform, AI services, municipal deployment, or partnership conversations.')
  return (
    <section className="section-shell narrow-shell">
      <p className="eyebrow">Contact</p>
      <h1>Talk with the EcoMind team.</h1>
      <div className="contact-panel">
        <p>Email: <a href="mailto:hello@ecomind.ai">hello@ecomind.ai</a></p>
        <p>Organization: <strong>[ORGANIZATION NAME]</strong></p>
        <p>Deployment: <strong>Local or municipal pilot environment</strong></p>
      </div>
    </section>
  )
}

function PrivacyPage() {
  usePageMeta('Privacy Policy | EcoMind AI', 'Learn how EcoMind AI handles account data, waste reports, AI processing, authentication, analytics, and user privacy in the platform.')
  return (
    <section className="section-shell narrow-shell legal-page">
      <p className="eyebrow">Privacy Policy</p>
      <h1>Privacy Policy</h1>
      <p>EcoMind AI processes data necessary to support waste reporting, collection operations, user authentication, and sustainability reporting. This page describes the categories of data used by the platform and the general handling approach.</p>
      <h2>Information collected</h2>
      <ul>
        <li>Account information such as name, email, and role</li>
        <li>Waste report details including description, location, and optional coordinates</li>
        <li>Collection and complaint metadata</li>
        <li>Authentication and session data used by the backend</li>
        <li>Operational analytics without sensitive personal information</li>
      </ul>
      <h2>AI processing</h2>
      <p>Waste descriptions and related metadata may be used to support AI-assisted classification and recommendations. This is a local or integration-based processing workflow and should be reviewed according to your deployment context.</p>
      <h2>Cookies and local storage</h2>
      <p>The current application uses essential local session storage for authenticated user operation. No non-essential advertising or tracking cookies are enabled by default. If a deployment adds analytics, the implementation should be configurable and consent-aware.</p>
      <h2>Data retention</h2>
      <p>Retention periods should be set by the controlling organization. Placeholder: [DATA RETENTION PERIOD].</p>
      <h2>Contact</h2>
      <p>For privacy questions, contact [PROJECT CONTACT EMAIL].</p>
    </section>
  )
}

function TermsPage() {
  usePageMeta('Terms & Conditions | EcoMind AI', 'Review the EcoMind AI terms governing acceptable use, user responsibilities, AI recommendations, and product operation.')
  return (
    <section className="section-shell narrow-shell legal-page">
      <p className="eyebrow">Terms & Conditions</p>
      <h1>Terms & Conditions</h1>
      <p>These terms describe the expected use of EcoMind AI as a waste-management and sustainability operations platform. The service may be used for authorized municipal, institutional, or community operations.</p>
      <h2>Acceptable use</h2>
      <p>Users must provide truthful report information and use the platform responsibly. Uploads, reports, or actions that are deceptive, abusive, or harmful are not permitted.</p>
      <h2>AI output</h2>
      <p>AI-assisted classifications and recommendations are advisory and should be reviewed by humans before operational action. The system does not replace official municipal or operational judgment.</p>
      <h2>Service limitations</h2>
      <p>Route optimization, environmental monitoring, and sustainability insights are dependent on available data quality and service configuration. Outputs should be treated as decision support rather than guaranteed operational truth.</p>
      <h2>Account responsibility</h2>
      <p>Users are responsible for maintaining the confidentiality of account access and for using the system according to their role and authorization level.</p>
      <h2>Contact</h2>
      <p>For questions, contact [PROJECT CONTACT EMAIL] or [ORGANIZATION NAME].</p>
    </section>
  )
}

function NotFoundPage() {
  usePageMeta('Page not found | EcoMind AI', 'The requested EcoMind AI page could not be found.')
  return (
    <section className="section-shell narrow-shell not-found-shell">
      <p className="eyebrow">404</p>
      <h1>Oops! This page could not be found.</h1>
      <p>It may have moved, been removed, or never existed. You can return to the EcoMind homepage or open the authenticated app.</p>
      <div className="cta-row">
        <Link to="/" className="primary-button">Return home</Link>
        <Link to="/app" className="secondary-button">Open app</Link>
      </div>
    </section>
  )
}

function AuthenticatedApp({ token, onSignOut }: { token: string; onSignOut: () => void }) {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [view, setView] = useState<View>('overview')
  const [loading, setLoading] = useState(Boolean(token))
  const [error, setError] = useState('')
  const [data, setData] = useState<DashboardData>({})

  useEffect(() => {
    if (!token) return
    api<Profile>('/users/me', token)
      .then(setProfile)
      .catch(() => {
        localStorage.removeItem('ecomind_token')
        onSignOut()
      })
      .finally(() => setLoading(false))
  }, [onSignOut, token])

  useEffect(() => {
    if (!token || !profile) return
    const requests: Promise<void>[] = []
    if (profile.role_id === 4) {
      requests.push(api<DashboardStats>('/analytics/dashboard', token).then((stats) => setData((current) => ({ ...current, stats }))))
    }
    if (profile.role_id === 5) {
      requests.push(api<Report[]>('/waste-reports/my-reports', token).then((reports) => setData((current) => ({ ...current, reports }))))
      requests.push(api<{ points: number }>('/rewards/me', token).then(({ points }) => setData((current) => ({ ...current, points }))))
      requests.push(api<Complaint[]>('/complaints/my', token).then((complaints) => setData((current) => ({ ...current, complaints }))))
    }
    if (profile.role_id === 6) {
      requests.push(api<Collection[]>('/collections/my-collections', token).then((collections) => setData((current) => ({ ...current, collections }))))
      requests.push(api<Route[]>('/routes/my-routes', token).then((routes) => setData((current) => ({ ...current, routes }))))
    }
    requests.push(api<Notification[]>('/notifications/', token).then((notifications) => setData((current) => ({ ...current, notifications }))))
    Promise.all(requests).catch((requestError: Error) => setError(requestError.message))
  }, [profile, token])

  if (!profile) {
    return <Login onLogin={(nextToken) => { localStorage.setItem('ecomind_token', nextToken); window.location.assign('/app') }} loading={loading} error={error} />
  }

  const role = roleNames[profile.role_id] ?? 'Citizen'
  const signOut = () => {
    localStorage.removeItem('ecomind_token')
    setProfile(null)
    setData({})
    onSignOut()
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark"><span>EM</span><div><strong>EcoMind</strong><small>operations console</small></div></div>
        <div className="side-label">Workspace</div>
        <nav aria-label="Primary navigation">
          <NavButton active={view === 'overview'} onClick={() => setView('overview')}>Overview</NavButton>
          {role === 'Citizen' && <><NavButton active={view === 'reports'} onClick={() => setView('reports')}>My reports</NavButton><NavButton active={view === 'create-report'} onClick={() => setView('create-report')}>New report</NavButton></>}
          {role === 'Citizen' && <><NavButton active={view === 'complaints'} onClick={() => setView('complaints')}>Complaints</NavButton><NavButton active={view === 'create-complaint'} onClick={() => setView('create-complaint')}>New complaint</NavButton></>}
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
        {view === 'create-report' && <CreateReport token={token} onCreated={() => { setView('reports'); api<Report[]>('/waste-reports/my-reports', token).then((reports) => setData((current) => ({ ...current, reports }))) }} />}
        {view === 'collections' && <CollectionList collections={data.collections ?? []} />}
        {view === 'routes' && <RouteList routes={data.routes ?? []} />}
        {view === 'complaints' && <ComplaintList complaints={data.complaints ?? []} />}
        {view === 'create-complaint' && <CreateComplaint token={token} onCreated={() => { setView('complaints'); api<Complaint[]>('/complaints/my', token).then((complaints) => setData((current) => ({ ...current, complaints }))) }} />}
        {view === 'notifications' && <NotificationList notifications={data.notifications ?? []} />}
      </section>
    </main>
  )
}

function Login({ onLogin, loading, error }: { onLogin: (token: string) => void; loading: boolean; error: string }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState(error)
  const navigate = useNavigate()

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSubmitting(true); setMessage('')
    try {
      if (mode === 'register') {
        const registerResponse = await fetch(`${API_URL}/users/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, email, password }) })
        const registerResult = await registerResponse.json()
        if (!registerResponse.ok) throw new Error(registerResult.detail ?? 'Unable to create account')
      }
      const body = new URLSearchParams({ username: email, password })
      const response = await fetch(`${API_URL}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail ?? 'Unable to sign in')
      trackEvent('login_success', { email })
      onLogin(result.access_token)
      navigate('/app')
    } catch (loginError) { setMessage((loginError as Error).message) } finally { setSubmitting(false) }
  }

  return <main className="login-screen"><div className="login-panel"><div className="brand-mark large"><span>EM</span><div><strong>EcoMind</strong><small>smart waste operations</small></div></div><div className="login-copy"><p className="eyebrow">Environmental intelligence</p><h1>{mode === 'login' ? 'Make every collection count.' : 'Join the cleaner loop.'}</h1><p>One operational view for reports, routes, collections, and community impact.</p></div><div className="auth-tabs"><button type="button" className={mode === 'login' ? 'selected' : ''} onClick={() => setMode('login')}>Sign in</button><button type="button" className={mode === 'register' ? 'selected' : ''} onClick={() => setMode('register')}>Register</button></div><form onSubmit={submit}>{mode === 'register' && <label>Name<input value={name} onChange={(event) => setName(event.target.value)} minLength={2} required /></label>}<label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required /></label>{message && <div className="form-error">{message}</div>}<button className="primary-button" disabled={submitting || loading}>{submitting ? 'Working...' : mode === 'login' ? 'Sign in to workspace' : 'Create citizen account'}</button></form><small className="login-note">Passwords are hashed by the EcoMind backend.</small></div><div className="login-aside"><div className="signal-line" /><p>Waste is not the end of a system. It is a signal.</p><span>Track it. Act on it. Learn from it.</span></div></main>
}

function CreateReport({ token, onCreated }: { token: string; onCreated: () => void }) {
  const [wasteType, setWasteType] = useState('plastic')
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState('')
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setMessage('')
    try {
      const report = await api<Report>('/waste-reports/', token, { method: 'POST', body: JSON.stringify({ waste_type: wasteType, description, location, latitude: latitude ? Number(latitude) : null, longitude: longitude ? Number(longitude) : null }) })
      await api(`/classification/${report.id}`, token, { method: 'POST' })
      trackEvent('waste_report_submitted', { waste_type: wasteType })
      onCreated()
    } catch (createError) { setMessage((createError as Error).message) } finally { setSaving(false) }
  }
  return <section className="panel form-panel"><div className="section-intro"><div><p className="eyebrow">Citizen activity</p><h2>Submit a waste report</h2></div></div><form className="report-form" onSubmit={submit}><label>Waste type<select value={wasteType} onChange={(event) => setWasteType(event.target.value)}>{['plastic', 'paper', 'glass', 'metal', 'organic', 'e-waste', 'other'].map((type) => <option key={type}>{type}</option>)}</select></label><label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} minLength={3} maxLength={5000} required placeholder="Describe what needs attention" /></label><label>Location<input value={location} onChange={(event) => setLocation(event.target.value)} minLength={2} maxLength={255} required placeholder="Street, ward, or landmark" /></label><div className="form-columns"><label>Latitude<input type="number" value={latitude} onChange={(event) => setLatitude(event.target.value)} min={-90} max={90} step="any" placeholder="Optional" /></label><label>Longitude<input type="number" value={longitude} onChange={(event) => setLongitude(event.target.value)} min={-180} max={180} step="any" placeholder="Optional" /></label></div>{message && <div className="form-error">{message}</div>}<button className="primary-button" disabled={saving}>{saving ? 'Submitting...' : 'Submit and classify report'}</button></form></section>
}

function Overview({ role, profile, data }: { role: Role; profile: Profile; data: DashboardData }) {
  if (role === 'Admin' && data.stats) { const stats = data.stats; return <><section className="welcome"><div><p className="eyebrow">Live operations</p><h2>Platform overview</h2><p>Monitor the system from intake through resolution.</p></div><div className="date-chip">{new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</div></section><div className="metric-grid"><Metric label="Total users" value={stats.total_users} detail={`${stats.citizens} citizens`} accent="mint" /><Metric label="Open reports" value={stats.pending_reports} detail={`${stats.total_reports} total reports`} accent="amber" /><Metric label="Collections pending" value={stats.pending_collections} detail={`${stats.completed_collections} completed`} accent="coral" /><Metric label="Unresolved complaints" value={stats.unresolved_complaints} detail={`${stats.total_complaints} total complaints`} accent="blue" /></div><section className="content-grid"><div className="panel feature-panel"><div className="panel-heading"><div><p className="eyebrow">System health</p><h3>Operational pulse</h3></div><span className="live-badge"><span className="status-dot" /> Live</span></div><div className="pulse-graphic"><div className="pulse-bar one" /><div className="pulse-bar two" /><div className="pulse-bar three" /><div className="pulse-bar four" /><div className="pulse-bar five" /><div className="pulse-bar six" /><div className="pulse-bar seven" /></div><p className="muted">Metrics are calculated by the backend from current database records.</p></div><div className="panel"><div className="panel-heading"><div><p className="eyebrow">Next move</p><h3>Keep the loop closed</h3></div></div><p className="panel-copy">Assign pending collections, review unresolved complaints, and keep field teams moving.</p><button className="secondary-button">Open operations queue <span>↗</span></button></div></section></> }
  return <><section className="welcome"><div><p className="eyebrow">{role} workspace</p><h2>Welcome back, {profile.name.split(' ')[0]}.</h2><p>Your sustainability activity stays in one clear place.</p></div><div className="impact-number"><strong>{role === 'Citizen' ? data.points ?? 0 : data.collections?.filter((item) => item.status === 'collected').length ?? 0}</strong><span>{role === 'Citizen' ? 'points earned' : 'collections completed'}</span></div></section><div className="metric-grid"><Metric label={role === 'Citizen' ? 'Reward points' : 'Assigned work'} value={role === 'Citizen' ? data.points ?? 0 : data.collections?.length ?? 0} detail={role === 'Citizen' ? 'Server-verified activity' : 'Current assignments'} accent="mint" /><Metric label="Notifications" value={data.notifications?.filter((item) => !item.read_at).length ?? 0} detail="Unread updates" accent="amber" /><Metric label={role === 'Citizen' ? 'My reports' : 'Optimized routes'} value={role === 'Citizen' ? data.reports?.length ?? 0 : data.routes?.length ?? 0} detail="From the backend" accent="blue" /></div></>
}

function Metric({ label, value, detail, accent }: { label: string; value: number; detail: string; accent: string }) { return <article className={`metric-card ${accent}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article> }
function NavButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) { return <button type="button" className={`nav-button ${active ? 'active' : ''}`} onClick={onClick}>{children}</button> }
function ReportList({ reports, points }: { reports: Report[]; points: number }) { return <section className="panel-list"><div className="section-intro"><div><p className="eyebrow">Citizen activity</p><h2>Waste reports</h2></div><span className="count-pill">{points} points</span></div>{reports.length === 0 ? <EmptyState text="No reports submitted yet." /> : reports.map((report) => <div className="list-row" key={report.id}><div className="row-icon">{report.waste_type.slice(0, 1).toUpperCase()}</div><div className="row-main"><strong>{report.description}</strong><span>{report.location} · {report.ai_waste_type ?? report.waste_type}</span></div><Status value={report.status} /></div>)}</section> }
function CollectionList({ collections }: { collections: Collection[] }) { return <section className="panel-list"><div className="section-intro"><div><p className="eyebrow">Field operations</p><h2>Assigned collections</h2></div><span className="count-pill">{collections.length} tasks</span></div>{collections.length === 0 ? <EmptyState text="No collections assigned." /> : collections.map((item) => <div className="list-row" key={item.id}><div className="row-icon">C</div><div className="row-main"><strong>Collection #{item.id}</strong><span>Report #{item.report_id}{item.scheduled_at ? ` · ${new Date(item.scheduled_at).toLocaleString()}` : ''}</span></div><Status value={item.status} /></div>)}</section> }
function RouteList({ routes }: { routes: Route[] }) { return <section className="panel-list"><div className="section-intro"><div><p className="eyebrow">Route planning</p><h2>Optimized routes</h2></div><span className="count-pill">{routes.length} routes</span></div>{routes.length === 0 ? <EmptyState text="No optimized routes yet." /> : routes.map((route) => <div className="list-row" key={route.id}><div className="row-icon">R</div><div className="row-main"><strong>Route #{route.id}</strong><span>{route.stops.length} stops · {route.estimated_distance_km.toFixed(2)} km</span></div><Status value={route.status} /></div>)}</section> }
function NotificationList({ notifications }: { notifications: Notification[] }) { return <section className="panel-list"><div className="section-intro"><div><p className="eyebrow">Updates</p><h2>Notifications</h2></div></div>{notifications.length === 0 ? <EmptyState text="You're all caught up." /> : notifications.map((item) => <div className={`list-row ${item.read_at ? 'read' : ''}`} key={item.id}><div className="row-icon">N</div><div className="row-main"><strong>{item.title}</strong><span>{item.message}</span></div><small>{item.read_at ? 'Read' : 'New'}</small></div>)}</section> }
function ComplaintList({ complaints }: { complaints: Complaint[] }) { return <section className="panel-list"><div className="section-intro"><div><p className="eyebrow">Citizen support</p><h2>My complaints</h2></div><span className="count-pill">{complaints.length} cases</span></div>{complaints.length === 0 ? <EmptyState text="No complaints submitted yet." /> : complaints.map((item) => <div className="list-row" key={item.id}><div className="row-icon">!</div><div className="row-main"><strong>{item.title ?? `Complaint #${item.id}`}</strong><span>{item.location} · {item.ai_priority ?? 'Review pending'}</span></div><Status value={item.status} /></div>)}</section> }
function CreateComplaint({ token, onCreated }: { token: string; onCreated: () => void }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setMessage('')
    try { await api('/complaints/', token, { method: 'POST', body: JSON.stringify({ title, description, location }) }); onCreated() }
    catch (error) { setMessage((error as Error).message) }
    finally { setSaving(false) }
  }
  return <section className="panel form-panel"><div className="section-intro"><div><p className="eyebrow">Citizen support</p><h2>Submit a complaint</h2></div></div><form className="report-form" onSubmit={submit}><label>Title<input value={title} onChange={(event) => setTitle(event.target.value)} minLength={2} maxLength={200} required /></label><label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} minLength={3} maxLength={5000} required /></label><label>Location<input value={location} onChange={(event) => setLocation(event.target.value)} minLength={2} maxLength={255} required /></label>{message && <div className="form-error">{message}</div>}<button className="primary-button" disabled={saving}>{saving ? 'Submitting...' : 'Submit complaint'}</button></form></section>
}
function Status({ value }: { value: string }) { return <span className={`status status-${value.replace('_', '-')}`}>{value.replace('_', ' ')}</span> }
function EmptyState({ text }: { text: string }) { return <div className="empty-state">{text}</div> }
function viewTitle(view: View) { return { overview: 'Overview', reports: 'My reports', 'create-report': 'New report', collections: 'Collections', routes: 'Routes', complaints: 'Complaints', 'create-complaint': 'New complaint', notifications: 'Notifications' }[view] }

export default App
