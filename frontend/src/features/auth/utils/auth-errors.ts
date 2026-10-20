import { ApiError } from '@/services/api-client';

function describeWait(seconds: number | null): string {
  if (seconds === null) return 'a few minutes';
  if (seconds < 90) return `${Math.max(1, seconds)} seconds`;
  return `${Math.ceil(seconds / 60)} minutes`;
}

function withReference(message: string, error: ApiError): string {
  return error.requestId ? `${message} (reference ${error.requestId})` : message;
}

/** User-facing text for a failed sign-in / sign-up request. Never echoes server internals. */
export function describeAuthError(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Something went wrong. Please try again.';
  if (error.status === 0) return 'We could not reach the server. Check your connection and try again.';
  if (error.code === 'invalid_credentials') return 'Incorrect email or password.';
  if (error.status === 429) return `Too many attempts. Try again in ${describeWait(error.retryAfterSeconds)}.`;
  if (error.status >= 500) return withReference('The server had a problem. Please try again shortly.', error);
  return withReference('The request could not be completed.', error);
}

/** The server's password-policy messages (HTTP 422, code `weak_password`), or null. */
export function passwordPolicyMessages(error: unknown): string[] | null {
  if (!(error instanceof ApiError) || error.code !== 'weak_password') return null;
  const details = Array.isArray(error.details) ? (error.details as Array<{ message?: unknown }>) : [];
  const messages = details.map((d) => d.message).filter((m): m is string => typeof m === 'string');
  return messages.length > 0 ? messages : [error.message];
}

export const isEmailTaken = (error: unknown): boolean =>
  error instanceof ApiError && error.code === 'email_already_registered';

/**
 * Where to go after signing in. Only same-site paths are accepted, so a crafted
 * `state.from` cannot bounce a user to another origin; auth pages are never a destination.
 */
export function safeRedirectTarget(from: unknown, fallback = '/dashboard'): string {
  if (typeof from !== 'string') return fallback;
  if (!from.startsWith('/') || from.startsWith('//') || from.includes('\\')) return fallback;
  if (from === '/sign-in' || from === '/sign-up') return fallback;
  return from;
}
