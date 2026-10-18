import { ApiError, apiRequest } from '@/services/api-client';
import { livenessSchema, readinessSchema } from '../schemas/system-status';
import type { Liveness, Readiness } from '../types';

export async function fetchLiveness(signal?: AbortSignal): Promise<Liveness> {
  return livenessSchema.parse(await apiRequest<unknown>('/health', { versioned: false, signal }));
}

/**
 * GET /ready answers 503 with the same JSON body when a dependency is down. That is a valid
 * "not ready" report, not a failed request, so the body is parsed in both cases.
 */
export async function fetchReadiness(signal?: AbortSignal): Promise<Readiness> {
  try {
    return readinessSchema.parse(await apiRequest<unknown>('/ready', { versioned: false, signal }));
  } catch (error) {
    if (error instanceof ApiError && error.status === 503) {
      const parsed = readinessSchema.safeParse(error.body);
      if (parsed.success) return parsed.data;
    }
    throw error;
  }
}
