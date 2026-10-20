import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input, PasswordInput } from '@/components/ui/Input';
import { signUp } from '@/services/session/session-store';
import { MIN_PASSWORD_LENGTH, signUpSchema, type SignUpValues } from '../schemas/auth-forms';
import { describeAuthError, isEmailTaken, passwordPolicyMessages } from '../utils/auth-errors';
import { SocialButtons } from './SocialButtons';

/** Creates a citizen account through the backend and signs in. Roles cannot be chosen here. */
export function SignUpForm() {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<SignUpValues>({
    resolver: zodResolver(signUpSchema),
    defaultValues: { name: '', email: '', password: '', confirmPassword: '' },
  });
  const mutation = useMutation({
    mutationFn: (values: SignUpValues) =>
      signUp({ email: values.email, password: values.password, full_name: values.name }),
    onError: (error) => {
      const policy = passwordPolicyMessages(error);
      if (policy) setError('password', { message: policy.join(' ') });
      else if (isEmailTaken(error)) setError('email', { message: 'An account with this email already exists. Try signing in.' });
    },
  });
  // Field-level problems are shown on their field; anything else gets the banner.
  const showBanner =
    mutation.isError && !passwordPolicyMessages(mutation.error) && !isEmailTaken(mutation.error);

  return (
    <>
      <h1 className="auth-title">Create your account</h1>
      <p className="auth-subtitle">Join your city&rsquo;s EcoMind AI workspace.</p>
      <form className="auth-form" noValidate onSubmit={handleSubmit((values) => mutation.mutate(values))}>
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
          hint={`At least ${MIN_PASSWORD_LENGTH} characters. A short phrase of unrelated words works well.`}
          error={errors.password?.message}
        >
          {(control) => <PasswordInput {...control} size="lg" autoComplete="new-password" {...register('password')} />}
        </Field>
        <Field label="Confirm password" error={errors.confirmPassword?.message}>
          {(control) => <PasswordInput {...control} size="lg" autoComplete="new-password" {...register('confirmPassword')} />}
        </Field>
        {showBanner && (
          <Alert tone="danger" title="Could not create the account">
            {describeAuthError(mutation.error)}
          </Alert>
        )}
        <Button type="submit" size="lg" fullWidth loading={mutation.isPending}>
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
