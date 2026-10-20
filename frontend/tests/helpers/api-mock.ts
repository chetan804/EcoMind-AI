import type { Mock } from 'vitest';
import { SESSION_HINT_KEY } from '@/services/session/session-store';
import type { SessionUser } from '@/services/session';
import { authResponse, isRefresh, testUser } from './session';

export interface RecordedCall {
  key: string;
  query: URLSearchParams;
  body: unknown;
}

type Reply = unknown | ((call: RecordedCall) => unknown);

/** A JSON error in the API's envelope (docs/api/api-conventions.md). */
export const errorReply = (status: number, code: string, message: string): Response =>
  Response.json({ error: { code, message } }, { status });

export const page = <T,>(items: T[], total = items.length) => ({ items, total, page: 1, page_size: 25 });

/**
 * Signs the test user in (through the real refresh path) and answers API calls from `routes`,
 * keyed `"GET /api/v1/path"`. A call with no matching route is recorded in `unmatched` and answered
 * 404, so a test that forgets a request fails loudly instead of silently seeing "not found".
 */
export function routeApi(
  fetchSpy: Mock,
  routes: Record<string, Reply>,
  user: SessionUser = testUser,
): { calls: RecordedCall[]; unmatched: string[] } {
  const calls: RecordedCall[] = [];
  const unmatched: string[] = [];
  window.localStorage.setItem(SESSION_HINT_KEY, '1');
  fetchSpy.mockImplementation((url: string, init?: RequestInit) => {
    if (isRefresh(url)) return Promise.resolve(Response.json(authResponse(user)));
    const parsed = new URL(String(url), 'http://localhost');
    const method = (init?.method ?? 'GET').toUpperCase();
    const key = `${method} ${parsed.pathname}`;
    let body: unknown = null;
    if (typeof init?.body === 'string') body = JSON.parse(init.body);
    const call: RecordedCall = { key, query: parsed.searchParams, body };
    const reply = routes[key];
    if (reply === undefined) {
      unmatched.push(key);
      return Promise.resolve(errorReply(404, 'not_found', `No test route for ${key}`));
    }
    calls.push(call);
    const result = typeof reply === 'function' ? (reply as (c: RecordedCall) => unknown)(call) : reply;
    return Promise.resolve(result instanceof Response ? result : Response.json(result));
  });
  return { calls, unmatched };
}
