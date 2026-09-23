/* Auth context: current user, active organization, permission helpers. */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  api,
  getAccessToken,
  onTokensChanged,
  post,
  setTokens,
  type Me,
  type Membership,
  type Org,
  type TokenPair,
} from './api'

interface AuthState {
  user: Me | null
  loading: boolean
  activeMembership: Membership | null
  orgId: string | null
  hasPerm: (code: string) => boolean
  isDemo: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string, joinSlug?: string) => Promise<void>
  logout: () => Promise<void>
  refreshMe: () => Promise<void>
  switchOrg: (orgId: string) => void
  applyTokens: (tokens: TokenPair) => void
}

const Ctx = createContext<AuthState | null>(null)

const ORG_STORAGE_KEY = 'ecomind.activeOrg'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [orgId, setOrgId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const loadMe = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null)
      setOrgId(null)
      setLoading(false)
      return
    }
    try {
      const me = await api<Me>('GET', '/auth/me')
      setUser(me)
      const stored = localStorage.getItem(ORG_STORAGE_KEY)
      const valid = stored && me.memberships.some((m) => m.organization_id === stored)
      const chosen = valid ? stored : me.memberships[0]?.organization_id ?? null
      setOrgId(chosen)
    } catch {
      setUser(null)
      setOrgId(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const unsub = onTokensChanged(() => {
      if (!getAccessToken()) {
        setUser(null)
        setOrgId(null)
      }
    })
    void loadMe()
    return () => {
      unsub()
    }
  }, [loadMe])

  const activeMembership = useMemo(
    () => user?.memberships.find((m) => m.organization_id === orgId) ?? null,
    [user, orgId],
  )

  const hasPerm = useCallback(
    (code: string) => {
      if (!activeMembership) return false
      if (user?.is_platform_admin) return true
      return activeMembership.permissions.includes(code)
    },
    [activeMembership, user],
  )

  const value: AuthState = {
    user,
    loading,
    activeMembership,
    orgId,
    hasPerm,
    isDemo: activeMembership?.is_demo ?? false,
    login: async (email, password) => {
      const res = await post<{ tokens: TokenPair; user: Me }>('/auth/login', { email, password })
      setTokens(res.tokens.access_token, res.tokens.refresh_token)
      localStorage.removeItem(ORG_STORAGE_KEY)
      setUser(res.user)
      const first = res.user.memberships[0]?.organization_id ?? null
      setOrgId(first)
      setLoading(false)
    },
    register: async (email, password, fullName, joinSlug) => {
      const res = await post<{ tokens: TokenPair; user: Me }>('/auth/register', {
        email,
        password,
        full_name: fullName,
        join_org_slug: joinSlug || null,
      })
      setTokens(res.tokens.access_token, res.tokens.refresh_token)
      setUser(res.user)
      const first = res.user.memberships[0]?.organization_id ?? null
      setOrgId(first)
      setLoading(false)
    },
    logout: async () => {
      const refresh = localStorage.getItem('ecomind.refresh')
      try {
        if (refresh) await post('/auth/logout', { refresh_token: refresh })
      } catch {
        /* best effort */
      }
      setTokens(null, null)
      setUser(null)
      setOrgId(null)
      queryClient.clear()
    },
    refreshMe: loadMe,
    switchOrg: (id) => {
      setOrgId(id)
      localStorage.setItem(ORG_STORAGE_KEY, id)
      queryClient.clear()
    },
    applyTokens: (tokens) => setTokens(tokens.access_token, tokens.refresh_token),
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}

/* Role-based navigation destinations */
export function homeRouteFor(m: Membership | null, isPlatformAdmin: boolean | undefined): string {
  if (!m) return '/onboarding'
  if (isPlatformAdmin) return '/exec'
  switch (m.role_code) {
    case 'org_admin':
      return '/ops'
    case 'ops_manager':
    case 'field_supervisor':
      return '/ops'
    case 'collector':
      return '/field'
    case 'sustainability_analyst':
      return '/sustainability'
    case 'citizen':
      return '/app'
    default:
      return '/exec'
  }
}
