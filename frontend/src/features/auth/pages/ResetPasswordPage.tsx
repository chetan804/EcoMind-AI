import { AuthCard } from '../components/AuthCard';
import { ResetPasswordForm } from '../components/ResetPasswordForm';

/** Not wrapped in `RedirectIfSignedIn`: the link may be opened in a browser that is signed in. */
export function ResetPasswordPage() {
  return (
    <AuthCard>
      <ResetPasswordForm />
    </AuthCard>
  );
}
