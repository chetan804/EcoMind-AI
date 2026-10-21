import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { requestPasswordReset } from '@/services/session';
import { useAuthConfig } from '../hooks/useAuthConfig';
import { forgotPasswordSchema, type ForgotPasswordValues } from '../schemas/auth-forms';
import { describeAuthError } from '../utils/auth-errors';

/**
 * Asks the server to e-mail a one-time reset link. The confirmation is deliberately the same for
 * every address (the API never says whether an account exists), and when the server has no e-mail
 * delivery the form is replaced by an honest explanation instead of promising a message.
 */
export function ForgotPasswordForm() {
  const config = useAuthConfig();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema), defaultValues: { email: '' } });
  const mutation = useMutation({ mutationFn: (values: ForgotPasswordValues) => requestPasswordReset(values.email) });

  const back = (
    <p className="auth-switch">
      <Link to="/sign-in">Back to sign in</Link>
    </p>
  );

  if (config.isPending) {
    return (
      <>
        <h1 className="auth-title">Reset your password</h1>
        <p className="auth-subtitle" role="status">
          Checking what this server supports&hellip;
        </p>
      </>
    );
  }
  if (config.isError) {
    return (
      <>
        <h1 className="auth-title">Reset your password</h1>
        <Alert tone="danger" title="Could not reach the server">
          {describeAuthError(config.error)}{' '}
          <Button variant="ghost" onClick={() => void config.refetch()}>
            Try again
          </Button>
        </Alert>
        {back}
      </>
    );
  }
  if (!config.data.password_reset_available) {
    return (
      <>
        <h1 className="auth-title">Reset your password</h1>
        <Alert tone="warning" title="Password reset by e-mail is not enabled">
          This server is not set up to send e-mail, so a reset link could never reach you. Ask an administrator to reset your access.
        </Alert>
        {back}
      </>
    );
  }
  if (mutation.isSuccess) {
    return (
      <>
        <h1 className="auth-title">Check your inbox</h1>
        <Alert tone="success" title="Request received">
          If an account exists for that address, an e-mail with a reset link is on its way. The link works once and expires soon. Nothing arrived? Check
          your spam folder, or try again in a few minutes.
        </Alert>
        {back}
      </>
    );
  }
  return (
    <>
      <h1 className="auth-title">Reset your password</h1>
      <p className="auth-subtitle">Enter your email address and we will send you a link to choose a new password.</p>
      <form className="auth-form" noValidate onSubmit={handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Email address" error={errors.email?.message}>
          {(control) => (
            <Input {...control} size="lg" type="email" autoComplete="email" placeholder="you@example.com" {...register('email')} />
          )}
        </Field>
        {mutation.isError && (
          <Alert tone="danger" title="Could not send the link">
            {describeAuthError(mutation.error)}
          </Alert>
        )}
        <Button type="submit" size="lg" fullWidth loading={mutation.isPending}>
          Send reset link
        </Button>
      </form>
      {back}
    </>
  );
}
