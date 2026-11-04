import { signInSchema, signUpSchema } from '@/features/auth/schemas/auth-forms';

describe('signInSchema', () => {
  it('accepts a valid email and any non-empty password', () => {
    expect(signInSchema.safeParse({ email: 'a@b.co', password: 'x' }).success).toBe(true);
  });

  it('reports required and malformed fields', () => {
    const empty = signInSchema.safeParse({ email: '', password: '' });
    expect(empty.success).toBe(false);
    const messages = empty.error?.issues.map((i) => i.message);
    expect(messages).toContain('Enter your email address.');
    expect(messages).toContain('Enter your password.');
    expect(signInSchema.safeParse({ email: 'nope', password: 'x' }).error?.issues[0]?.message).toBe('Enter a valid email address.');
  });
});

describe('signUpSchema', () => {
  const valid = { name: 'Asha', email: 'asha@example.org', password: 'a-long-passphrase', confirmPassword: 'a-long-passphrase', accountType: 'citizen' as const };

  it('accepts valid input', () => {
    expect(signUpSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects short passwords and mismatched confirmation', () => {
    expect(signUpSchema.safeParse({ ...valid, password: 'short', confirmPassword: 'short' }).error?.issues[0]?.message).toMatch(/at least 12/);
    const mismatch = signUpSchema.safeParse({ ...valid, confirmPassword: 'different-passphrase' });
    expect(mismatch.error?.issues[0]?.path).toEqual(['confirmPassword']);
    expect(mismatch.error?.issues[0]?.message).toBe('The passwords do not match.');
  });

  it('never accepts administrator as an account type, and asks for a reason for operational roles', () => {
    expect(signUpSchema.safeParse({ ...valid, accountType: 'administrator' }).success).toBe(false);
    const noReason = signUpSchema.safeParse({ ...valid, accountType: 'manager', reason: 'short' });
    expect(noReason.error?.issues[0]?.path).toEqual(['reason']);
    expect(signUpSchema.safeParse({ ...valid, accountType: 'manager', reason: 'I coordinate the ward collection teams.' }).success).toBe(true);
  });
});
