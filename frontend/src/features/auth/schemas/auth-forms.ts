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

export const signUpSchema = z
  .object({
    name: z.string().trim().min(1, 'Enter your name.'),
    email,
    password: z
      .string()
      .min(MIN_PASSWORD_LENGTH, `Use at least ${MIN_PASSWORD_LENGTH} characters.`),
    confirmPassword: z.string().min(1, 'Repeat your password.'),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ['confirmPassword'],
    message: 'The passwords do not match.',
  });

export type SignInValues = z.infer<typeof signInSchema>;
export type SignUpValues = z.infer<typeof signUpSchema>;
