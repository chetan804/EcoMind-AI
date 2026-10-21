import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Alert } from '@/components/feedback/Alert';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { PasswordInput } from '@/components/ui/Input';
import { clearSession, confirmPasswordReset } from '@/services/session';
import { useLinkToken } from '../hooks/useLinkToken';
import { MIN_PASSWORD_LENGTH, resetPasswordSchema, type ResetPasswordValues } from '../schemas/auth-forms';
import { describeAuthError, isInvalidToken, passwordPolicyMessages } from '../utils/auth-errors';

/**
 * Lets the person behind an e-mailed link choose a new password. The token is read once from the
 * URL fragment and then removed from the address bar, so it is not left in history, bookmarks or a
 * screenshot. A server that rejects the password keeps the link valid, so the person can retry.
 */
export function ResetPasswordForm() {
  const token = useLinkToken();

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ResetPasswordValues>({ resolver: zodResolver(resetPasswordSchema), defaultValues: { password: '', confirmPassword: '' } });
  const mutation = useMutation({
    mutationFn: (values: ResetPasswordValues) => confirmPasswordReset(token ?? '', values.password),
    onSuccess: () => clearSession(), // the server ended every session; drop the local one too
    onError: (error) => {
      const policy = passwordPolicyMessages(error);
      if (policy) setError('password', { message: policy.join(' ') });
    },
  });

  if (token === null) {
    return (
      <>
        <h1 className="auth-title">Reset your password</h1>
        <Alert tone="warning" title="This link is incomplete">
          Open the link from your e-mail exactly as it was sent, or request a new one.
        </Alert>
        <p className="auth-switch">
          <Link to="/forgot-password">Request a new link</Link>
        </p>
      </>
    );
  }
  if (mutation.isSuccess) {
    return (
      <>
        <h1 className="auth-title">Password changed</h1>
        <Alert tone="success" title="You can sign in with your new password">
          Every device was signed out. If two-step verification is on for your account, it is still required.
        </Alert>
        <div className="auth-form">
          <ButtonLink to="/sign-in" size="lg" fullWidth>
            Go to sign in
          </ButtonLink>
        </div>
      </>
    );
  }
  const expired = mutation.isError && isInvalidToken(mutation.error);
  const showBanner = mutation.isError && !passwordPolicyMessages(mutation.error);
  return (
    <>
      <h1 className="auth-title">Choose a new password</h1>
      <p className="auth-subtitle">Pick something you do not use anywhere else.</p>
      <form className="auth-form" noValidate onSubmit={handleSubmit((values) => mutation.mutate(values))}>
        <Field
          label="New password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters. A short phrase of unrelated words works well.`}
          error={errors.password?.message}
        >
          {(control) => <PasswordInput {...control} size="lg" autoComplete="new-password" data-autofocus {...register('password')} />}
        </Field>
        <Field label="Confirm new password" error={errors.confirmPassword?.message}>
          {(control) => <PasswordInput {...control} size="lg" autoComplete="new-password" {...register('confirmPassword')} />}
        </Field>
        {showBanner && (
          <Alert tone="danger" title={expired ? 'This link no longer works' : 'Could not change the password'}>
            {describeAuthError(mutation.error)}
          </Alert>
        )}
        {expired ? (
          <ButtonLink to="/forgot-password" size="lg" fullWidth>
            Request a new link
          </ButtonLink>
        ) : (
          <Button type="submit" size="lg" fullWidth loading={mutation.isPending}>
            Change password
          </Button>
        )}
      </form>
    </>
  );
}
