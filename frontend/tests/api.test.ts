/* Tests for the API client: error normalization, token refresh, org header. */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, get, setTokens } from '../src/lib/api'

const BASE = '/api/v1'

function mockFetchOnce(handler: (url: string, init?: RequestInit) => Promise<Response>) {
  return vi.fn(handler)
}

let fetchMock: ReturnType<typeof mockFetchOnce>

beforeEach(() => {
  setTokens(null, null)
  fetchMock = mockFetchOnce(async () => new Response('{}', { status: 200 }))
  globalThis.fetch = fetchMock as unknown as typeof fetch
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('api client', () => {
  it('sends GET with JSON accept header', async () => {
    await get('/ping')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(BASE + '/ping')
    expect((init?.headers as Record<string, string>)['Accept']).toBe('application/json')
  })

  it('raises ApiError with structured details on validation failure', async () => {
    fetchMock = mockFetchOnce(async () =>
      new Response(JSON.stringify({ error: { code: 'VALIDATION_ERROR', message: 'Bad input', details: [{ field: 'lat' }] } }), {
        status: 422,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const err = await api('POST', '/waste/reports', { json: {} }).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    const apiErr = err as ApiError
    expect(apiErr.status).toBe(422)
    expect(apiErr.code).toBe('VALIDATION_ERROR')
    expect(apiErr.message).toBe('Bad input')
    expect(apiErr.details).toEqual([{ field: 'lat' }])
  })

  it('includes bearer token when set', async () => {
    setTokens('access-abc', 'refresh-xyz')
    await get('/auth/me')
    const [, init] = fetchMock.mock.calls[0]
    expect((init?.headers as Record<string, string>)['Authorization']).toBe('Bearer access-abc')
  })

  it('sends X-Org-Id when orgId is passed', async () => {
    setTokens('t', null)
    await get('/waste/reports', 'org-123')
    const [, init] = fetchMock.mock.calls[0]
    expect((init?.headers as Record<string, string>)['X-Org-Id']).toBe('org-123')
  })

  it('normalizes non-JSON error bodies', async () => {
    fetchMock = mockFetchOnce(async () => new Response('Internal Server Error', { status: 500 }))
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const err = await get('/boom').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(500)
    expect((err as ApiError).code).toBe('error')
    expect((err as ApiError).message).toBe('Request failed (500)')
  })

  it('surfaces the server error on 401 when no refresh token is available', async () => {
    setTokens('stale-token', null)
    fetchMock = mockFetchOnce(async () => new Response('{"error":{"code":"UNAUTHORIZED","message":"bad token"}}', {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    }))
    globalThis.fetch = fetchMock as unknown as typeof fetch
    const err = await get('/auth/me').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(401)
    expect((err as ApiError).code).toBe('UNAUTHORIZED')
    expect((err as ApiError).message).toBe('bad token')
  })
})
