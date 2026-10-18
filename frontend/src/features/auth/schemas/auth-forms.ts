import { z } from 'zod';

/**
 * Client-side validation for the sign-in and sign-up forms.
 * PROVISIONAL: the password rules (minimum length, breach checks) are defined by the
 * authentication milestone (docs/security/security-baseline.md). 12 characters is a placeholder.
 */
export const PROVISIONAL_MIN_PASSWORD_LENGTH = 12;

const email = z.string().trim().min(1, 'Enter your email address.').pipe(z.email('Enter a valid email address.'));

export const signInSchema = z.object({
  email,
  password: z.string().min(1, 'Enter your password.'),
});

export const signUpSchema = z
  .object({
    name: z.string().trim().min(1, 'Enter your name.'),
    email,
    password: z
      .string()
      .min(PROVISIONAL_MIN_PASSWORD_LENGTH, `Use at least ${PROVISIONAL_MIN_PASSWORD_LENGTH} characters.`),
    confirmPassword: z.string().min(1, 'Repeat your password.'),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ['confirmPassword'],
    message: 'The passwords do not match.',
  });

export type SignInValues = z.infer<typeof signInSchema>;
export type SignUpValues = z.infer<typeof signUpSchema>;
