import { ApiError } from '@/services/api-client';
import {
  describeAuthError,
  isEmailTaken,
  passwordPolicyMessages,
  safeRedirectTarget,
  tokenFromHash,
} from '@/features/auth/utils/auth-errors';

const err = (init: Partial<ConstructorParameters<typeof ApiError>[0]> & { status: number; code: string }) =>
  new ApiError({ message: 'm', ...init });

describe('safeRedirectTarget', () => {
  it('accepts same-site paths, including query strings', () => {
    expect(safeRedirectTarget('/classify')).toBe('/classify');
    expect(safeRedirectTarget('/reports?status=open#top')).toBe('/reports?status=open#top');
  });

  it.each([
    'https://evil.example/phish',
    '//evil.example',
    '/\\evil.example',
    'javascript:alert(1)',
    'classify',
    '',
    undefined,
    null,
    42,
    '/sign-in',
    '/sign-up',
  ])('falls back to the dashboard for %j (open-redirect and loop protection)', (value) => {
    expect(safeRedirectTarget(value)).toBe('/dashboard');
  });
});

describe('describeAuthError', () => {
  it('maps known failures to specific, non-leaky messages', () => {
    expect(describeAuthError(err({ status: 401, code: 'invalid_credentials' }))).toBe('Incorrect email or password.');
    expect(describeAuthError(err({ status: 0, code: 'network_error' }))).toMatch(/could not reach the server/);
    expect(describeAuthError(err({ status: 429, code: 'rate_limited', retryAfterSeconds: 45 }))).toBe(
      'Too many attempts. Try again in 45 seconds.',
    );
    expect(describeAuthError(err({ status: 429, code: 'rate_limited', retryAfterSeconds: 600 }))).toBe(
      'Too many attempts. Try again in 10 minutes.',
    );
    expect(describeAuthError(err({ status: 429, code: 'rate_limited' }))).toMatch(/a few minutes/);
  });

  it('includes the request id for server faults so support can trace them, and never the raw message', () => {
    const text = describeAuthError(err({ status: 500, code: 'internal_error', message: 'SQL exploded', requestId: 'req-9' }));
    expect(text).toContain('req-9');
    expect(text).not.toContain('SQL');
  });

  it('handles non-API errors', () => {
    expect(describeAuthError(new Error('boom'))).toBe('Something went wrong. Please try again.');
  });
});

describe('field-level error helpers', () => {
  it('extracts password policy messages from a weak_password error', () => {
    const error = err({
      status: 422,
      code: 'weak_password',
      details: [{ message: 'Use at least 12 characters.' }, { message: 'Too common.' }],
    });
    expect(passwordPolicyMessages(error)).toEqual(['Use at least 12 characters.', 'Too common.']);
    expect(passwordPolicyMessages(err({ status: 422, code: 'validation_error' }))).toBeNull();
    expect(passwordPolicyMessages(err({ status: 422, code: 'weak_password' }))).toEqual(['m']);
  });

  it('detects a duplicate email', () => {
    expect(isEmailTaken(err({ status: 409, code: 'email_already_registered' }))).toBe(true);
    expect(isEmailTaken(err({ status: 409, code: 'conflict' }))).toBe(false);
  });
});

describe('tokenFromHash', () => {
  const valid = 'abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE';
  it('reads a well-formed token from the fragment', () => {
    expect(tokenFromHash(`#token=${valid}`)).toBe(valid);
    expect(tokenFromHash(`token=${valid}&x=1`)).toBe(valid);
  });
  it.each(['', '#', '#token=', '#token=short', '#token=has space xxxxxxxxxxxxxxxxxxxxxxxx', '#t=abcdefghijklmnopqrstuvwxyz', `#token=${'a'.repeat(201)}`])(
    'rejects %j',
    (hash) => expect(tokenFromHash(hash)).toBeNull(),
  );
});

describe('recovery errors', () => {
  it('has clear, non-technical messages', () => {
    expect(describeAuthError(err({ status: 400, code: 'invalid_or_expired_token' }))).toMatch(/invalid or has expired/);
    expect(describeAuthError(err({ status: 503, code: 'email_not_configured' }))).toMatch(/cannot send e-mail/);
    expect(describeAuthError(err({ status: 403, code: 'email_not_verified' }))).toMatch(/Confirm your email address/);
  });
  it('never leaves recovery pages as a post-sign-in destination', () => {
    for (const path of ['/forgot-password', '/reset-password', '/reset-password?x=1', '/verify-email#token=abc']) {
      expect(safeRedirectTarget(path)).toBe('/dashboard');
    }
  });
});
