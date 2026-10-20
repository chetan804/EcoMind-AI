import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input, PasswordInput } from '@/components/ui/Input';
import { signIn } from '@/services/session/session-store';
import { signInSchema, type SignInValues } from '../schemas/auth-forms';
import { describeAuthError } from '../utils/auth-errors';
import { MfaStep } from './MfaStep';
import { SocialButtons } from './SocialButtons';

/**
 * Signs in through the backend. On success the session store flips to authenticated and
 * `RedirectIfSignedIn` (wrapping the page) navigates to the originally requested page.
 */
export function SignInForm() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignInValues>({ resolver: zodResolver(signInSchema), defaultValues: { email: '', password: '' } });
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: (values: SignInValues) => signIn(values.email, values.password),
    onSuccess: (result) => {
      if (result.status === 'mfa_required') setMfaToken(result.mfaToken);
    },
  });

  if (mfaToken !== null) {
    return (
      <MfaStep
        mfaToken={mfaToken}
        onBack={() => {
          setMfaToken(null);
          mutation.reset();
        }}
      />
    );
  }

  return (
    <>
      <h1 className="auth-title">Welcome back</h1>
      <p className="auth-subtitle">Sign in to your EcoMind AI workspace.</p>
      <form className="auth-form" noValidate onSubmit={handleSubmit((values) => mutation.mutate(values))}>
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
        {mutation.isError && (
          <Alert tone="danger" title="Could not sign in">
            {describeAuthError(mutation.error)}
          </Alert>
        )}
        <Button type="submit" size="lg" fullWidth loading={mutation.isPending}>
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
