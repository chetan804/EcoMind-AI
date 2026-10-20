import { ApiError } from './api-client';

const FALLBACK_MESSAGE = 'Something went wrong. Please try again.';

/** Convert any thrown value into a message that is safe to show to a user. */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return 'Cannot reach the server. Check your connection and try again.';
    if (error.status === 401) return 'Your session has expired. Please sign in again.';
    if (error.status === 403) return 'You do not have permission to do that.';
    if (error.status >= 500) return FALLBACK_MESSAGE;
    return error.message || FALLBACK_MESSAGE;
  }
  return FALLBACK_MESSAGE;
}

/** Whether a failed request is worth retrying automatically (network and 5xx, never 4xx). */
export function isRetryableError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 0 || error.status >= 500);
}
