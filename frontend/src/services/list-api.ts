import type { z } from 'zod';
import { apiRequest } from './api-client';

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

/** Query string without empty values, so unset filters are not sent. */
export function toQuery(params: QueryParams = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

/** GET a validated response. The server's shape is checked at runtime, not just trusted. */
export async function getJson<T>(path: string, schema: z.ZodType<T>, params?: QueryParams, signal?: AbortSignal): Promise<T> {
  return schema.parse(await apiRequest<unknown>(`${path}${toQuery(params)}`, { signal }));
}

export async function sendJson<T>(
  method: 'POST' | 'PUT' | 'PATCH',
  path: string,
  schema: z.ZodType<T>,
  body?: unknown,
): Promise<T> {
  return schema.parse(await apiRequest<unknown>(path, { method, body: body ?? {} }));
}
