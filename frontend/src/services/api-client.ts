import { API_V1_PATH, config } from '@/app/config';

/** Structured error from the backend (docs/api/api-conventions.md) or from the network layer. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;
  /** Parsed JSON body when the response had one (for example the 503 readiness report). */
  readonly body: unknown;

  constructor(init: {
    status: number;
    code: string;
    message: string;
    details?: unknown;
    requestId?: string | null;
    body?: unknown;
  }) {
    super(init.message);
    this.name = 'ApiError';
    this.status = init.status;
    this.code = init.code;
    this.details = init.details ?? null;
    this.requestId = init.requestId ?? null;
    this.body = init.body ?? null;
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
  /**
   * true (default): path is relative to /api/v1.
   * false: path is relative to the API origin (operational endpoints such as /health, /ready).
   */
  versioned?: boolean;
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

function toApiError(response: Response, body: unknown): ApiError {
  const envelope = (body as { error?: Record<string, unknown> } | null)?.error;
  return new ApiError({
    status: response.status,
    code: typeof envelope?.code === 'string' ? envelope.code : 'http_error',
    message: typeof envelope?.message === 'string' ? envelope.message : response.statusText || 'Request failed',
    details: envelope?.details,
    requestId: typeof envelope?.request_id === 'string' ? envelope.request_id : null,
    body,
  });
}

/** The single HTTP entry point for the app. Resolves with parsed JSON or rejects with ApiError. */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, versioned = true } = options;
  let response: Response;
  try {
    response = await fetch(buildUrl(path, versioned), {
      method,
      signal,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
    throw new ApiError({ status: 0, code: 'network_error', message: 'Network request failed' });
  }

  const parsed = await readJson(response);
  if (!response.ok) throw toApiError(response, parsed);
  return parsed as T;
}
