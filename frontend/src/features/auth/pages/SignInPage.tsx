import { AuthCard } from '../components/AuthCard';
import { RedirectIfSignedIn } from '../components/RedirectIfSignedIn';
import { SignInForm } from '../components/SignInForm';

export function SignInPage() {
  return (
    <RedirectIfSignedIn>
      <AuthCard>
        <SignInForm />
      </AuthCard>
    </RedirectIfSignedIn>
  );
}
