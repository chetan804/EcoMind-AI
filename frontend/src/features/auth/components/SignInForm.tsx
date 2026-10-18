import { useState } from 'react';
import { Link } from 'react-router';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input, PasswordInput } from '@/components/ui/Input';
import { signInSchema, type SignInValues } from '../schemas/auth-forms';
import { SocialButtons } from './SocialButtons';

/**
 * Validates the sign-in fields. Authentication is not implemented: a valid submission is NOT sent
 * anywhere and the form says so rather than pretending to sign in.
 */
export function SignInForm() {
  const [submitted, setSubmitted] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignInValues>({ resolver: zodResolver(signInSchema), defaultValues: { email: '', password: '' } });

  return (
    <>
      <h1 className="auth-title">Welcome back</h1>
      <p className="auth-subtitle">Sign in to your EcoMind AI workspace.</p>
      <form className="auth-form" noValidate onSubmit={handleSubmit(() => setSubmitted(true))}>
        <Field label="Email address" error={errors.email?.message}>
          {(control) => (
            <Input {...control} size="lg" type="email" autoComplete="email" placeholder="you@example.com" {...register('email')} />
          )}
        </Field>
        <Field label="Password" error={errors.password?.message}>
          {(control) => <PasswordInput {...control} size="lg" autoComplete="current-password" {...register('password')} />}
        </Field>
        <div className="auth-form__aside">
          <Button variant="ghost" unavailableReason="Password reset is not available yet.">
            Forgot password?
          </Button>
        </div>
        {submitted && (
          <Alert tone="warning" title="Sign-in is not available yet">
            Authentication has not been implemented, so nothing was sent and no session was created.
          </Alert>
        )}
        <Button type="submit" size="lg" fullWidth>
          Sign in
        </Button>
      </form>
      <SocialButtons />
      <p className="auth-switch">
        Don&rsquo;t have an account? <Link to="/sign-up">Sign up</Link>
      </p>
    </>
  );
}
