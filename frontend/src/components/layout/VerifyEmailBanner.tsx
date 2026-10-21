import { useMutation, useQuery } from '@tanstack/react-query';
import { Alert } from '@/components/feedback/Alert';
import { Button } from '@/components/ui/Button';
import { getErrorMessage } from '@/services/error-handler';
import { fetchAuthConfig, requestEmailVerification, useAuth } from '@/services/session';

/**
 * Asks a signed-in person to confirm their e-mail address, but only when the server can actually
 * send the link (otherwise the banner would promise something that cannot happen).
 */
export function VerifyEmailBanner() {
  const { user } = useAuth();
  const unverified = user !== null && !user.email_verified;
  const config = useQuery({
    queryKey: ['auth', 'config'],
    queryFn: ({ signal }) => fetchAuthConfig(signal),
    staleTime: 5 * 60_000,
    enabled: unverified,
  });
  const send = useMutation({ mutationFn: (email: string) => requestEmailVerification(email) });

  if (!unverified || !config.data?.email_verification_available) return null;
  return (
    <div className="shell__notice">
      {send.isSuccess ? (
        <Alert tone="success" title="Check your inbox">
          A confirmation link is on its way to {user.email}.
        </Alert>
      ) : (
        <Alert tone="info" title="Confirm your email address">
          We sent a link to {user.email}. Selecting it confirms the address.{' '}
          <Button variant="secondary" loading={send.isPending} onClick={() => send.mutate(user.email)}>
            Send a new link
          </Button>
          {send.isError && <span role="alert"> {getErrorMessage(send.error)}</span>}
        </Alert>
      )}
    </div>
  );
}
