import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router';
import { Alert } from '@/components/feedback/Alert';
import { Button, ButtonLink } from '@/components/ui/Button';
import { confirmEmailVerification } from '@/services/session';
import { useLinkToken } from '../hooks/useLinkToken';
import { describeAuthError } from '../utils/auth-errors';

/**
 * Confirms an e-mail address from an e-mailed link. Confirming needs a click on purpose: link
 * scanners and previewers that fetch URLs must not be able to use up a one-time link by themselves.
 */
export function VerifyEmailPanel() {
  const token = useLinkToken();
  const mutation = useMutation({ mutationFn: () => confirmEmailVerification(token ?? '') });

  if (token === null) {
    return (
      <>
        <h1 className="auth-title">Confirm your email</h1>
        <Alert tone="warning" title="This link is incomplete">
          Open the link from your e-mail exactly as it was sent. You can ask for a new one after signing in.
        </Alert>
        <p className="auth-switch">
          <Link to="/sign-in">Go to sign in</Link>
        </p>
      </>
    );
  }
  if (mutation.isSuccess) {
    return (
      <>
        <h1 className="auth-title">Email confirmed</h1>
        <Alert tone="success" title="Thank you">
          Your email address is now confirmed.
        </Alert>
        <div className="auth-form">
          <ButtonLink to="/sign-in" size="lg" fullWidth>
            Continue
          </ButtonLink>
        </div>
      </>
    );
  }
  return (
    <>
      <h1 className="auth-title">Confirm your email</h1>
      <p className="auth-subtitle">Select the button to confirm that this is your email address.</p>
      <div className="auth-form">
        {mutation.isError && (
          <Alert tone="danger" title="Could not confirm">
            {describeAuthError(mutation.error)}
          </Alert>
        )}
        <Button size="lg" fullWidth loading={mutation.isPending} onClick={() => mutation.mutate()}>
          Confirm my email address
        </Button>
      </div>
    </>
  );
}
