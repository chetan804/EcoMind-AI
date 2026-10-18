import { useState } from 'react';
import { Link } from 'react-router';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input, PasswordInput } from '@/components/ui/Input';
import { PROVISIONAL_MIN_PASSWORD_LENGTH, signUpSchema, type SignUpValues } from '../schemas/auth-forms';
import { SocialButtons } from './SocialButtons';

/** Validates the sign-up fields. Registration is not implemented; nothing is sent. */
export function SignUpForm() {
  const [submitted, setSubmitted] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignUpValues>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { name: '', email: '', password: '', confirmPassword: '' },
  });

  return (
    <>
      <h1 className="auth-title">Create your account</h1>
      <p className="auth-subtitle">Join your city&rsquo;s EcoMind AI workspace.</p>
      <form className="auth-form" noValidate onSubmit={handleSubmit(() => setSubmitted(true))}>
        <Field label="Full name" error={errors.name?.message}>
          {(control) => <Input {...control} size="lg" autoComplete="name" {...register('name')} />}
        </Field>
        <Field label="Email address" error={errors.email?.message}>
          {(control) => (
            <Input {...control} size="lg" type="email" autoComplete="email" placeholder="you@example.com" {...register('email')} />
          )}
        </Field>
        <Field
          label="Password"
          hint={`At least ${PROVISIONAL_MIN_PASSWORD_LENGTH} characters (provisional rule).`}
          error={errors.password?.message}
        >
          {(control) => <PasswordInput {...control} size="lg" autoComplete="new-password" {...register('password')} />}
        </Field>
        <Field label="Confirm password" error={errors.confirmPassword?.message}>
          {(control) => <PasswordInput {...control} size="lg" autoComplete="new-password" {...register('confirmPassword')} />}
        </Field>
        {submitted && (
          <Alert tone="warning" title="Registration is not available yet">
            Account creation has not been implemented, so nothing was sent and no account was created.
          </Alert>
        )}
        <Button type="submit" size="lg" fullWidth>
          Create account
        </Button>
      </form>
      <SocialButtons />
      <p className="auth-switch">
        Already have an account? <Link to="/sign-in">Sign in</Link>
      </p>
    </>
  );
}
