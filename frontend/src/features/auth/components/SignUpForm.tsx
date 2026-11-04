import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Alert } from '@/components/feedback/Alert';
import { useToast } from '@/components/feedback/toast-context';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input, PasswordInput, Textarea } from '@/components/ui/Input';
import { createRoleRequest } from '@/features/access-requests';
import { getErrorMessage } from '@/services/error-handler';
import { signUp } from '@/services/session/session-store';
import { MIN_PASSWORD_LENGTH, MIN_ROLE_REASON, signUpSchema, type AccountType, type SignUpValues } from '../schemas/auth-forms';
import { describeAuthError, isEmailTaken, passwordPolicyMessages } from '../utils/auth-errors';
import { AccountTypePicker } from './AccountTypePicker';

/**
 * Creates a citizen account through the backend and signs in. A role is never chosen here: picking
 * an operational account type sends a role request after the account exists, and an administrator
 * decides. The server refuses any attempt to register with another role.
 */
export function SignUpForm({ accountType, onAccountType }: { accountType: AccountType; onAccountType: (type: AccountType) => void }) {
  const toast = useToast();
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    formState: { errors },
  } = useForm<SignUpValues>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { name: '', email: '', password: '', confirmPassword: '', accountType, organisation: '', reason: '' },
  });
  const mutation = useMutation({
    mutationFn: async (values: SignUpValues) => {
      await signUp({ email: values.email, password: values.password, full_name: values.name });
      if (values.accountType === 'citizen') return;
      // The account exists and is signed in: now ask for the operational role. A failure here must
      // not be silent; the person can send the request again from Settings, Access and roles.
      try {
        await createRoleRequest({
          requested_role: values.accountType,
          reason: values.reason ?? '',
          organisation: values.organisation || undefined,
        });
        toast({ tone: 'success', title: 'Account created and role requested', description: 'An administrator will review your request. Until then you have citizen access.' });
      } catch (error) {
        toast({ tone: 'danger', title: 'Account created, but the role request was not sent', description: `${getErrorMessage(error)} Send it again under Settings, Access and roles.` });
      }
    },
    onError: (error) => {
      const policy = passwordPolicyMessages(error);
      if (policy) setError('password', { message: policy.join(' ') });
      else if (isEmailTaken(error)) setError('email', { message: 'An account with this email already exists. Try signing in.' });
    },
  });
  // Field-level problems are shown on their field; anything else gets the banner.
  const showBanner = mutation.isError && !passwordPolicyMessages(mutation.error) && !isEmailTaken(mutation.error);
  const operational = accountType !== 'citizen';

  return (
    <>
      <h1 className="auth-title">Create your account</h1>
      <p className="auth-subtitle">Join your city&rsquo;s EcoMind AI workspace.</p>
      <form className="auth-form" noValidate onSubmit={handleSubmit((values) => mutation.mutate(values))}>
        <AccountTypePicker
          value={accountType}
          onChange={(type) => {
            onAccountType(type);
            setValue('accountType', type);
          }}
        />
        <Field label="Full name" error={errors.name?.message}>
          {(control) => <Input {...control} size="lg" autoComplete="name" {...register('name')} />}
        </Field>
        <Field label="Email address" error={errors.email?.message}>
          {(control) => <Input {...control} size="lg" type="email" autoComplete="email" placeholder="you@example.com" {...register('email')} />}
        </Field>
        <Field label="Password" hint={`At least ${MIN_PASSWORD_LENGTH} characters. A short phrase of unrelated words works well.`} error={errors.password?.message}>
          {(control) => <PasswordInput {...control} size="lg" autoComplete="new-password" {...register('password')} />}
        </Field>
        <Field label="Confirm password" error={errors.confirmPassword?.message}>
          {(control) => <PasswordInput {...control} size="lg" autoComplete="new-password" {...register('confirmPassword')} />}
        </Field>
        {operational && (
          <>
            <Field label="Organisation or team (optional)" error={errors.organisation?.message}>
              {(control) => <Input {...control} size="lg" autoComplete="organization" {...register('organisation')} />}
            </Field>
            <Field label="Why do you need this role?" hint={`At least ${MIN_ROLE_REASON} characters. An administrator reads this before approving.`} error={errors.reason?.message}>
              {(control) => <Textarea {...control} {...register('reason')} />}
            </Field>
          </>
        )}
        {showBanner && (
          <Alert tone="danger" title="Could not create the account">
            {describeAuthError(mutation.error)}
          </Alert>
        )}
        <Button type="submit" size="lg" fullWidth loading={mutation.isPending}>
          {operational ? 'Create account and request role' : 'Create account'}
        </Button>
      </form>
      <p className="auth-switch">
        Already have an account? <Link to="/sign-in">Sign in</Link>
      </p>
    </>
  );
}
