import { useMutation } from '@tanstack/react-query';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { completeMfaSignIn } from '@/services/session/session-store';
import { describeAuthError } from '../utils/auth-errors';

const schema = z.object({ code: z.string().trim().min(6, 'Enter the 6-digit code or a recovery code.').max(32, 'That code is too long.') });
type Values = z.infer<typeof schema>;

/** Second sign-in step: the password was right, now prove possession of the authenticator. */
export function MfaStep({ mfaToken, onBack }: { mfaToken: string; onBack: () => void }) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { code: '' } });
  const mutation = useMutation({ mutationFn: (values: Values) => completeMfaSignIn(mfaToken, values.code) });

  return (
    <>
      <h1 className="auth-title">Two-step verification</h1>
      <p className="auth-subtitle">Enter the 6-digit code from your authenticator app, or one of your recovery codes.</p>
      <form className="auth-form" noValidate onSubmit={handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Verification code" error={errors.code?.message}>
          {(control) => (
            <Input {...control} size="lg" autoComplete="one-time-code" inputMode="text" data-autofocus autoFocus {...register('code')} />
          )}
        </Field>
        {mutation.isError && (
          <Alert tone="danger" title="Could not verify">
            {describeAuthError(mutation.error)}
          </Alert>
        )}
        <Button type="submit" size="lg" fullWidth loading={mutation.isPending}>
          Verify and sign in
        </Button>
        <Button type="button" variant="ghost" fullWidth onClick={onBack}>
          Back to sign in
        </Button>
      </form>
    </>
  );
}
