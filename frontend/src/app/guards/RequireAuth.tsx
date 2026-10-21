import { Navigate, Outlet, useLocation } from 'react-router';
import { PageLoading } from '@/components/feedback/Loading';
import { useAuth } from '@/services/session';

const SECURITY_PATH = '/settings/security';

/**
 * Layout route that admits signed-in users only. While the session is being restored from the
 * refresh cookie it shows a loading state (so a signed-in user never flashes the sign-in page);
 * anonymous visitors are sent to sign-in and returned here afterwards.
 *
 * This is a usability layer. Every API call is authorised again on the server.
 */
export function RequireAuth() {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === 'unknown') return <PageLoading />;
  if (status === 'anonymous') {
    return <Navigate to="/sign-in" replace state={{ from: `${location.pathname}${location.search}` }} />;
  }
  // A role that requires two-step verification gets nowhere else until it is set up (the server
  // refuses every other request with 403 mfa_enrollment_required, so this just avoids dead ends).
  if (user?.mfa_enrollment_required && location.pathname !== SECURITY_PATH) {
    return <Navigate to={SECURITY_PATH} replace />;
  }
  return <Outlet />;
}
