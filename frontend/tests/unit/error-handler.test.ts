import { ApiError } from '@/services/api-client';
import { getErrorMessage, isRetryableError } from '@/services/error-handler';

const apiError = (status: number, message = 'Server said no') =>
  new ApiError({ status, code: 'x', message });

describe('getErrorMessage', () => {
  it('shows backend messages for client errors', () => {
    expect(getErrorMessage(apiError(409, 'Already exists'))).toBe('Already exists');
  });

  it('never exposes server error text for 5xx responses or unknown errors', () => {
    expect(getErrorMessage(apiError(500, 'psycopg.OperationalError: password'))).not.toMatch(/psycopg/);
    expect(getErrorMessage(new Error('internal detail'))).not.toMatch(/internal/);
  });

  it('has specific messages for network, auth and permission failures', () => {
    expect(getErrorMessage(apiError(0))).toMatch(/cannot reach/i);
    expect(getErrorMessage(apiError(401))).toMatch(/sign in/i);
    expect(getErrorMessage(apiError(403))).toMatch(/permission/i);
  });
});

describe('isRetryableError', () => {
  it('retries network and server errors but not client errors', () => {
    expect(isRetryableError(apiError(0))).toBe(true);
    expect(isRetryableError(apiError(503))).toBe(true);
    expect(isRetryableError(apiError(404))).toBe(false);
    expect(isRetryableError(new Error('x'))).toBe(false);
  });
});
