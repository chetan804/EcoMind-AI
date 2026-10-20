import { API_V1_PATH, config } from '@/app/config';

/** Structured error from the backend (docs/api/api-conventions.md) or from the network layer. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;
  /** Parsed JSON body when the response had one (for example the 503 readiness report). */
  readonly body: unknown;
  /** Seconds from a `Retry-After` header (429 responses), when present. */
  readonly retryAfterSeconds: number | null;

  constructor(init: {
    status: number;
    code: string;
    message: string;
    details?: unknown;
    requestId?: string | null;
    body?: unknown;
    retryAfterSeconds?: number | null;
  }) {
    super(init.message);
    this.name = 'ApiError';
    this.status = init.status;
    this.code = init.code;
    this.details = init.details ?? null;
    this.requestId = init.requestId ?? null;
    this.body = init.body ?? null;
    this.retryAfterSeconds = init.retryAfterSeconds ?? null;
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  /**
   * A `Blob`/`File` is sent as the raw request body with its own content type (image upload).
   * Anything else is sent as JSON.
   */
  body?: unknown;
  signal?: AbortSignal;
  /**
   * true (default): path is relative to /api/v1.
   * false: path is relative to the API origin (operational endpoints such as /health, /ready).
   */
  versioned?: boolean;
  /** Extra request headers (for example the CSRF header on cookie-authenticated endpoints). */
  headers?: Record<string, string>;
  /**
   * true (default): attach the access token when there is one, and on a 401 refresh the session
   * once and retry. false: send as-is (sign-in, sign-up, refresh and other public calls).
   */
  authenticated?: boolean;
}

/**
 * Hooks installed by the auth feature, so this module needs no knowledge of sessions.
 * `refreshAccessToken` must resolve true only when a new access token is now available.
 */
export interface AuthHooks {
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<boolean>;
}

let authHooks: AuthHooks | null = null;

export function configureAuthHooks(hooks: AuthHooks | null): void {
  authHooks = hooks;
}

export function buildUrl(path: string, versioned = true): string {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${config.apiBaseUrl}${versioned ? API_V1_PATH : ''}${normalized}`;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function parseRetryAfter(response: Response): number | null {
  const raw = response.headers.get('Retry-After');
  const seconds = raw === null ? Number.NaN : Number.parseInt(raw, 10);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

function toApiError(response: Response, body: unknown): ApiError {
  const envelope = (body as { error?: Record<string, unknown> } | null)?.error;
  return new ApiError({
    status: response.status,
    code: typeof envelope?.code === 'string' ? envelope.code : 'http_error',
    message: typeof envelope?.message === 'string' ? envelope.message : response.statusText || 'Request failed',
    details: envelope?.details,
    requestId: typeof envelope?.request_id === 'string' ? envelope.request_id : null,
    body,
    retryAfterSeconds: parseRetryAfter(response),
  });
}

async function send(path: string, options: RequestOptions, token: string | null): Promise<Response> {
  const { method = 'GET', body, signal, versioned = true, headers = {} } = options;
  const raw = body instanceof Blob;
  try {
    return await fetch(buildUrl(path, versioned), {
      method,
      signal,
      // Needed so the HttpOnly refresh cookie is sent when the API is on another origin; for the
      // default same-origin deployment it changes nothing.
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(body !== undefined
          ? { 'Content-Type': raw ? body.type || 'application/octet-stream' : 'application/json' }
          : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : raw ? body : JSON.stringify(body),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
    throw new ApiError({ status: 0, code: 'network_error', message: 'Network request failed' });
  }
}

/** The single HTTP entry point for the app. Resolves with parsed JSON or rejects with ApiError. */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const useAuth = options.authenticated !== false && authHooks !== null;
  let response = await send(path, options, useAuth ? (authHooks?.getAccessToken() ?? null) : null);

  if (response.status === 401 && useAuth && authHooks && (await authHooks.refreshAccessToken())) {
    response = await send(path, options, authHooks.getAccessToken());
  }

  const parsed = await readJson(response);
  if (!response.ok) throw toApiError(response, parsed);
  return parsed as T;
}
