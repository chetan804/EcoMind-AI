import { AuthCard } from '../components/AuthCard';
import { ForgotPasswordForm } from '../components/ForgotPasswordForm';
import { RedirectIfSignedIn } from '../components/RedirectIfSignedIn';

export function ForgotPasswordPage() {
  return (
    <RedirectIfSignedIn>
      <AuthCard>
        <ForgotPasswordForm />
      </AuthCard>
    </RedirectIfSignedIn>
  );
}
