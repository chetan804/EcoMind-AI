import { z } from 'zod';

/**
 * Client-side validation for the sign-in and sign-up forms: early feedback only. The server
 * enforces the real password policy (backend/app/modules/auth/policy.py: 12 to 128 characters,
 * no common or personal passwords) and its messages are shown when it rejects a password.
 */
export const MIN_PASSWORD_LENGTH = 12;

const email = z.string().trim().min(1, 'Enter your email address.').pipe(z.email('Enter a valid email address.'));

export const signInSchema = z.object({
  email,
  password: z.string().min(1, 'Enter your password.'),
});

export const ACCOUNT_TYPES = ['citizen', 'collector', 'facility_operator', 'manager'] as const;
export type AccountType = (typeof ACCOUNT_TYPES)[number];
export const MIN_ROLE_REASON = 20;

/**
 * Everyone registers as a citizen. Choosing an operational account type only sends a role request
 * after the account exists: it needs a reason, and an administrator decides.
 */
export const signUpSchema = z
  .object({
    name: z.string().trim().min(1, 'Enter your name.'),
    email,
    password: z
      .string()
      .min(MIN_PASSWORD_LENGTH, `Use at least ${MIN_PASSWORD_LENGTH} characters.`),
    confirmPassword: z.string().min(1, 'Repeat your password.'),
    accountType: z.enum(ACCOUNT_TYPES),
    organisation: z.string().trim().max(200).optional(),
    reason: z.string().trim().max(2000).optional(),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ['confirmPassword'],
    message: 'The passwords do not match.',
  })
  .refine((values) => values.accountType === 'citizen' || (values.reason ?? '').length >= MIN_ROLE_REASON, {
    path: ['reason'],
    message: `Tell the administrator why you need this role (at least ${MIN_ROLE_REASON} characters).`,
  });

export const forgotPasswordSchema = z.object({ email });

export const resetPasswordSchema = z
  .object({
    password: z.string().min(MIN_PASSWORD_LENGTH, `Use at least ${MIN_PASSWORD_LENGTH} characters.`),
    confirmPassword: z.string().min(1, 'Repeat your password.'),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ['confirmPassword'],
    message: 'The passwords do not match.',
  });

export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;
export type SignInValues = z.infer<typeof signInSchema>;
export type SignUpValues = z.infer<typeof signUpSchema>;
