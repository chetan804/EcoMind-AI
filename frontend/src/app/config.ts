/**
 * Runtime configuration. This is the ONLY place that reads import.meta.env; features import
 * `config` instead of hardcoding URLs.
 */

export const API_V1_PATH = '/api/v1';

/** Strip trailing slashes; an empty value means "same origin". */
export function normalizeBaseUrl(value: string | undefined): string {
  return (value ?? '').trim().replace(/\/+$/, '');
}

export const config = {
  /** Backend origin (no path). Empty string = same origin, proxied by the dev/preview server. */
  apiBaseUrl: normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
} as const;
