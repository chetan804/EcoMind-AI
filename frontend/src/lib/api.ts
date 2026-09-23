/* API client: token handling, transparent refresh, typed helpers.
 * Uses relative /api paths only — the dev server proxies to the backend. */

const BASE = '/api/v1'

let accessToken: string | null = null
let refreshToken: string | null = null

const listeners = new Set<() => void>()

export function setTokens(access: string | null, refresh: string | null) {
  accessToken = access
  refreshToken = refresh
  listeners.forEach((l) => l())
}

export function getAccessToken() {
  return accessToken
}

export function onTokensChanged(fn: () => void) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export class ApiError extends Error {
  code: string
  status: number
  details: Record<string, unknown>
  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

let refreshPromise: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  if (!refreshToken) return false
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
        if (!res.ok) return false
        const data = await res.json()
        setTokens(data.access_token, data.refresh_token)
        return true
      } catch {
        return false
      } finally {
        setTimeout(() => (refreshPromise = null), 0)
      }
    })()
  }
  return refreshPromise
}

export async function api<T = unknown>(
  method: string,
  path: string,
  opts: { json?: unknown; form?: FormData; orgId?: string | null; raw?: boolean; retry?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  if (opts.orgId) headers['X-Org-Id'] = opts.orgId
  if (opts.json !== undefined && !opts.form) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: opts.form ?? (opts.json !== undefined ? JSON.stringify(opts.json) : undefined),
  })

  if (res.status === 401 && refreshToken && opts.retry !== false) {
    const ok = await tryRefresh()
    if (ok) return api<T>(method, path, { ...opts, retry: false })
    setTokens(null, null)
    throw new ApiError(401, 'unauthorized', 'Session expired. Please log in again.')
  }

  if (!res.ok) {
    let code = 'error'
    let message = `Request failed (${res.status})`
    let details: Record<string, unknown> = {}
    try {
      const body = await res.json()
      if (body?.error) {
        code = body.error.code ?? code
        message = body.error.message ?? message
        details = body.error.details ?? {}
      }
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, code, message, details)
  }

  if (opts.raw) return res as unknown as T
  if (res.status === 204) return undefined as T
  const ct = res.headers.get('content-type') ?? ''
  return (ct.includes('json') ? res.json() : res.text()) as Promise<T>
}

export const get = <T = unknown>(path: string, orgId?: string | null) => api<T>('GET', path, { orgId })
export const post = <T = unknown>(path: string, json?: unknown, orgId?: string | null) =>
  api<T>('POST', path, { json, orgId })
export const patch = <T = unknown>(path: string, json?: unknown, orgId?: string | null) =>
  api<T>('PATCH', path, { json, orgId })
export const postForm = <T = unknown>(path: string, form: FormData, orgId?: string | null) =>
  api<T>('POST', path, { form, orgId })

/* ---------- shared types ---------- */

export interface Membership {
  organization_id: string
  organization_name: string
  organization_slug: string
  role_code: string
  role_name: string
  is_default: boolean
  is_demo: boolean
  permissions: string[]
}

export interface Me {
  id: string
  email: string
  full_name: string
  phone: string | null
  is_active: boolean
  is_platform_admin: boolean
  memberships: Membership[]
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  expires_in: number
}

export interface Org {
  id: string
  slug: string
  name: string
  org_type: string
  status: string
  timezone: string
  city: string | null
  country: string | null
  is_demo: boolean
  allow_citizen_signup: boolean
  allow_anonymous_reports: boolean
  branding: Record<string, unknown>
  settings: Record<string, unknown>
  created_at: string
}
